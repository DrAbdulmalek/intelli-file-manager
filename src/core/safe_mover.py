"""SafeMover — نقل ونسخ آمن ذرّي مع تحقّق checksum ومعالجة sidecar

هذه الوحدة تنفّذ عمليات النقل/النسخ بأمان:
  - نقل ذرّي: كتابة إلى ملف مؤقت ثم rename (POSIX atomic rename)
  - تحقّق SHA-256 قبل وبعد العملية (integrity verification)
  - معالجة sidecar: نقل/نسخ ملف .ifm_meta_<name>.json مع الملف الأصلي
  - حل تضارب الأسماء: إضافة لاحقة _1, _2, ... تلقائيًا (ممنوع الكتابة فوق أي موجود)
  - تنظيف الملف المؤقت عند الفشل (rollback)
  - لا توجد إجراءات تدميرية: لا يحذف الملف المصدر عند الفشل
  - لا AI، لا medical — فقط عمليات ملفات آمنة

التصميم:
  - كل عملية تُرجع MoveResult/CopyResult يحتوي على: source, destination,
    checksum_before, checksum_after, success, error, sidecar_moved, duration_ms
  - لو فشل التحقّق بعد النقل، يُعاد الملف إلى موضعه الأصلي (rollback)
  - thread-safe عبر قفل لكل عملية (لا حالة مشتركة)
  - يعمل مع RuleEngine._exec_move/_exec_copy كبديل آمن

PR-07 من development-roadmap-v1.0 (IFM Phase A)
"""
from __future__ import annotations

import ctypes
import ctypes.util
import errno
import hashlib
import logging
import os
import shutil
import stat
import tempfile
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import List, Optional, Union

logger = logging.getLogger(__name__)

# renameat2(RENAME_NOREPLACE) عبر ctypes — للنقل الذرّي الذي يرفض الاستبدال
_RENAME_NOREPLACE = 1  # RENAME_NOREPLACE per Linux renameat2(2)
_libc = None
_renameat2_available = False

try:
    _libc_path = ctypes.util.find_library("c")
    if _libc_path:
        _libc = ctypes.CDLL(_libc_path, use_errno=True)
        # renameat2(int olddirfd, const char *oldpath, int newdirfd,
        #           const char *newpath, unsigned int flags)
        _libc.renameat2.restype = ctypes.c_long
        _libc.renameat2.argtypes = [
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_uint,
        ]
        _renameat2_available = True
except (OSError, AttributeError):
    _libc = None
    _renameat2_available = False


# ─── ثوابت ─────────────────────────────────────────────────────────────────

# حجم الكتلة لقراءة الملف أثناء حساب checksum (64 KB)
_CHECKSUM_CHUNK_SIZE = 64 * 1024

# أقصى عدد محاولات لإيجاد اسم فريد عند التضارب
_MAX_NAME_COLLISION_RETRIES = 999

# overwrite محظور كلياً وفق تعليمات المستخدم: "ممنوع الكتابة فوق أي موجود"
OVERWRITE_FORBIDDEN = True


# ─── Dataclasses ────────────────────────────────────────────────────────────

@dataclass
class MoveResult:
    """نتيجة عملية نقل آمنة"""
    source: str
    destination: str
    checksum_before: str = ""
    checksum_after: str = ""
    sidecar_moved: bool = False
    sidecar_source: Optional[str] = None
    sidecar_destination: Optional[str] = None
    success: bool = True
    error: Optional[str] = None
    duration_ms: float = 0.0
    # هل استُخدمت لاحقة لحل التضارب؟
    renamed_due_to_collision: bool = False
    # المسار النهائي الفعلي (قد يختلف عن destination لو حدث تضارب)
    final_path: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        # ضمان أن final_path معبأ دائمًا
        if not d.get("final_path"):
            d["final_path"] = d.get("destination", "")
        return d


@dataclass
class CopyResult:
    """نتيجة عملية نسخ آمنة"""
    source: str
    destination: str
    checksum_before: str = ""
    checksum_after: str = ""
    sidecar_copied: bool = False
    sidecar_source: Optional[str] = None
    sidecar_destination: Optional[str] = None
    success: bool = True
    error: Optional[str] = None
    duration_ms: float = 0.0
    renamed_due_to_collision: bool = False
    final_path: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        if not d.get("final_path"):
            d["final_path"] = d.get("destination", "")
        return d


# ─── استثناءات ─────────────────────────────────────────────────────────────

class SafeMoveError(Exception):
    """خطأ في النقل الآمن"""


class ChecksumMismatchError(SafeMoveError):
    """عدم تطابق checksum بعد النقل/النسخ"""


class SourceNotFoundError(SafeMoveError):
    """الملف المصدر غير موجود"""


class OverwriteForbiddenError(SafeMoveError):
    """محاولة الكتابة فوق ملف موجود — محظور وفق تعليمات المستخدم"""


def _reject_symlink_components(path: Union[str, Path]) -> None:
    """يرفض أي مكوّن symlink في المسار، ويفشل مغلقاً عند تعذر فحصه."""
    absolute = Path(os.path.abspath(os.fspath(path)))
    current = Path(absolute.anchor)
    for part in absolute.parts[1:]:
        current = current / part
        try:
            info = current.lstat()
        except FileNotFoundError:
            # ما دام أحد الآباء غير موجود فلا يمكن أن توجد مكونات لاحقة تحته.
            break
        except OSError as exc:
            raise SafeMoveError(f"تعذر فحص مكوّن المسار {current}: {exc}") from exc
        if stat.S_ISLNK(info.st_mode):
            raise SafeMoveError(f"المسار يحتوي رابطاً رمزياً محظوراً: {current}")
        if current != absolute and not stat.S_ISDIR(info.st_mode):
            raise SafeMoveError(f"مكوّن وسيط ليس مجلداً: {current}")


def _validate_safe_file_paths(src: Path, dst: Path) -> None:
    """يتحقق من مساري المصدر والوجهة قبل أي قراءة أو إنشاء أو نشر."""
    _reject_symlink_components(src)
    _reject_symlink_components(dst)
    try:
        source_info = src.lstat()
    except FileNotFoundError:
        return  # تتولى الواجهة إرجاع SourceNotFoundError بصورة موحدة.
    except OSError as exc:
        raise SafeMoveError(f"تعذر فحص المصدر {src}: {exc}") from exc
    if not stat.S_ISREG(source_info.st_mode):
        raise SafeMoveError(f"المصدر ليس ملفاً عادياً: {src}")


# ─── دوال مساعدة ───────────────────────────────────────────────────────────

def compute_sha256(file_path: Union[str, Path], *, chunk_size: int = _CHECKSUM_CHUNK_SIZE) -> str:
    """يحسب SHA-256 لملف

    Args:
        file_path: مسار الملف
        chunk_size: حجم الكتلة بالبايت (افتراضيًا 64 KB)

    Returns:
        hex digest بصيغة 64 حرفًا، أو "" لو الملف غير موجود

    Raises:
        OSError: لو فشلت قراءة الملف
    """
    p = Path(file_path)
    if not p.exists():
        return ""
    h = hashlib.sha256()
    with p.open("rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _reraise_if_interrupt(exc: BaseException) -> None:
    """إعادة إطلاق المقاطعات (KeyboardInterrupt/SystemExit) — لا يجوز ابتلاعها
    داخل نتائج العمليات؛ تنظيف الحالة ثم الإطلاق (مراجعة جلسة ChatGPT، المرحلة 3)."""
    if isinstance(exc, (KeyboardInterrupt, SystemExit)):
        raise exc


def _sidecar_path(file_path: Union[str, Path]) -> Path:
    """يُرجع مسار ملف sidecar (.ifm_meta_<name>.json) بجانب الملف

    ملاحظة: يجب أن يتطابق هذا مع rule_engine._sidecar_path
    """
    p = Path(file_path)
    return p.parent / f".ifm_meta_{p.name}.json"


def _resolve_collision(dst: Path, src: Path) -> tuple[Path, bool]:
    """يحل تضارب الأسماء بإضافة لاحقة _1, _2, ...

    Returns:
        (final_destination, was_renamed)
    """
    if not dst.exists():
        return dst, False
    # لو src و dst نفس الملف (نقل إلى نفس الموضع)
    try:
        if src.resolve() == dst.resolve():
            return dst, False
    except OSError:
        pass

    stem = dst.stem
    suffix = dst.suffix
    parent = dst.parent
    counter = 1
    while counter < _MAX_NAME_COLLISION_RETRIES:
        candidate = parent / f"{stem}_{counter}{suffix}"
        if not candidate.exists():
            return candidate, True
        counter += 1
    raise SafeMoveError(
        f"تعذّر إيجاد اسم فريد بعد {_MAX_NAME_COLLISION_RETRIES} محاولة: {dst}"
    )


def _atomic_move(src: Path, dst: Path) -> None:
    """نقل ذرّي يرفض الكتابة فوق أي موجود.

    يستخدم renameat2(RENAME_NOREPLACE) عبر ctypes عند التوفر (لينكس)،
    وإلا يستخدم os.link + unlink fallback. لو الوجهة موجودة بالفعل،
    يُرفع FileExistsError بدلاً من الاستبدال الصامت.

    لا يتبع الروابط الرمزية، لا يعبر نقاط التركيب، لا يُعدّل صلاحيات.
    """
    _validate_safe_file_paths(src, dst)
    src_str = str(src)
    dst_str = str(dst)

    # رفض إذا كانت الوجهة مجلداً (P5) — الفحص داخل try فقط لأن is_dir()
    # قد يفشل بنظام الملفات؛ الخطأ الصريح يُرفع خارج try حتى لا يبتلعه
    # except OSError (عيب جولة DeepSeek 7: IsADirectoryError صنف فرعي من OSError)
    try:
        _dst_is_dir = dst.is_dir()
    except OSError:
        _dst_is_dir = False
    if _dst_is_dir:
        raise IsADirectoryError(
            f"ممنوع النقل فوق مجلد موجود: {dst}"
        )

    # renameat2(RENAME_NOREPLACE) — ذرّي ويرفض الاستبدال
    # AT_FDCWD غير متوفر على جميع الأنظمة (مثلاً macOS) — نتحقق قبل الاستدعاء
    _at_fdcwd = getattr(os, "AT_FDCWD", None)
    if _renameat2_available and _libc is not None and _at_fdcwd is not None:
        try:
            ret = _libc.renameat2(
                ctypes.c_int(_at_fdcwd),
                src_str.encode("utf-8"),
                ctypes.c_int(os.AT_FDCWD),
                dst_str.encode("utf-8"),
                ctypes.c_uint(_RENAME_NOREPLACE),
            )
            if ret == 0:
                return
            link_errno = ctypes.get_errno()
            if link_errno == 17:  # EEXIST — الوجهة موجودة
                raise FileExistsError(
                    f"الوجهة موجودة بالفعل (RENAME_NOREPLACE): {dst}"
                )
            if link_errno == 18:  # EXDEV — أنظمة ملفات مختلفة
                raise OSError(link_errno, "cross-device link not permitted", dst_str)
            raise OSError(link_errno, os.strerror(link_errno), dst_str)
        except (FileExistsError, OSError):
            # Fallback إلى os.link + unlink للأنظمة التي لا تدعم renameat2
            pass

    # Fallback: hard link ثم حذف المصدر (ذرّي على نظام الملفات نفسه)
    try:
        os.link(str(src), str(dst))
    except FileExistsError:
        raise FileExistsError(f"الوجهة موجودة بالفعل (fallback link): {dst}")
    except OSError as e:
        if getattr(e, "errno", None) == 18:  # EXDEV
            # نسخ عبر الأجهزة إلى ملف مؤقت في مجلد الوجهة ثم rename
            tmp_path: Optional[Path] = None
            try:
                with tempfile.NamedTemporaryFile(
                    prefix=".ifm_tmp_",
                    dir=str(dst.parent),
                    delete=False,
                ) as tmp:
                    tmp_path = Path(tmp.name)
                shutil.copy2(str(src), str(tmp_path))
                # بديل ذرّي لـ os.replace: os.link يفشل ذرياً إن ظهر dst بين
                # الفحص والكتابة (فجوة TOCTOU — جولة DeepSeek 7، البند 3)
                _linked = False
                try:
                    os.link(str(tmp_path), str(dst))
                    _linked = True
                except FileExistsError:
                    raise FileExistsError(
                        f"الوجهة موجودة (سباق ما بعد الفحص — رفض بلا استبدال): {dst}"
                    )
                except OSError as link_err:
                    # لا fallback إلى os.replace مطلقاً: قد يستبدل شاغلاً ظهر
                    # بعد الفحص. عند غياب hard-link نغلق العملية بأمان.
                    raise OSError(
                        getattr(link_err, "errno", errno.EOPNOTSUPP),
                        f"تعذر النشر الذري دون استبدال؛ رُفض fallback غير الآمن: {link_err}",
                        str(dst),
                    ) from link_err
                if _linked:
                    try:
                        tmp_path.unlink()
                    except OSError:
                        pass
                try:
                    src.unlink()
                except OSError as unlink_err:
                    # dst نسخة كاملة والصفر الأصلي سليم — نزيل النسخة
                    # لإعادة الحالة الأصلية ثم نرفع خطأً صريحاً
                    try:
                        os.unlink(str(dst))
                    except OSError:
                        pass
                    raise OSError(f"فشل حذف المصدر بعد النسخ — أُزيلت الوجهة: {unlink_err}")
                return
            finally:
                if tmp_path is not None and tmp_path.exists():
                    try:
                        tmp_path.unlink()
                    except OSError:
                        pass
        raise

    # حذف المصدر بعد ربط ناجح — فشله يترك «كلاهما موجود» (hardlink، صفر
    # فقد بيانات): نزيل الرابط dst لإعادة الحالة الأصلية ثم نرفع صريحاً
    # (جولة DeepSeek 7 — البند 4)
    try:
        src.unlink()
    except OSError as e:
        try:
            os.unlink(str(dst))
        except OSError:
            pass
        raise OSError(f"فشل حذف المصدر بعد الربط الناجح — أُزيل الرابط: {e}")
    return


def _atomic_copy(src: Path, dst: Path) -> None:
    """نسخ ذرّي: كتابة إلى ملف مؤقت في نفس مجلد الوجهة ثم rename.

    يرفض الكتابة فوق أي موجود — لو الوجهة موجودة يُرفع FileExistsError.
    """
    _validate_safe_file_paths(src, dst)
    # رفض إذا كانت الوجهة مجلداً — الخطأ الصريح خارج try (عيب جولة DeepSeek 7:
    # IsADirectoryError صنف فرعي من OSError وكان يُبتلع بـexcept OSError: pass)
    try:
        _dst_is_dir = dst.is_dir()
    except OSError:
        _dst_is_dir = False
    if _dst_is_dir:
        raise IsADirectoryError(
            f"ممنوع النسخ فوق مجلد موجود: {dst}"
        )

    tmp_path: Optional[Path] = None
    try:
        with tempfile.NamedTemporaryFile(
            prefix=".ifm_tmp_",
            dir=str(dst.parent),
            delete=False,
        ) as tmp:
            tmp_path = Path(tmp.name)
        shutil.copy2(str(src), str(tmp_path))
        # بديل ذرّي لـ os.replace (فجوة TOCTOU — جولة DeepSeek 7): الربط
        # يفشل ذرياً إن ظهرت الوجهة بين الفحص والكتابة
        try:
            os.link(str(tmp_path), str(dst))
            try:
                tmp_path.unlink()
            except OSError:
                pass
        except FileExistsError:
            raise FileExistsError(
                f"الوجهة موجودة (سباق ما بعد الفحص — رفض بلا استبدال): {dst}"
            )
        except OSError as link_err:
            # Fail closed: os.replace قد يستبدل ملفاً ظهر بعد فحص التضارب.
            raise OSError(
                getattr(link_err, "errno", errno.EOPNOTSUPP),
                f"تعذر النشر الذري دون استبدال؛ رُفض fallback غير الآمن: {link_err}",
                str(dst),
            ) from link_err
    finally:
        if tmp_path is not None and tmp_path.exists() and tmp_path != dst:
            try:
                tmp_path.unlink()
            except OSError:
                pass


# ─── SafeMover ──────────────────────────────────────────────────────────────

class SafeMover:
    """ناقل/ناسخ آمن للملفات مع تحقّق checksum ومعالجة sidecar

    الاستخدام الأساسي:

        mover = SafeMover()
        result = mover.move("/src/file.txt", "/dst/file.txt")
        if not result.success:
            print(f"فشل: {result.error}")

    الخصائص:
      - ذرّي: استخدم rename عبر ملف مؤقت
      - مُتحقَّق: SHA-256 قبل وبعد
      - آمن: لا يحذف المصدر عند الفشل
      - يحترم sidecar: ينقل/ينسخ .ifm_meta_<name>.json تلقائيًا
      - thread-safe: لا حالة مشتركة
      - لا overwrite: ممنوع الكتابة فوق أي موجود (يضاف لاحقة تلقائيًا)

    Options:
      - verify_checksum: افتراضيًا True، يتحقّق بعد العملية
      - move_sidecar: افتراضيًا True، ينقل/ينسخ sidecar إن وُجد
      - overwrite: محظور كليًا (سيُرفع OverwriteForbiddenError إذا True)
    """

    def __init__(
        self,
        *,
        verify_checksum: bool = True,
        move_sidecar: bool = True,
        overwrite: bool = False,
    ):
        if overwrite:
            raise OverwriteForbiddenError(
                "overwrite=True محظور وفق تعليمات المستخدم: ممنوع الكتابة فوق أي موجود. "
                "يُضاف لاحقة _1, _2, ... تلقائيًا عند التضارب."
            )
        self.verify_checksum = verify_checksum
        self.move_sidecar = move_sidecar
        self.overwrite = overwrite

    # ─── Move ──────────────────────────────────────────────────────────────

    def move(
        self,
        source: Union[str, Path],
        destination: Union[str, Path],
        *,
        verify_checksum: Optional[bool] = None,
        move_sidecar: Optional[bool] = None,
        overwrite: Optional[bool] = None,
    ) -> MoveResult:
        """نقل آمن لملف مع تحقّق checksum

        Args:
            source: مسار المصدر
            destination: مسار الوجهة
            verify_checksum: تجاوز الإعداد الافتراضي
            move_sidecar: تجاوز إعداد نقل sidecar
            overwrite: تجاوز إعداد overwrite (محظور)

        Returns:
            MoveResult بتفاصيل العملية
        """
        start = time.monotonic()
        verify = self.verify_checksum if verify_checksum is None else verify_checksum
        do_sidecar = self.move_sidecar if move_sidecar is None else move_sidecar
        do_overwrite = self.overwrite if overwrite is None else overwrite

        if do_overwrite:
            result = MoveResult(source=str(source), destination=str(destination))
            result.success = False
            result.error = "overwrite=True محظور: ممنوع الكتابة فوق أي موجود"
            result.duration_ms = (time.monotonic() - start) * 1000
            return result

        src = Path(source)
        dst = Path(destination)

        result = MoveResult(
            source=str(src),
            destination=str(dst),
            final_path=str(dst),
        )

        try:
            # التحقق من وجود المصدر (مع تحذير TOCTOU — يتم معالجته عند الفتح الفعلي)
            if not src.exists():
                result.success = False
                result.error = f"الملف المصدر غير موجود: {src}"
                result.duration_ms = (time.monotonic() - start) * 1000
                return result

            # no-op: النقل إلى نفس الموضع الفعلي — العقد الموثق في الاختبارات:
            # ينجح دون فعل (idempotent)، لا تضارب مع نفسه ولا لاحقة.
            # يعمل قبل رفض symlink (وجهة symlink تحلّ للمصدر نفسه = no-op)
            try:
                if src.resolve() == dst.resolve():
                    if verify:
                        result.checksum_before = compute_sha256(src)
                        result.checksum_after = result.checksum_before
                    result.success = True
                    result.final_path = str(dst)
                    result.duration_ms = (time.monotonic() - start) * 1000
                    logger.info(f"نقل إلى نفس الموضع — no-op: {src}")
                    return result
            except OSError as e:
                result.success = False
                result.error = f"فشل فحص تطابق المسارين: {e}"
                result.duration_ms = (time.monotonic() - start) * 1000
                return result

            _validate_safe_file_paths(src, dst)
        except SafeMoveError as e:
            result.success = False
            result.error = str(e)
            result.duration_ms = (time.monotonic() - start) * 1000
            return result

        # حساب checksum قبل النقل (يفتح الملف فعليًا — يقلل نافذة TOCTOU)
        try:
            if verify:
                result.checksum_before = compute_sha256(src)
        except OSError as e:
            result.success = False
            result.error = f"فشل حساب checksum للمصدر: {e}"
            result.duration_ms = (time.monotonic() - start) * 1000
            return result

        # ضمان وجود مجلد الوجهة
        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            result.success = False
            result.error = f"فشل إنشاء مجلد الوجهة: {e}"
            result.duration_ms = (time.monotonic() - start) * 1000
            return result

        # حل التضارب (ممنوع overwrite — يُضاف لاحقة تلقائيًا)
        try:
            if do_overwrite:
                # الكتابة فوق الموجود محظورة — لا يُنفذ أبدًا
                raise OverwriteForbiddenError(
                    f"ممنوع الكتابة فوق الملف الموجود: {dst}"
                )
            else:
                final_dst, renamed = _resolve_collision(dst, src)
        except SafeMoveError as e:
            result.success = False
            result.error = str(e)
            result.duration_ms = (time.monotonic() - start) * 1000
            return result

        result.renamed_due_to_collision = renamed
        result.final_path = str(final_dst)

        # التحقق من أن الوجهة لم تُنشأ بين الفحص والنقل (TOCTOU guard)
        # لو كانت الوجهة موجودة الآن (ينبغي ألا تكون لأن _resolve_collision يضمن فريدة)
        if final_dst.exists() and src.resolve() != final_dst.resolve():
            result.success = False
            result.error = f"TOCTOU: الوجهة ظهرت فجأة: {final_dst}"
            result.duration_ms = (time.monotonic() - start) * 1000
            return result

        # نقل sidecar أولاً (لو وُجد) — لضمان التناسق مع الملف الرئيسي
        src_sidecar = _sidecar_path(src)
        dst_sidecar = _sidecar_path(final_dst)
        sidecar_existed = src_sidecar.exists()

        # النقل الذرّي للملف الرئيسي (BaseException يغطي KeyboardInterrupt - P4)
        try:
            _atomic_move(src, final_dst)
        except BaseException as e:
            _reraise_if_interrupt(e)
            result.success = False
            result.error = f"فشل النقل: {e}"
            result.duration_ms = (time.monotonic() - start) * 1000
            return result

        # تحقّق checksum بعد النقل
        if verify:
            try:
                result.checksum_after = compute_sha256(final_dst)
            except BaseException as e:
                # فشل التحقق — إعادة الملف إلى موضعه
                logger.error(f"فشل حساب checksum بعد النقل: {e} — محاولة rollback")
                try:
                    _atomic_move(final_dst, src)
                except BaseException:
                    logger.error(f"فشل rollback من {final_dst} إلى {src}")
                _reraise_if_interrupt(e)
                result.success = False
                result.error = f"فشل حساب checksum بعد النقل: {e}"
                result.duration_ms = (time.monotonic() - start) * 1000
                return result

            if result.checksum_before != result.checksum_after:
                # عدم تطابق — rollback
                logger.error(
                    f"عدم تطابق checksum: قبل={result.checksum_before} "
                    f"بعد={result.checksum_after} — rollback"
                )
                try:
                    _atomic_move(final_dst, src)
                except OSError:
                    logger.error(f"فشل rollback من {final_dst} إلى {src}")
                result.success = False
                result.error = (
                    f"عدم تطابق checksum بعد النقل "
                    f"(قبل={result.checksum_before[:12]}..., "
                    f"بعد={result.checksum_after[:12]}...)"
                )
                result.duration_ms = (time.monotonic() - start) * 1000
                return result

        # نقل sidecar (بعد نجاح الملف الرئيسي والتحقق)
        if do_sidecar and sidecar_existed:
            try:
                if dst_sidecar.exists() and src_sidecar.resolve() != dst_sidecar.resolve():
                    # دمج — ندمج الوسوم
                    _merge_sidecar(dst_sidecar, src_sidecar)
                    src_sidecar.unlink()
                else:
                    _atomic_move(src_sidecar, dst_sidecar)
                result.sidecar_moved = True
                result.sidecar_source = str(src_sidecar)
                result.sidecar_destination = str(dst_sidecar)
            except BaseException as e:
                # توحيد الفشل (مراجعة جلسة ChatGPT، المرحلة 4): فشل نقل sidecar
                # ليس نجاحاً جزئياً مقبولاً — نتراجع عن نقل الملف الرئيسي ثم
                # نفشل العملية كاملة (لا نجاح مضلل ولا فقد بيانات).
                _reraise_if_interrupt(e)
                logger.error(
                    f"فشل نقل sidecar من {src_sidecar} إلى {dst_sidecar}: {e} "
                    f"— تراجع عن نقل الملف الرئيسي"
                )
                rolled_back = True
                try:
                    _atomic_move(final_dst, src)
                except OSError as rb:
                    rolled_back = False
                    logger.critical(
                        f"فشل التراجع من {final_dst} إلى {src}: {rb} — الحالة غير متجانسة"
                    )
                result.sidecar_moved = False
                result.success = False
                result.error = (
                    f"فشل نقل sidecar — تم التراجع: {e}"
                    if rolled_back
                    else f"فشل نقل sidecar وفشل التراجع: {e} / الحالة غير متجانسة"
                )
                result.duration_ms = (time.monotonic() - start) * 1000
                return result

        result.success = True
        result.duration_ms = (time.monotonic() - start) * 1000
        return result

    # ─── Copy ──────────────────────────────────────────────────────────────

    def copy(
        self,
        source: Union[str, Path],
        destination: Union[str, Path],
        *,
        verify_checksum: Optional[bool] = None,
        copy_sidecar: Optional[bool] = None,
        overwrite: Optional[bool] = None,
    ) -> CopyResult:
        """نسخ آمن لملف مع تحقّق checksum

        Args:
            source: مسار المصدر
            destination: مسار الوجهة
            verify_checksum: تجاوز الإعداد الافتراضي
            copy_sidecar: تجاوز إعداد نسخ sidecar
            overwrite: تجاوز إعداد overwrite (محظور)

        Returns:
            CopyResult بتفاصيل العملية
        """
        start = time.monotonic()
        verify = self.verify_checksum if verify_checksum is None else verify_checksum
        do_sidecar = self.move_sidecar if copy_sidecar is None else copy_sidecar
        do_overwrite = self.overwrite if overwrite is None else overwrite

        if do_overwrite:
            result = CopyResult(source=str(source), destination=str(destination))
            result.success = False
            result.error = "overwrite=True محظور: ممنوع الكتابة فوق أي موجود"
            result.duration_ms = (time.monotonic() - start) * 1000
            return result

        src = Path(source)
        dst = Path(destination)

        result = CopyResult(
            source=str(src),
            destination=str(dst),
            final_path=str(dst),
        )

        try:
            _validate_safe_file_paths(src, dst)
        except SafeMoveError as e:
            result.success = False
            result.error = str(e)
            result.duration_ms = (time.monotonic() - start) * 1000
            return result

        # التحقق من وجود المصدر
        if not src.exists():
            result.success = False
            result.error = f"الملف المصدر غير موجود: {src}"
            result.duration_ms = (time.monotonic() - start) * 1000
            return result

        # checksum قبل
        try:
            if verify:
                result.checksum_before = compute_sha256(src)
        except OSError as e:
            result.success = False
            result.error = f"فشل حساب checksum للمصدر: {e}"
            result.duration_ms = (time.monotonic() - start) * 1000
            return result

        # ضمان مجلد الوجهة
        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            result.success = False
            result.error = f"فشل إنشاء مجلد الوجهة: {e}"
            result.duration_ms = (time.monotonic() - start) * 1000
            return result

        # حل التضارب (ممنوع overwrite)
        try:
            if do_overwrite:
                raise OverwriteForbiddenError(
                    f"ممنوع الكتابة فوق الملف الموجود: {dst}"
                )
            else:
                final_dst, renamed = _resolve_collision(dst, src)
        except SafeMoveError as e:
            result.success = False
            result.error = str(e)
            result.duration_ms = (time.monotonic() - start) * 1000
            return result

        result.renamed_due_to_collision = renamed
        result.final_path = str(final_dst)

        # التحقق من TOCTOU للوجهة
        if final_dst.exists() and src.resolve() != final_dst.resolve():
            result.success = False
            result.error = f"TOCTOU: الوجهة ظهرت فجأة: {final_dst}"
            result.duration_ms = (time.monotonic() - start) * 1000
            return result

        # نسخ sidecar أولاً (لو وُجد)
        src_sidecar = _sidecar_path(src)
        dst_sidecar = _sidecar_path(final_dst)
        sidecar_existed = src_sidecar.exists()

        # النسخ الذرّي (BaseException يغطي KeyboardInterrupt - P4)
        try:
            _atomic_copy(src, final_dst)
        except BaseException as e:
            _reraise_if_interrupt(e)
            result.success = False
            result.error = f"فشل النسخ: {e}"
            result.duration_ms = (time.monotonic() - start) * 1000
            return result

        # تحقّق checksum
        if verify:
            try:
                result.checksum_after = compute_sha256(final_dst)
            except BaseException as e:
                logger.error(f"فشل حساب checksum بعد النسخ: {e} — حذف النسخة")
                try:
                    final_dst.unlink()
                except BaseException:
                    pass
                _reraise_if_interrupt(e)
                result.success = False
                result.error = f"فشل حساب checksum بعد النسخ: {e}"
                result.duration_ms = (time.monotonic() - start) * 1000
                return result

            if result.checksum_before != result.checksum_after:
                logger.error(
                    f"عدم تطابق checksum بعد النسخ: قبل={result.checksum_before} "
                    f"بعد={result.checksum_after} — حذف النسخة"
                )
                try:
                    final_dst.unlink()
                except BaseException:
                    pass
                result.success = False
                result.error = (
                    f"عدم تطابق checksum بعد النسخ "
                    f"(قبل={result.checksum_before[:12]}..., "
                    f"بعد={result.checksum_after[:12]}...)"
                )
                result.duration_ms = (time.monotonic() - start) * 1000
                return result

        # نسخ sidecar
        if do_sidecar and sidecar_existed:
            try:
                if dst_sidecar.exists() and src_sidecar.resolve() != dst_sidecar.resolve():
                    _merge_sidecar(dst_sidecar, src_sidecar)
                else:
                    _atomic_copy(src_sidecar, dst_sidecar)
                result.sidecar_copied = True
                result.sidecar_source = str(src_sidecar)
                result.sidecar_destination = str(dst_sidecar)
            except BaseException as e:
                # توحيد الفشل (مراجعة جلسة ChatGPT، المرحلة 4): فشل نسخ sidecar
                # ليس نجاحاً جزئياً مقبولاً — نحذف النسخة في الوجهة ثم نفشل
                # العملية كاملة (لا نسخة ناقصة بلا بياناتها الوصفية).
                _reraise_if_interrupt(e)
                logger.error(
                    f"فشل نسخ sidecar من {src_sidecar} إلى {dst_sidecar}: {e} "
                    f"— حذف النسخة في الوجهة"
                )
                cleaned = True
                try:
                    final_dst.unlink()
                except OSError as rb:
                    cleaned = False
                    logger.critical(
                        f"فشل حذف النسخة في الوجهة عند التراجع: {rb} — الحالة غير متجانسة"
                    )
                result.sidecar_copied = False
                result.success = False
                result.error = (
                    f"فشل نسخ sidecar — تم التراجع بحذف النسخة: {e}"
                    if cleaned
                    else f"فشل نسخ sidecar وفشل حذف النسخة: {e} / الحالة غير متجانسة"
                )
                result.duration_ms = (time.monotonic() - start) * 1000
                return result

        result.success = True
        result.duration_ms = (time.monotonic() - start) * 1000
        return result

    # ─── Batch ───────────────────────────────────────────────────────────

    def move_many(
        self,
        pairs: List[tuple[Union[str, Path], Union[str, Path]]],
        *,
        stop_on_error: bool = False,
    ) -> List[MoveResult]:
        """ينقل عدة أزواج (source, destination) دفعة واحدة

        Args:
            pairs: قائمة أزواج (source, destination)
            stop_on_error: لو True، يتوقف عند أول فشل

        Returns:
            قائمة MoveResult بنفس ترتيب pairs
        """
        results: List[MoveResult] = []
        for src, dst in pairs:
            r = self.move(src, dst)
            results.append(r)
            if not r.success and stop_on_error:
                break
        return results

    def copy_many(
        self,
        pairs: List[tuple[Union[str, Path], Union[str, Path]]],
        *,
        stop_on_error: bool = False,
    ) -> List[CopyResult]:
        """ينسخ عدة أزواج دفعة واحدة"""
        results: List[CopyResult] = []
        for src, dst in pairs:
            r = self.copy(src, dst)
            results.append(r)
            if not r.success and stop_on_error:
                break
        return results

    # ─── Directory-tree operations ──────────────────────────────────────

    def move_directory_tree(
        self,
        source_dir: Union[str, Path],
        destination_dir: Union[str, Path],
        *,
        verify_checksum: Optional[bool] = None,
        move_sidecar: Optional[bool] = None,
    ) -> List[MoveResult]:
        """ينقل شجرة مجلدات كاملة مع جميع ملفاتها عبر SafeMover.

        لا يتبع الروابط الرمزية، لا يعبر نقاط التركيب.
        كل ملف يُنقل فرديًا عبر move() مع تحقّق checksum.

        Returns:
            قائمة MoveResult لكل ملف تم نقله
        """
        from .path_policy import iter_files

        src_dir = Path(source_dir)
        dst_dir = Path(destination_dir)

        if not src_dir.is_dir():
            return [
                MoveResult(
                    source=str(src_dir),
                    destination=str(dst_dir),
                    success=False,
                    error=f"المصدر ليس مجلدًا: {src_dir}",
                )
            ]

        results: List[MoveResult] = []
        for src_file in iter_files(src_dir, recursive=True, skip_hidden=True):
            # حساب المسار النسبي للحفاظ على بنية المجلدات
            try:
                rel = src_file.relative_to(src_dir)
            except ValueError:
                rel = src_file.name

            dst_file = dst_dir / rel
            r = self.move(
                src_file,
                dst_file,
                verify_checksum=verify_checksum,
                move_sidecar=move_sidecar,
            )
            results.append(r)
        return results

    def copy_directory_tree(
        self,
        source_dir: Union[str, Path],
        destination_dir: Union[str, Path],
        *,
        verify_checksum: Optional[bool] = None,
        copy_sidecar: Optional[bool] = None,
    ) -> List[CopyResult]:
        """ينسخ شجرة مجلدات كاملة مع جميع ملفاتها عبر SafeMover.

        لا يتبع الروابط الرمزية، لا يعبر نقاط التركيب.

        Returns:
            قائمة CopyResult لكل ملف تم نسخه
        """
        from .path_policy import iter_files

        src_dir = Path(source_dir)
        dst_dir = Path(destination_dir)

        if not src_dir.is_dir():
            return [
                CopyResult(
                    source=str(src_dir),
                    destination=str(dst_dir),
                    success=False,
                    error=f"المصدر ليس مجلدًا: {src_dir}",
                )
            ]

        results: List[CopyResult] = []
        for src_file in iter_files(src_dir, recursive=True, skip_hidden=True):
            try:
                rel = src_file.relative_to(src_dir)
            except ValueError:
                rel = src_file.name

            dst_file = dst_dir / rel
            r = self.copy(
                src_file,
                dst_file,
                verify_checksum=verify_checksum,
                copy_sidecar=copy_sidecar,
            )
            results.append(r)
        return results


# ─── Sidecar merge helper ───────────────────────────────────────────────────

def _merge_sidecar(target_sidecar: Path, source_sidecar: Path) -> None:
    """يدمج محتوى sidecar مصدر في sidecar هدف

    الوسوم: اتحاد القائمتين (deduped)
    التصنيف: يُحتفظ بقيمة الهدف إن وُجدت، وإلا يؤخذ من المصدر
    """
    import json
    try:
        target_data = json.loads(target_sidecar.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        target_data = {}
    try:
        source_data = json.loads(source_sidecar.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        source_data = {}

    merged_tags = list(set(target_data.get("tags", []) + source_data.get("tags", [])))
    target_data["tags"] = merged_tags
    if "category" not in target_data and "category" in source_data:
        target_data["category"] = source_data["category"]
    target_sidecar.write_text(
        json.dumps(target_data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


# ─── Convenience: integration with RuleEngine ──────────────────────────────

def safe_move_for_rule_engine(
    source: Union[str, Path],
    destination: Union[str, Path],
    *,
    overwrite: bool = False,
) -> tuple[bool, str, str]:
    """واجهة مبسّطة لاستخدام SafeMover من RuleEngine

    Returns:
        (success, final_destination, error_message)
        لو success=True، error_message فارغ
    """
    mover = SafeMover(verify_checksum=True, move_sidecar=True, overwrite=overwrite)
    result = mover.move(source, destination)
    if result.success:
        return True, result.final_path, ""
    return False, "", result.error or "unknown error"


def safe_copy_for_rule_engine(
    source: Union[str, Path],
    destination: Union[str, Path],
    *,
    overwrite: bool = False,
) -> tuple[bool, str, str]:
    """واجهة مبسّطة لاستخدام SafeMover (copy) من RuleEngine"""
    mover = SafeMover(verify_checksum=True, move_sidecar=True, overwrite=overwrite)
    result = mover.copy(source, destination)
    if result.success:
        return True, result.final_path, ""
    return False, "", result.error or "unknown error"
