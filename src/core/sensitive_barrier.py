"""حسّاس-بارير — حاجز حماية الملفات الحساسة قبل القراءة/OCR/الإرسال الخارجي

هذه الوحدة تمنع فتح محتوى أي ملف يُصنّف على أنه "حساس" قبل任何 عملية
قراءة أو استخراج نص أو OCR أو إرسال إلى خدمة خارجية.

تصنيفات الحساسية المدعومة:
  1. ملفات طبية (MRI، DICOM، تقارير مرضى): تُصنّف بناءً على الامتداد واسم المجلد.
     لا تُفتح بمحتواها ولا تُرسل لأي خدمة.
  2. مجلدات النظام الحساسة (.ssh، .config): تُستبعد من المسح والقراءة.
  3. ملفات الترخيص/tracking: ملفات قد تحتوي على بيانات اعتماد أو تتبع.

المبادئ التوجيهية من المستخدم:
  - ممنوع opening محتوى الملفات الطبية لأي سبب.
  - ممنوع إرسال أي بيانات طبية إلى خدمة خارجية.
  - لا تُتبع الروابط الرمزية، ولا تُعبر نقاط التركيب.
  - لا تُعدّل صلاحيات/ملكية/سمات الملفات.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Iterable, Optional, Union

logger = logging.getLogger(__name__)

PathLike = Union[str, Path]

# دليمة DICOM عند الإزاحة 128 (البايتات 128-131) per معيار DICOM
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

# ─── مؤشرات المسارات الحساسة ────────────────────────────────────────────────

# أجزاء المسار التي تشير إلى مجلدات طبية أو حساسة
SENSITIVE_PATH_PARTS = frozenset(
    {
        # مجلدات طبية
        "mri",
        "dicom",
        "medical",
        "patient",
        "مرضى",
        "تقرير طبي",
        "تقرير_طبي",
        "clinics",
        "clinic",
        "hospital",
        "مستشفى",
        "عيادة",
        # مجلدات نظام حساسة
        ".ssh",
        ".config",
        ".gnupg",
        ".gnupg2",
        ".pki",
        ".certs",
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
    }
)


# ─── استثناءات ───────────────────────────────────────────────────────────────


class SensitiveFileBlockedError(Exception):
    """يُرفع عند محاولة قراءة ملف محمي بواسطة الحسّاس-بارير."""


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


def _has_dicom_header(file_path: Path) -> bool:
    """يُعيد True لو كان الملف يبدأ بدليمة DICOM عند الإزاحة 128.

    معيار DICOM: البايتات 128–131 devono أن تحتوي على "DICM" لو كان الملف
    ملف DICOM صالح regardless من الامتداد. يُفتح الملف في وضع قراءة بايتات
    فقط وتُقرأ 4 بايتات عند الإزاحة 128 دون تعديل任何 شيء.
    """
    try:
        with file_path.open("rb") as f:
            f.seek(_DICOM_MAGIC_OFFSET)
            magic = f.read(_DICOM_MAGIC_LEN)
        return magic == _DICOM_MAGIC
    except OSError:
        # لو تعذّر القراءة، نتعامل مع الملف على أنه غير مؤكد (ليس DICOM مؤكد)
        return False


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


def is_sensitive_path(
    file_path: Union[str, Path],
    *,
    skip_dirs: Optional[Iterable[str]] = None,
) -> bool:
    """يُعيد True إذا كان الملف يُصنّف على أنه حساس ولا يُسمح بقراءة محتواه.

    قواعد الكشف (محدّثة per مراجعة F1):
      1. امتداد DICOM/تصوير طبي مؤكد (.dcm، .dicom، إلخ) → حساس دائمًا.
      2. دليمة DICOM (байтات 128–131 = "DICM") حتى لو امتداد الملف عام
         (.jpg، .png، .pdf...) → حساس دائمًا (كشف المحتوى دون فتح مضمون).
      3. أي جزء من المسار يتطابق مع SENSITIVE_PATH_PARTS (مطابقة كلمة كاملة)
         → حساس.
      4. أي جزء من اسم الملف يتطابق مع SENSITIVE_FILENAME_PARTS (مطابقة كلمة
         كاملة عبر word-boundary، لا substring) → حساس.
      5. امتدادات التقارير الطبية (.pdf، .docx، .txt، إلخ) تُحسم بناءً على
         وجود مؤشر مسار أو اسم ملف حساس في المسار.
      6. امتدادات الصور العادية (.jpg، .png، إلخ) تُحسم بناءً على وجود
         مؤشر مسار أو اسم ملف حساس في المسار.

    تُستخدم مطابقة الكلمة الكاملة (word-boundary) لتجنب الإنذارات الكاذبة
    مثل "Amrita" التي تحتوي على "mri" كسلسلة فرعية.

    Args:
        file_path: مسار الملف المراد فحصه.
        skip_dirs: مجلدات إضافية للاستبعاد (مثل __pycache__, node_modules).

    Returns:
        True إذا كان الملف حساسًا ويجب حظر قراءة محتواه.
    """
    path = Path(file_path)
    ext = path.suffix.lower()
    # جميع suffixes (بما في ذلك .nii.gz → ['.nii', '.gz'])
    all_suffixes = [s.lower() for s in path.suffixes]
    full_name_lower = path.name.lower()
    parts = _path_parts_lower(path)

    # 1. امتداد تصوير طبي مؤكد — دائمًا محظور
    if is_medical_imaging_extension(ext) or any(
        s in MEDICAL_IMAGING_EXTENSIONS for s in all_suffixes
    ):
        return True

    # 2. دليمة DICOM عند الإزاحة 128 — حتى لو الامتداد عام
    # (يُقرأ فقط 4 بايتات، لا يُفتح محتوى الملف)
    try:
        if _has_dicom_header(path):
            return True
    except OSError:
        pass

    # 3. أي جزء من المسار يشير إلى مجلد طبي/نظام/حساس
    sensitive_parts = set(parts) & SENSITIVE_PATH_PARTS
    if skip_dirs:
        skip_lower = {d.lower() for d in skip_dirs}
        sensitive_parts -= skip_lower
    if sensitive_parts:
        return True

    # 4. أي جزء من اسم الملف يشير إلى محتوى طبي/حساس (word-boundary)
    name_parts = _name_parts_lower(full_name_lower)
    sensitive_name_parts = name_parts & SENSITIVE_FILENAME_PARTS
    if sensitive_name_parts:
        return True

    # 5. امتدادات التقارير الطبية — محظورة فقط إذا كان هناك مؤشر مسار/اسم حساس
    if ext in MEDICAL_REPORT_EXTENSIONS:
        # إذا وصلنا到这里 ولم يُعثر على جزء حساس، نعيد False للسماح بقراءة العادية
        return False

    # 6. امتدادات الصور العادية — محظورة فقط إذا كان هناك مؤشر حساس
    if ext in MEDICAL_IMAGE_EXTENSIONS:
        return False

    # 7. امتدادات أخرى غير معروفة — لا تُحظر
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
        skip_dirs: مجلدات إضافية للاستبعاد.

    Raises:
        SensitiveFileBlockedError: إذا كان الملف حساسًا.
    """
    if is_sensitive_path(file_path, skip_dirs=skip_dirs):
        path = Path(file_path)
        msg = (
            f"محظور: archivo حساس — لا يُسمح بـ '{operation}' على: {path}. "
            f"البيانات الطبية والأنظمة الحساسة محمية per تعليمات المستخدم."
        )
        logger.warning(msg)
        raise SensitiveFileBlockedError(msg)


def classify_sensitivity(file_path: Union[str, Path]) -> dict:
    """يُرجع تصنيفًا مفصلاً لحساسية الملف لأغراض التسجيل والمراجعة.

    Returns:
        قاموس يحتوي على:
          - is_sensitive: bool
          - reason: str — سبب التصنيف
          - extension: str
          - path_parts: list[str] — أجزاء المسار بالأحرف الصغيرة
    """
    path = Path(file_path)
    ext = path.suffix.lower()
    parts = _path_parts_lower(path)
    full_name_lower = path.name.lower()
    name_parts = _name_parts_lower(full_name_lower)

    reason = "غير حساس"

    if is_medical_imaging_extension(ext) or any(
        s in MEDICAL_IMAGING_EXTENSIONS for s in path.suffixes
    ):
        reason = f"امتداد تصوير طبي مؤكد: {ext}"
    elif _has_dicom_header(path):
        reason = "دليمة DICOM عند الإزاحة 128 (ملف طبي حتى لو امتداده عام)"
    elif set(parts) & SENSITIVE_PATH_PARTS:
        matched = set(parts) & SENSITIVE_PATH_PARTS
        reason = f"جزء مسار حساس: {', '.join(sorted(matched))}"
    elif name_parts & SENSITIVE_FILENAME_PARTS:
        matched = name_parts & SENSITIVE_FILENAME_PARTS
        reason = f"جزء اسم ملف حساس (word-boundary): {', '.join(sorted(matched))}"
    elif ext in MEDICAL_REPORT_EXTENSIONS:
        reason = f"امتداد تقرير طبي (بدون مؤشر مسار): {ext}"
    elif ext in MEDICAL_IMAGE_EXTENSIONS:
        reason = f"امتداد صورة عادية (بدون مؤشر مسار): {ext}"

    return {
        "is_sensitive": is_sensitive_path(path),
        "reason": reason,
        "extension": ext,
        "path_parts": parts,
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
        skip_dirs: مجلدات إضافية للاستبعاد.

    Returns:
        نتيجة extractor إذا لم يكن الملف حساسًا، أو None إذا كان محظورًا.
    """
    if is_sensitive_path(file_path, skip_dirs=skip_dirs):
        path = Path(file_path)
        logger.warning(
            f"محظور: archivo حساس — لا يُسمح بـ '{operation}' على: {path}. "
            f"البيانات الطبية والأنظمة الحساسة محمية per تعليمات المستخدم."
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
        skip_dirs: مجلدات إضافية للاستبعاد.

    Returns:
        نتيجة ocr_func إذا لم تكن الصورة حساسة، أو None إذا كانت محظورة.
    """
    if is_sensitive_path(filepath, skip_dirs=skip_dirs):
        path = Path(filepath)
        logger.warning(
            f"محظور: archivo حساس — لا يُسمح بـ '{operation}' على: {path}. "
            f"البيانات الطبية والأنظمة الحساسة محمية per تعليمات المستخدم."
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
        file_path: مسار الملف المراد التحقق منه.
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
