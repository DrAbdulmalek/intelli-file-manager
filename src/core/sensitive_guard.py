"""حاجز الحساسية — يمنع قراءة محتوى الملفات الحساسة أو إرسالها خارج الجهاز (P0)

يصنف أي مسار إلى أحد المستويات الخمسة من بروتوكول AlphaCode v2.0
(docs/ALPHACODE_PROTOCOL_v2.0.md §2.2):

    PUBLIC / NON_SENSITIVE / PRIVATE / SENSITIVE_MEDICAL / SECURITY_SECRETS

القاعدة الحاكمة: SECURITY_SECRETS وSENSITIVE_MEDICAL لا يُقرأ محتواها
للتصنيف (نص/PDF/OCR) ولا تُرسل إلى أي خدمة خارجية — التصنيف يقتصر على
الاسم والحجم والبيانات الوصفية، والحالة تُعلَّم REVIEW_REQUIRED.

التصنيف هنا بالاسم والمسار فقط — لا يقرأ المحتوى أبداً.
"""
from __future__ import annotations

from pathlib import Path
from typing import Union

LEVEL_PUBLIC = "PUBLIC"
LEVEL_NON_SENSITIVE = "NON_SENSITIVE"
LEVEL_PRIVATE = "PRIVATE"
LEVEL_SENSITIVE_MEDICAL = "SENSITIVE_MEDICAL"
LEVEL_SECURITY_SECRETS = "SECURITY_SECRETS"

# أنماط الأسرار الأمنية (تُطابق على اسم الملف بأحرف صغيرة).
# ملاحظة: Path(".env").suffix == "" — ملفات النقطة تُطابق بالاسم لا بالامتداد.
_SECRET_NAME_PATTERNS = (
    ".env", ".htpasswd", ".netrc",
    "id_rsa", "id_dsa", "id_ecdsa", "id_ed25519", "authorized_keys",
    "credentials", "credential", "password", "passwd", "secret", "token",
    "api_key", "apikey", "wallet", "keystore",
)

# امتدادات الأسرار (شهادات/مفاتيح/خزائن كلمات مرور)
_SECRET_EXTENSIONS = (
    ".env", ".pem", ".key", ".p12", ".pfx", ".kdbx", ".jks", ".keystore",
)

# مجلدات أسرار معروفة (تُطابق على أجزاء المسار)
_SECRET_DIR_PATTERNS = (".ssh", ".gnupg", ".aws", ".kube")

# أنماط البيانات الطبية الحساسة (MRI/DICOM/تقارير مرضى) — عربي وإنجليزي.
# ملاحظة: كلمات عامة مثل «أشعة» مستبعدة عمداً لتجنب حجب الكتب التعليمية.
_MEDICAL_PATTERNS = (
    "dicom", ".dcm", "mri", "ct_scan", "ct-scan", "pet_scan",
    "patient", "مريض", "مرضى", "رنين", "تحاليل",
    "سجل طبي", "تقرير طبي", "سجل_طبي", "تقرير_طبي",
)

# أنماط خاصة/شخصية
_PRIVATE_PATTERNS = (
    "invoice", "فاتورة", "عقد", "contract", "passport", "جواز",
    "هوية", "id_card", "سيرة",
)


def classify_sensitivity(path: Union[str, Path]) -> str:
    """يصنف حساسية مسار ملف من اسمه ومجلداته فقط — دون قراءة المحتوى.

    الأولوية: SECURITY_SECRETS > SENSITIVE_MEDICAL > PRIVATE > NON_SENSITIVE.
    """
    p = Path(path)
    name = p.name.lower()
    parts = " / ".join(part.lower() for part in p.parts)
    ext = p.suffix.lower()
    blob = f"{name} {parts}"

    if ext in _SECRET_EXTENSIONS:
        return LEVEL_SECURITY_SECRETS
    if any(pat in name for pat in _SECRET_NAME_PATTERNS):
        return LEVEL_SECURITY_SECRETS
    if any(pat in parts for pat in _SECRET_DIR_PATTERNS):
        return LEVEL_SECURITY_SECRETS

    if any(pat in blob for pat in _MEDICAL_PATTERNS):
        return LEVEL_SENSITIVE_MEDICAL

    if any(pat in blob for pat in _PRIVATE_PATTERNS):
        return LEVEL_PRIVATE

    return LEVEL_NON_SENSITIVE


def content_read_allowed(level: str) -> bool:
    """هل يجوز قراءة محتوى هذا المستوى للتصنيف؟ حاجز ما قبل الاستخراج/OCR."""
    return level not in (LEVEL_SECURITY_SECRETS, LEVEL_SENSITIVE_MEDICAL)


def external_send_allowed(level: str) -> bool:
    """هل يجوز إرسال بيانات هذا المستوى إلى خدمة خارجية؟ حاجز ما قبل أي AI خارجي."""
    return level in (LEVEL_PUBLIC, LEVEL_NON_SENSITIVE)


def redact_path(path: Union[str, Path], home: Union[str, Path, None] = None) -> str:
    """مسار منقّح للسجلات الهندسية: يستبدل مجلد المنزل بـ~ عند تمريره."""
    p = str(path)
    if home:
        h = str(home)
        if h and p.startswith(h):
            p = "~" + p[len(h):]
    return p
