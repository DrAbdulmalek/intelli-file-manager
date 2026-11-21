"""حسّاس-بارير — حاجز حماية الملفات الحساسة قبل القراءة/OCR/الإرسال الخارجي

هذه الوحدة تمنع فتح محتوى أي ملف يُصنّف على أنه "حساس" قبل أي عملية
قراءة أو استخراج نص أو OCR أو إرسال إلى خدمة خارجية.

مستويات الكشف الثلاثة (انظر docs/SENSITIVE_BARRIER.md):
  1. Path/name-based detection  — الاسم والمسار فقط، لا يفتح الملف إطلاقاً.
  2. Header-based detection     — يفتح الملف ويقرأ 4 بايتات فقط عند الإزاحة 128
     للتحقق من دليمة DICOM (حتى لو كان الامتداد مضللاً مثل .pdf). هذا *قراءة
     محتوى محدودة وموثّقة* — لا تُصنّف الوحدة على أنها "لا تقرأ المحتوى".
  3. Full content inspection    — مستوى لا يفعله الحاجز أبداً؛ يُمنع على
     الملفات الحساسة (فهرسة/تصنيف/OCR/إرسال خارجي).

قواعد الحساسية إلزامية (MANDATORY):
  - لا يمكن لأي إعداد مستخدم (skip_dirs أو غيره) تعطيلها.
  - المعامل skip_dirs محفوظ للتوافق التوقيعي فقط ويُتجاهل هنا؛ استخدامه
    الوحيد المشروع هو تقليم المسح في path_policy.iter_files قبل الوصول
    إلى القارئات.

سياسة الروابط الرمزية (symlinks):
  - الـ lstat لا يتبع الروابط: إن كان المسار نفسه رابطاً رمزياً يُصنّف
    كلٌّ من مسار الرابط وهدفه النهائي (readlink + realpath) — إن كان أي
    منهما حساساً فالملف حساس. لا يُقرأ محتوى الهدف.
  - open_checked() يفتح بـ O_NOFOLLOW (على POSIX) لمنع بدل الرابط بعد
    الفحص، ثم يتحقق عبر fstat أن المفتوح ملف عادي.

حدود الحماية من TOCTOU (موثّقة، لا تُخفى):
  - O_NOFOLLOW يمنع بدل المكوّن الأخير برابط رمزي بين الفحص والفتح.
  - تبديل ملف عادي بآخر عادي (نفس الاسم) بعد الفحص وقبل القراءة يبقى
    نافذة سباق ضيقة لا يغلقها أي فحص مساري؛ القراءات الحرجة تعيد التحقق
    من الهوية (st_dev/st_ino) عبر verify_open_identity() بعد الفتح.
  - بدل مجلد أب (rename) خارج نطاق هذه الوحدة — انظر docs/SENSITIVE_BARRIER.md.
"""
from __future__ import annotations

import logging
import os
import stat
import re
from pathlib import Path
from typing import Iterable, Optional, Union

logger = logging.getLogger(__name__)

PathLike = Union[str, Path]

# دليمة DICOM عند الإزاحة 128 (البايتات 128-131) وفق معيار DICOM
_DICOM_MAGIC = b"DICM"
_DICOM_MAGIC_OFFSET = 128
_DICOM_MAGIC_LEN = 4


# ─── امتدادات الملفات الطبية الحساسة ────────────────────────────────────────

# DICOM وصيغ التصوير الطبي الشائعة
MEDICAL_IMAGING_EXTENSIONS = frozenset(
    {
        ".dcm",
        ".dicom",
        ".dicm",
        ".nifti",
        ".nii",
        ".nii.gz",
        ".mha",
        ".mhd",
        ".nrrd",
        ".nhdr",
    }
)

# امتدادات تقارير المرضى والوثائق الطبية
MEDICAL_REPORT_EXTENSIONS = frozenset(
    {
        ".pdf",   # قد تحتوي على تقارير طبية — تُفحص حسب المسار
        ".docx",
        ".doc",
        ".rtf",
        ".txt",   # قد تحتوي على ملاحظات طبية — تُفحص حسب المسار
    }
)

# امتدادات الصور التي قد تكون صورًا طبية (تُفحص حسب المسار)
MEDICAL_IMAGE_EXTENSIONS = frozenset(
    {
        ".jpg",
        ".jpeg",
        ".png",
        ".tiff",
        ".tif",
        ".bmp",
        ".webp",
    }
)

# جميع امتدادات الحساسية (تُدمج مع فحص المسار)
ALL_SENSITIVE_EXTENSIONS = (
    MEDICAL_IMAGING_EXTENSIONS
    | MEDICAL_REPORT_EXTENSIONS
    | MEDICAL_IMAGE_EXTENSIONS
)

# ─── ملفات الأسرار والاعتماديات (قواعد إلزامية لا تُعطَّل) ───────────────────

# أسماء ملفات تُحظر بالاسم الصارم (case-insensitive)
SECRET_NAME_EXACT = frozenset(
    {
        ".env",
        ".env.local",
        ".env.production",
        ".netrc",
        ".htpasswd",
        ".git-credentials",
        ".npmrc",
        ".pypirc",
        "credentials.json",
        "credentials.yaml",
        "credentials.yml",
        "secrets.json",
        "secrets.yaml",
        "secrets.yml",
        "id_rsa",
        "id_dsa",
        "id_ecdsa",
        "id_ed25519",
        "id_ed448",
        "identity",
        "wallet.dat",
        "authorized_keys",
    }
)

# امتدادات مفاتيح/شهادات/حاويات اعتماديات
SECRET_EXTENSIONS = frozenset(
    {
        ".pem",
        ".p12",
        ".pfx",
        ".p7b",
        ".p7c",
        ".key",
        ".ppk",
        ".jks",
        ".keystore",
        ".kdb",
        ".kdbx",
        ".gpg",
        ".asc",
        ".crt",
        ".cer",
        ".der",
        ".crl",
        ".pub",  # ملاحظة: المفاتيح العامة تُحظر أيضًا احترازيًا — العائلة كلها
    }
)

# ─── مؤشرات المسارات الحساسة ────────────────────────────────────────────────

# أجزاء المسار التي تشير إلى مجلدات طبية أو حساسة
SENSITIVE_PATH_PARTS = frozenset(
    {
        # مجلدات طبية
        "mri",
        "dicom",
        "medical",
        "patient",
        "patients",  # الجمع الشائع — إغلاق جولة 12: كان يمرّ بالمسار exact
        "medical_records",
        "hospital_records",
        "clinical",
        "radiology",
        "prescriptions",
        "laboratory",
        "lab_results",
        "مرضى",
        "المرضى",  # صيغة التعريف — نفس الإغلاق
        "مريض",
        "سجل طبي",
        "سجلات طبية",
        "تقرير طبي",
        "تقرير_طبي",
        "أشعة",
        "وصفة",
        "وصفات",
        "تحاليل",
        "مختبر",
        "clinics",
        "clinic",
        "hospital",
        "hospitals",
        "مستشفى",
        "عيادة",
        # مجلدات نظام حساسة
        ".ssh",
        ".config",
        ".gnupg",
        ".gnupg2",
        ".pki",
        ".certs",
        ".aws",
        ".azure",
        ".gcloud",
        ".kube",
        ".docker",
        # معلومات اعتماد
        "secrets",
        "credentials",
        "keys",
        "تسجيلات دخول",
    }
)

# أجزاء اسم الملف التي تشير إلى محتوى طبي أو حساس
SENSITIVE_FILENAME_PARTS = frozenset(
    {
        "mri",
        "dicom",
        "ct_scan",
        "ct_scan_",
        "scan",
        "scan_",
        "xray",
        "x_ray",
        "ultrasound",
        "patient",
        "medical_records",
        "hospital_records",
        "clinical",
        "radiology",
        "prescription",
        "prescriptions",
        "laboratory",
        "lab_result",
        "مرضى",
        "تقرير طبي",
        "تقرير_طبي",
        "ملف مريض",
        "ملف_مريض",
        "chest",
        "صدر",
        "brain",
        "دماغ",
        "spine",
        "عمود",
        # أسماء اعتماديات بالاسم (word-boundary؛ لا يلتقط "secretary")
        "credentials",
        "credential",
        "secret",
        "secrets",
        "password",
        "passwd",
        "private_key",
        "apikey",
        "api_key",
        "access_token",
    }
)


CREDENTIAL_WORD_PARTS = frozenset(
    {"credentials", "credential", "secret", "secrets", "password", "passwd",
     "private_key", "apikey", "api_key", "access_token"}
)

# ─── استثناءات ───────────────────────────────────────────────────────────────


class SensitiveFileBlockedError(Exception):
    """يُرفع عند محاولة قراءة ملف محمي بواسطة الحسّاس-بارير."""


class SymlinkBlockedError(SensitiveFileBlockedError):
    """يُرفع عندما يشترط السياق ملفاً حقيقياً ويُقدَّم رابط رمزي."""


# ─── دوال الكشف ───────────────────────────────────────────────────────────────


def _path_parts_lower(path: Path) -> list[str]:
    """تُرجع أجزاء المسار جميعها بأحرف صغيرة للمقارنة."""
    parts: list[str] = []
    p = path
    while True:
        parts.append(p.name.lower())
        parent = p.parent
        if parent == p:
            break
        p = parent
    parts.reverse()
    return parts


def is_sensitive_extension(ext: str) -> bool:
    """هل الامتداد يُصنّف كحساس (طبي أو نظام أو صورة محتملة)."""
    return ext.lower() in ALL_SENSITIVE_EXTENSIONS


def is_medical_imaging_extension(ext: str) -> bool:
    """هل الامتداد هو صيغة تصوير طبي مؤكدة (DICOM، NIfTI، إلخ)."""
    return ext.lower() in MEDICAL_IMAGING_EXTENSIONS


def _readlink_if_symlink(file_path: Path) -> Optional[str]:
    """يُعيد هدف الرابط الرمزي إن كان المسار رابطاً، وإلا None.

    lstat لا يتبع الروابط — قراءة الهدف نصية فقط (لا محتوى).
    """
    try:
        info = os.lstat(os.fspath(file_path))
    except OSError:
        return None
    if stat.S_ISLNK(info.st_mode):
        try:
            return os.readlink(os.fspath(file_path))
        except OSError:
            return ""  # رابط مكسور — يُعامل كرابط بلا هدف
    return None


def _realpath_no_strict(file_path: Path) -> Optional[Path]:
    """realpath بلا استثناءات — لأغراض تصنيف هدف الرابط فقط."""
    try:
        return Path(os.path.realpath(os.fspath(file_path)))
    except OSError:
        return None


SECRET_EXACT_NAMES = frozenset(
    {
        ".env", ".netrc", ".htpasswd", ".pgpass", ".npmrc", ".pypirc",
        ".git-credentials", "authorized_keys", "credentials.json",
        "secrets.json", "wallet.dat",
    }
)

_SECRET_KEY_NAME = re.compile(r"^id_(?:rsa|dsa|ecdsa|ed25519)(?:[_.-][a-z0-9_.-]+)?$")
_ENV_VARIANT = re.compile(r"^\.env\.[a-z0-9_.-]+$")
_ENV_TEMPLATE_SUFFIXES = (".example", ".sample", ".template", ".dist")


def is_secret_file(file_path: Union[str, Path]) -> bool:
    """هل اسم/امتداد الملف يدل على سرّ (مفتاح خاص، بيانات اعتماد، خزنة كلمات مرور)؟

    لا تُقرأ محتويات الملف إطلاقًا. المفتاح العام (``id_rsa.pub``) وقوالب
    ``.env.example`` لا تُعدّ أسرارًا.

    منقولة حرفيًا من مراجعة P0 (فرع fix/p0-review-2026-11-21) لتوحيد الواجهة
    فوق حاجز #74 الحاكم.
    """
    name = Path(file_path).name.lower()
    if name.endswith(".pub") or name.endswith(_ENV_TEMPLATE_SUFFIXES):
        return False
    if name in SECRET_EXACT_NAMES or _SECRET_KEY_NAME.match(name):
        return True
    if _ENV_VARIANT.match(name):
        return True
    return Path(name).suffix in SECRET_EXTENSIONS


def _has_dicom_header(file_path: Path) -> bool:
    """يُعيد True لو كان الملف يبدأ بدليمة DICOM عند الإزاحة 128.

    مستوى كشف Header-based: يفتح الملف بـ O_NOFOLLOW ويقرأ 4 بايتات فقط
    عند الإزاحة 128 — هذا "قراءة محتوى محدودة وموثّقة" وليست قراءة كاملة.
    الروابط الرمزية لا تُتبع هنا (كشف الرابط يُدار في is_sensitive_path).
    """
    path = os.fspath(file_path)
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
    nofollow = getattr(os, "O_NOFOLLOW", None)
    if nofollow is not None:
        flags |= nofollow
    try:
        fd = os.open(path, flags)
    except OSError:
        # رابط رمزي (O_NOFOLLOW) أو تعذّر الفتح → لا كشف header
        return False
    try:
        os.lseek(fd, _DICOM_MAGIC_OFFSET, os.SEEK_SET)
        magic = os.read(fd, _DICOM_MAGIC_LEN)
        return magic == _DICOM_MAGIC
    except OSError:
        return False
    finally:
        os.close(fd)


MEDICAL_IMAGE_EXTENSIONS = frozenset(
    {".jpg", ".jpeg", ".png", ".tiff", ".tif", ".bmp", ".webp"}
)


def _should_probe_dicom(ext: str) -> bool:
    """DICOM بلا امتداد أو متنكّر بصورة عامة؛ لا نفتح غير المرشّحين.

    منقولة من مراجعة P0: الملفات بامتداد غير مرشّح (csv/txt...) لا تُمس
    إطلاقاً — لا مسح ضخم على ملفات عادية."""
    return (
        ext == ""
        or ext.lstrip(".").isdigit()
        or ext in MEDICAL_IMAGE_EXTENSIONS
        or ext == ".pdf"  # حاوية مستندات قد تخفي دليمة (اختبار #74: DICOM خلف invoice.pdf)
        or ext in MEDICAL_IMAGING_EXTENSIONS
    )


def _name_parts_lower(name: str) -> set[str]:
    """يُنفّذ word-boundary splitting على اسم الملف بدون الامتداد.

    يفصل على "_" و "-" و "." ويجمع الأجزاء غير الفارغة بالإضافة إلى الجذر كاملاً.
    """
    stem = Path(name).stem
    parts: set[str] = set()
    for sep in ("_", "-", "."):
        parts.update(part for part in stem.split(sep) if part)
    parts.add(stem)
    return {p.lower() for p in parts if p}


def _classify_by_name_and_path(path: Path) -> bool:
    """الطبقة الأولى (Path/name-based): اسم الملف والمسار فقط — بلا فتح."""
    ext = path.suffix.lower()
    all_suffixes = [s.lower() for s in path.suffixes]
    full_name_lower = path.name.lower()
    parts = _path_parts_lower(path)
    name_no_ext_lower = full_name_lower.rsplit(".", 1)[0] if "." in full_name_lower else full_name_lower

    # استثناءات الدقة (مراجعة P0): قوالب البيئة ومستندات السياسة.
    # المفتاح العام .pub يبقى محجوباً احترازياً (عائلة المفاتيح كلها — قرار #74
    # الموثق في اختباره test_public_key_blocked_too)؛ is_secret_file وحدهما
    # يعدّه "ليس سراً بالاسم" للتمييز الدلالي، والحجب قرار الحاجز.
    is_template = full_name_lower.endswith(_ENV_TEMPLATE_SUFFIXES)
    doc_ext = ext in {".md", ".rst"}

    # 1. امتداد تصوير طبي مؤكد — دائمًا محظور
    if is_medical_imaging_extension(ext) or any(
        s in MEDICAL_IMAGING_EXTENSIONS for s in all_suffixes
    ):
        return True

    # 1ب. امتداد أسرار/مفاتيح/شهادات — دائمًا محظور (المفتاح العام مستثنى)
    if ext in SECRET_EXTENSIONS and not is_template:
        return True

    # 1ج. اسم ملف أسرار بالاسم الصارم (.env، id_rsa، credentials.json...)
    if full_name_lower in SECRET_NAME_EXACT:
        return True

    # 1ج-2. أي ملف ينتهي بـ .env (deep.env، backup.env...) — ملفات بيئة أسرار
    if full_name_lower.endswith(".env"):
        return True

    # 1د. أسماء مفاتيح SSH بنمط شائع (id_rsa.old، id_ed25519@1440223141.tmp…)
    if name_no_ext_lower in SECRET_NAME_EXACT and not is_template:
        return True

    # 1هـ. أنماط مفاتيح SSH المشتقة (id_ed25519_work) وبيئات متغيرة (.env.staging)
    if not is_template and (
        _SECRET_KEY_NAME.match(full_name_lower) or _ENV_VARIANT.match(full_name_lower)
    ):
        return True

    # 2. أي جزء من المسار يشير إلى مجلد طبي/نظام/حساس (إلزامي — لا يتأثر
    #    بأي إعداد مستخدم مثل skip_dirs)
    if set(parts) & SENSITIVE_PATH_PARTS:
        return True

    # 3. أي جزء من اسم الملف يشير إلى محتوى طبي/حساس (word-boundary)
    name_parts = _name_parts_lower(full_name_lower)
    if name_parts & SENSITIVE_FILENAME_PARTS:
        hits = name_parts & SENSITIVE_FILENAME_PARTS
        if doc_ext and "policy" in name_parts and hits <= CREDENTIAL_WORD_PARTS:
            pass  # مستند سياسة يذكر الاعتماديات — وصف وليس سراً (مراجعة P0)
        else:
            return True

    # 4. امتدادات التقارير/الصور العامة — تُحسم عند وجود مؤشر مسار/اسم
    #    (فُحص أعلاه)؛ هنا نُرجع False.
    return False


def is_sensitive_path(
    file_path: Union[str, Path],
    *,
    skip_dirs: Optional[Iterable[str]] = None,
) -> bool:
    """يُعيد True إذا كان الملف يُصنّف على أنه حساس ولا يُسمح بقراءة محتواه.

    قواعد الكشف (محدّثة — مراجعة التصلّد الشامل):
      1. امتداد DICOM/تصوير طبي مؤكد (.dcm، .dicom، إلخ) → حساس دائمًا.
      1ب. امتداد أسرار/مفاتيح (.pem، .p12، .pfx، .key، ...) → حساس دائمًا.
      1ج. اسم ملف أسرار بالاسم الصارم (.env، .netrc، credentials.json،
          id_rsa، ...) → حساس دائمًا.
      2. دليمة DICOM عند الإزاحة 128 حتى لو الامتداد عام — كشف header-based
         (يقرأ 4 بايتات فقط؛ هذا "قراءة محتوى محدودة" موثّقة، لا يُدّعى أنها
         "لا تقرأ المحتوى").
      3. أي جزء من المسار يطابق SENSITIVE_PATH_PARTS (مطابقة كلمة كاملة) →
         حساس. هذه القاعدة إلزامية: skip_dirs *لا* يعطّلها (المعامل محفوظ
         للتوافق التوقيعي فقط — الإغلاق الأمني لجولة التصلّد).
      4. أي جزء من اسم الملف يطابق SENSITIVE_FILENAME_PARTS (word-boundary،
         لا substring) → حساس.
      5. الروابط الرمزية: إن كان المسار رابطاً رمزياً يُصنّف مسار الرابط
         وهدفه النهائي معاً — حساس إن حسّ أي منهما (بلا قراءة محتوى).

    تُستخدم مطابقة الكلمة الكاملة (word-boundary) لتجنب الإنذارات الكاذبة
    مثل "Amrita" التي تحتوي على "mri" كسلسلة فرعية.

    Args:
        file_path: مسار الملف المراد فحصه.
        skip_dirs: مُتجاهَل — كان سابقاً يستطيع تعطيل قواعد إلزامية، وهذا
            ممنوع. يُحفظ للتوافق التوقيعي مع المستدعين القدامى.

    Returns:
        True إذا كان الملف حساسًا ويجب حظر قراءة محتواه.
    """
    path = Path(file_path)

    # الطبقة 1: الاسم والمسار (الرابط + الهدف إن كان رابطاً)
    if _classify_by_name_and_path(path):
        return True

    # الطبقة 1-روابط: رابط رمزي نهائي أو مكوّن وسيط → يُصنّف المسار الفعلي
    # بعد الحل (realpath) — الاسم/المسار + فحص header DICOM على الهدف
    # (4 بايتات موثّقة كما في الطبقة 2)
    abspath = os.path.abspath(os.fspath(path))
    real = os.path.realpath(abspath)
    if real != abspath:
        real_path = Path(real)
        if _classify_by_name_and_path(real_path) or (
            _should_probe_dicom(real_path.suffix.lower()) and _has_dicom_header(real_path)
        ):
            return True

    # الطبقة 2: دليمة DICOM عند الإزاحة 128 — للمرشّحين فقط (بلا امتداد،
    # امتداد رقمي، صورة عامة، أو تصوير طبي). المرشّح غير المعتاد (.csv) لا يُمس.
    if _should_probe_dicom(path.suffix.lower()) and _has_dicom_header(path):
        return True

    return False


def block_if_sensitive(
    file_path: Union[str, Path],
    *,
    operation: str = "قراءة المحتوى",
    skip_dirs: Optional[Iterable[str]] = None,
) -> None:
    """يُرفع استثناء SensitiveFileBlockedError إذا كان الملف حساسًا.

    يجب استدعاء هذه الدالة **قبل** أي عملية قراءة أو استخراج نص أو OCR.

    Args:
        file_path: مسار الملف المراد فحصه.
        operation: وصف العملية لأغراض تسجيل الخطأ.
        skip_dirs: مُتجاهَل (انظر is_sensitive_path).

    Raises:
        SensitiveFileBlockedError: إذا كان الملف حساسًا.
    """
    if is_sensitive_path(file_path, skip_dirs=skip_dirs):
        path = Path(file_path)
        msg = (
            f"محظور: ملف حساس — لا يُسمح بـ '{operation}' على: {path}. "
            f"البيانات الطبية والأنظمة الحساسة محمية وفق تعليمات المستخدم."
        )
        logger.warning(msg)
        raise SensitiveFileBlockedError(msg)


def open_checked(
    file_path: Union[str, Path],
    mode: str = "rb",
    *,
    operation: str = "قراءة المحتوى",
    require_real_file: bool = True,
):
    """يفتح الملف بأمان بعد الحاجز: تصنيف + O_NOFOLLOW + فحص ملف عادي.

    تسلسل الضمانات:
      1. block_if_sensitive — التصنيف (اسم/مسار/header DICOM/هدف رابط).
      2. O_NOFOLLOW عند الفتح (POSIX) — منع بدل المكوّن الأخير برابط رمزي.
      3. fstat بعد الفتح — يجب أن يكون ملفاً عادياً (ليس مجلداً/جهازاً/FIFO).
      4. (اختياري) require_real_file يرفض أي رابط رمزي ظاهر عبر lstat قبل
         الفتح حتى لو كان هدفه غير حساس.

    حدود TOCTOU المتبقية موثّقة في رأس الوحدة وdocs/SENSITIVE_BARRIER.md.

    Raises:
        SensitiveFileBlockedError: ملف حساس أو رابط رمزي محظور أو ليس ملفاً عادياً.
        OSError: أخطاء فعلية من نظام الملفات (لا تُخفى).
    """
    path = Path(file_path)
    block_if_sensitive(path, operation=operation)

    if require_real_file and _readlink_if_symlink(path) is not None:
        msg = f"محظور: '{operation}' يتطلب ملفاً حقيقياً والمسار رابط رمزي: {path}"
        logger.warning(msg)
        raise SymlinkBlockedError(msg)

    if mode not in ("rb", "r"):
        raise ValueError("open_checked يدعم الوضعين 'rb' و 'r' فقط")
    # أنماط نصية: افتح ثنائياً بـ O_NOFOLLOW ثم غلّفها بطبقة نصية
    if mode == "r":
        import io
        binary = open_checked(path, "rb", operation=operation,
                              require_real_file=require_real_file)
        return io.TextIOWrapper(binary, encoding="utf-8", errors="ignore")
    flags = getattr(os, "O_CLOEXEC", 0) | os.O_RDONLY
    nofollow = getattr(os, "O_NOFOLLOW", None)
    if nofollow is not None:
        flags |= nofollow
    fd = os.open(os.fspath(path), flags)
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode):
            raise SensitiveFileBlockedError(
                f"محظور: '{operation}' على غير ملف عادي: {path}"
            )
        if nofollow is None:
            # منصات بلا O_NOFOLLOW (مثل ويندوز): إعادة فحص بعد الفتح
            if _readlink_if_symlink(path) is not None:
                raise SymlinkBlockedError(
                    f"محظور: تحوّل المسار إلى رابط رمزي أثناء الفتح: {path}"
                )
    except Exception:
        os.close(fd)
        raise
    return os.fdopen(fd, mode)


def verify_open_identity(
    fd_file_obj,
    expected_stat: os.stat_result,
) -> bool:
    """يتحقق أن الملف المفتوح (بعد القراءة) ما يزال نفس الهوية الأصلية.

    ضد بدل الملف العادي بملف عادي آخر بين الفحص والقراءة (نافذة TOCTOU
    المتبقية): يقارن st_dev و st_ino لوصف الملف المفتوح مع stat مأخوذ
    قبل الفتح. لا يغلق الملف ولا يقرأ محتواه.

    Returns:
        True إذا كانت الهوية مطابقة.
    """
    try:
        st = os.fstat(fd_file_obj.fileno())
    except (OSError, ValueError, AttributeError):
        return False
    return (st.st_dev, st.st_ino) == (expected_stat.st_dev, expected_stat.st_ino)


def classify_sensitivity(file_path: Union[str, Path]) -> dict:
    """يُرجع تصنيفًا مفصلاً لحساسية الملف لأغراض التسجيل والمراجعة.

    Returns:
        قاموس يحتوي على:
          - is_sensitive: bool
          - reason: str — سبب التصنيف
          - extension: str
          - path_parts: list[str] — أجزاء المسار بالأحرف الصغيرة
          - detection_layers: list[str] — الطبقات التي كشفت الحساسية
            ("path_name"، "header_dicom"، "symlink_target")
    """
    path = Path(file_path)
    ext = path.suffix.lower()
    parts = _path_parts_lower(path)
    full_name_lower = path.name.lower()
    name_parts = _name_parts_lower(full_name_lower)
    layers: list[str] = []

    reason = "غير حساس"
    is_sensitive = False

    if is_medical_imaging_extension(ext) or any(
        s in MEDICAL_IMAGING_EXTENSIONS for s in path.suffixes
    ):
        reason = f"امتداد تصوير طبي مؤكد: {ext}"
        layers.append("path_name")
        is_sensitive = True
    elif ext in SECRET_EXTENSIONS:
        reason = f"امتداد أسرار/مفاتيح: {ext}"
        layers.append("path_name")
        is_sensitive = True
    elif full_name_lower in SECRET_NAME_EXACT:
        reason = "اسم ملف أسرار/اعتماديات بالاسم الصارم"
        layers.append("path_name")
        is_sensitive = True
    elif set(parts) & SENSITIVE_PATH_PARTS:
        matched = set(parts) & SENSITIVE_PATH_PARTS
        reason = f"جزء مسار حساس: {', '.join(sorted(matched))}"
        layers.append("path_name")
        is_sensitive = True
    elif name_parts & SENSITIVE_FILENAME_PARTS:
        matched = name_parts & SENSITIVE_FILENAME_PARTS
        reason = f"جزء اسم ملف حساس (word-boundary): {', '.join(sorted(matched))}"
        layers.append("path_name")
        is_sensitive = True
    elif _readlink_if_symlink(path) is not None:
        target = _realpath_no_strict(path)
        if target is not None and target != path and _classify_by_name_and_path(target):
            reason = f"هدف الرابط الرمزي حساس: {target.name}"
            layers.append("symlink_target")
            is_sensitive = True

    if not is_sensitive and _should_probe_dicom(path.suffix.lower()) and _has_dicom_header(path):
        reason = "دليمة DICOM عند الإزاحة 128 (ملف طبي حتى لو امتداده عام)"
        layers.append("header_dicom")
        is_sensitive = True

    if not is_sensitive:
        reason = "غير حساس"

    return {
        "is_sensitive": is_sensitive,
        "reason": reason,
        "extension": ext,
        "path_parts": parts,
        "detection_layers": layers,
    }


# ─── دوال التكامل مع الوحدات الأخرى ─────────────────────────────────────────


def safe_extract_content(
    file_path: Union[str, Path],
    extractor,
    *,
    operation: str = "استخراج المحتوى",
    skip_dirs: Optional[Iterable[str]] = None,
):
    """يستخرج محتوى الملف فقط إذا لم يكن حساسًا.

    Args:
        file_path: مسار الملف.
        extractor: دالة تستقبل (file_path) وتعيد النص المستخرج.
        operation: وصف العملية لأغراض التسجيل.
        skip_dirs: مُتجاهَل (انظر is_sensitive_path).

    Returns:
        نتيجة extractor إذا لم يكن الملف حساسًا، أو None إذا كان محظورًا.
    """
    if is_sensitive_path(file_path, skip_dirs=skip_dirs):
        path = Path(file_path)
        logger.warning(
            f"محظور: ملف حساس — لا يُسمح بـ '{operation}' على: {path}. "
            f"البيانات الطبية والأنظمة الحساسة محمية وفق تعليمات المستخدم."
        )
        return None
    return extractor(file_path)


def safe_ocr_image(
    filepath: Union[str, Path],
    ocr_func,
    *,
    operation: str = "OCR",
    skip_dirs: Optional[Iterable[str]] = None,
):
    """ينفذ OCR على الصورة فقط إذا لم تكن حساسة.

    Args:
        filepath: مسار ملف الصورة.
        ocr_func: دالة تستقبل (filepath) وتعيد نتيجة OCR.
        operation: وصف العملية.
        skip_dirs: مُتجاهَل (انظر is_sensitive_path).

    Returns:
        نتيجة ocr_func إذا لم تكن الصورة حساسة، أو None إذا كانت محظورة.
    """
    if is_sensitive_path(filepath, skip_dirs=skip_dirs):
        path = Path(filepath)
        logger.warning(
            f"محظور: ملف حساس — لا يُسمح بـ '{operation}' على: {path}. "
            f"البيانات الطبية والأنظمة الحساسة محمية وفق تعليمات المستخدم."
        )
        return None
    return ocr_func(filepath)


# ─── external_send_allowed (سابقًا كود ميت — الآن مُنفَّذ) ────────────────────

def external_send_allowed(
    file_path: Union[str, Path],
    *,
    service_name: str = "external",
) -> bool:
    """يُعيد True إذا يُسمح بإرسال الملف إلى خدمة خارجية.

    تُمنع إرسال أي ملف حساس (طبي، نظامي، اعتماد) إلى أي خدمة خارجية per
    تعليمات المستخدم. هذه الدالة تُستدعى قبل أي عملية إرسال خارجي.

    Args:
        file_path: المسار المراد التحقق منه.
        service_name: اسم الخدمة الخارجية (لأغراض التسجيل فقط).

    Returns:
        True إذا يُسمح بالإرسال، False إذا كان الملف حساسًا ويُمنع إرساله.
    """
    if is_sensitive_path(file_path):
        path = Path(file_path)
        logger.warning(
            f"محظور: إرسال ملف حساس إلى خدمة خارجية '{service_name}' — "
            f"الملف: {path}. البيانات الطبية والأنظمة الحساسة محمية per "
            f"تعليمات المستخدم: ممنوع إرسال أي بيانات طبية إلى خدمة خارجية."
        )
        return False
    return True
