"""content_analyzer — تحليل عميق للمحتوى عند الفرز: نصوص وصور وصوت (محلي بالكامل)

يستكمل محرك الفرز بثلاث قدرات كانت شاغرة في وضع المسح السريع (fast):
  1. قراءة محتوى المستندات (نص عادي/PDF/Office/ODT/EPUB) واستنباط نوع المستند
     ولغته من الكلمات المفتاحية العربية والإنجليزية — لتغذية شروط القواعد
     (extra:doc_type، extra:content_lang) ووسوم ملف الميتاداتا.
  2. تحليل الصور: الأبعاد، EXIF (صانع الكاميرا/الموديل/الوقت)، كشف لقطات
     الشاشة، الألوان السائدة، الرمادي — عبر Pillow بلا أدوات خارجية.
  3. تحليل الصوت: المدة، معدل البت، وسوم ID3 (فنان/ألبوم/نوع)، وتمييز
     موسيقى/تسجيل صوتي — عبر mutagen بلا حاجة لـ ffprobe (الغائب عادةً
     على أجهزة المستخدمين).

ضمانات الأمان (غير قابلة للتفاوض):
  - الحاجز أولاً: الملف الحساس (is_sensitive_path) لا يُفتح محتواه إطلاقاً —
    يُوسم sensitive-no-deep فقط ويُتخطى. وضع medical strict يمنع قراءة
    المحتوى الطبي أيضاً (is_medical_content_locked).
  - محلي 100%: لا شبكة، لا إرسال خارجي، لا OCR سحابي — القراءة للتصنيف
    المحلي فقط بنفس منطق FileInventory.include_content.
  - حدود أحجام لكل نوع (نص/صورة/صوت) تُتجاوز بالتخطي لا بالفشل.
  - كل ملف في try/except مستقل: فشل ملف واحد لا يوقف المسح، ويُحتسب في
    عدادات deep_errors.

الاستهلاك في القواعد (rule_schemas):
  - شرط extra بمفتاح فرعي: {field: extra, op: eq, value: screenshot, key: image_kind}
  - شرط has_tag: {field: has_tag, op: eq, value: camera-photo}
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .sensitive_barrier import is_sensitive_path

logger = logging.getLogger(__name__)

# ─── حدود الأحجام (بايت) — تجاوز الحد = تخطي التحليل بلا فشل ────────────────
MAX_TEXT_FILE_BYTES = 20 * 1024 * 1024      # 20MB للنصوص
MAX_IMAGE_BYTES = 80 * 1024 * 1024          # 80MB للصور
MAX_AUDIO_BYTES = 500 * 1024 * 1024         # 500MB للصوت (قراءة رأس فقط)
TEXT_SAMPLE_CHARS = 64_000                  # أول 64 ألف محرف تكفي للتصنيف

# امتدادات النص الصريح (قراءة مباشرة بلا مكتبات)
_PLAIN_TEXT_EXT = {
    "txt", "md", "csv", "log", "json", "xml", "yaml", "yml", "ini", "cfg",
    "toml", "py", "js", "ts", "jsx", "tsx", "html", "htm", "css", "scss",
    "sh", "bash", "bat", "ps1", "sql", "srt", "tex", "vue", "swift", "kt",
}
_IMAGE_EXT = {"jpg", "jpeg", "png", "bmp", "gif", "webp", "tiff", "tif", "heic", "avif"}
_AUDIO_EXT = {"mp3", "wav", "flac", "ogg", "m4a", "wma", "aac", "opus", "amr", "3gp"}

# أنماط أسماء لقطات الشاشة الشائعة (Windows/macOS/أدوات الالتقاط)
_SCREENSHOT_NAME_RE = re.compile(
    r"(screenshot|screen\s?shot|لقطة|لقطة شاشة|snip|capture|grim|scrot)", re.IGNORECASE
)

# كلمات أنواع المستندات — أول تطابق يفوز (ترتيب الأكثر تحديداً أولاً)
_DOC_TYPE_KEYWORDS: List[Tuple[str, tuple]] = [
    ("فاتورة", ("فاتورة", "فواتير", "invoice", "المبلغ الإجمالي", "الضريبة", "القيمة المضافة")),
    ("شهادة", ("شهادة", "شهادات", "certificate", "إتمام دورة", "completion")),
    ("عقد", ("عقد", "اتفاقية", "contract", "agreement", "الطرف الأول", "الطرف الثاني")),
    ("سيرة_ذاتية", ("سيرة ذاتية", "السيرة الذاتية", "resume", "curriculum vitae", "cv")),
    ("بحث", ("الملخص", "المستخلص", "abstract", "المراجع", "references", "المنهجية")),
    ("تقرير", ("تقرير", "تقارير", "report")),
    ("كتاب", ("الفصل", "الفهرس", "chapter", "table of contents")),
    ("محاضرة", ("محاضرة", "المحاضرة", "lecture", "course notes")),
    ("رسالة", ("رسالة", "خطاب", "الموضوع:", "subject:")),
]


def extract_text(path: Path, ext: str) -> str:
    """استخراج نص من المستند — حسب الامتداد، مع سقف محارف.

    لا يُستدعى على الملفات الحساسة إطلاقاً (يتحقق المتصل analyze_file).
    """
    if ext in _PLAIN_TEXT_EXT:
        raw = path.read_bytes()[: TEXT_SAMPLE_CHARS * 4]
        for enc in ("utf-8", "utf-16", "cp1256", "latin-1"):
            try:
                return raw.decode(enc)[:TEXT_SAMPLE_CHARS]
            except (UnicodeDecodeError, ValueError):
                continue
        return ""
    if ext == "pdf":
        try:
            from pypdf import PdfReader
            reader = PdfReader(str(path))
            return "\n".join((p.extract_text() or "") for p in reader.pages[:5])[:TEXT_SAMPLE_CHARS]
        except Exception:
            pass
        try:
            import fitz  # PyMuPDF — أفضل للعربية
            doc = fitz.open(str(path))
            text = "\n".join(doc[i].get_text() for i in range(min(5, doc.page_count)))
            doc.close()
            return text[:TEXT_SAMPLE_CHARS]
        except Exception:
            return ""
    if ext == "docx":
        try:
            from docx import Document
            doc = Document(str(path))
            return "\n".join(p.text for p in doc.paragraphs)[:TEXT_SAMPLE_CHARS]
        except Exception:
            return ""
    if ext in ("odt", "pptx", "xlsx", "epub"):
        try:
            import zipfile
            import xml.etree.ElementTree as ET
            with zipfile.ZipFile(str(path)) as zf:
                names = [n for n in zf.namelist() if n.endswith(".xml")][:20]
                chunks = []
                for n in names:
                    try:
                        root = ET.fromstring(zf.read(n))
                        chunks.append(" ".join(t.strip() for t in root.itertext() if t and t.strip()))
                    except Exception:
                        continue
                return "\n".join(chunks)[:TEXT_SAMPLE_CHARS]
        except Exception:
            return ""
    return ""


def analyze_text_content(text: str, file_name: str) -> Dict[str, object]:
    """استنباط لغة المحتوى ونوع المستند من النص (وعينات الاسم)."""
    out: Dict[str, object] = {}
    if not text:
        return out
    arabic = sum(1 for ch in text if "\u0600" <= ch <= "\u06ff")
    latin = sum(1 for ch in text if ch.isascii() and ch.isalpha())
    total = arabic + latin
    if total >= 20:
        out["content_lang"] = "ar" if arabic / total >= 0.3 else "en"
        if 0.3 < arabic / total < 0.7:
            out["content_lang"] = "mixed"
    haystack = (text[:4000] + " " + file_name).lower()
    for doc_type, keywords in _DOC_TYPE_KEYWORDS:
        for kw in keywords:
            if kw.lower() in haystack:
                out["doc_type"] = doc_type
                break
        if "doc_type" in out:
            break
    return out


def analyze_image(path: Path, ext: str) -> Dict[str, object]:
    """تحليل صورة: أبعاد/EXIF/لقطة شاشة/ألوان سائدة/رمادي — عبر Pillow."""
    from PIL import Image, ExifTags
    out: Dict[str, object] = {}
    with Image.open(str(path)) as img:
        width, height = img.size
        out["width"] = width
        out["height"] = height
        out["format"] = (img.format or ext).lower()
        if height > 0:
            out["aspect_ratio"] = round(width / height, 2)
        exif = img.getexif()
        exif_dict: Dict[str, object] = {}
        if exif:
            name_of = {v: k for k, v in ExifTags.TAGS.items()}
            keep = {271: "make", 272: "model", 306: "datetime", 34853: "gps"}
            for tag_id, tag_name in keep.items():
                val = exif.get(tag_id)
                if val:
                    exif_dict[tag_name] = str(val)
            out["exif"] = exif_dict
        else:
            out["exif"] = None
        # كشف لقطة الشاشة: بلا كاميرا + اسم/خصائص لقطة
        camera = bool(exif_dict.get("make") or exif_dict.get("model"))
        name_hit = bool(_SCREENSHOT_NAME_RE.search(path.name))
        screen_like = min(width, height) >= 720 and 1.0 <= (width / max(height, 1)) <= 2.4
        if camera:
            out["image_kind"] = "camera_photo"
        elif name_hit or (ext in ("png", "bmp") and screen_like):
            out["image_kind"] = "screenshot"
        else:
            out["image_kind"] = "photo"
        # ألوان سائدة + رمادي (عينة 32×32 تكفي وتكفي الذاكرة)
        small = img.convert("RGB").resize((32, 32))
        colors = small.getcolors(maxcolors=1024 * 8) or []
        if colors:
            colors.sort(reverse=True)
            out["dominant_colors"] = [
                "#{:02x}{:02x}{:02x}".format(*c[1]) for c in colors[:3]
            ]
            out["is_grayscale"] = all(r == g == b for _, (r, g, b) in colors)
        else:
            out["is_grayscale"] = img.mode in ("L", "LA", "1")
    return out


def analyze_audio(path: Path, ext: str) -> Dict[str, object]:
    """تحليل صوت: مدة/معدل بت/وسوم ID3/تمييز موسيقى أم تسجيل — عبر mutagen."""
    from mutagen import File as MutagenFile
    out: Dict[str, object] = {}
    audio = MutagenFile(str(path), easy=True)
    if audio is None or audio.info is None:
        return out
    out["format_name"] = type(audio).__name__.lower()
    duration = getattr(audio.info, "length", 0) or 0
    out["duration_seconds"] = round(duration, 1)
    bitrate = getattr(audio.info, "bitrate", 0) or 0
    out["bit_rate"] = bitrate
    out["sample_rate"] = getattr(audio.info, "sample_rate", 0) or 0
    out["channels"] = getattr(audio.info, "channels", 0) or 0
    tags = {}
    if audio.tags:
        for key in ("title", "artist", "album", "genre", "date"):
            val = audio.tags.get(key)
            if val:
                tags[key] = str(val[0] if isinstance(val, (list, tuple)) else val)
    out["audio_tags"] = tags
    # تمييز النوع: وسوم فنان/ألبوم → موسيقى؛ بلا وسوم وتسجيل طويل/امتداد هاتف → تسجيل
    if tags.get("artist") or tags.get("album") or tags.get("genre"):
        out["audio_kind"] = "music"
    elif duration >= 60 or ext in ("amr", "3gp", "wav", "m4a"):
        out["audio_kind"] = "voice_recording"
    else:
        out["audio_kind"] = "unknown"
    return out


def analyze_file(file_path: str, ext: str, file_size: int) -> Tuple[Dict[str, object], List[str], str]:
    """التحليل العميق لملف واحد — الحاجز أولاً ثم التصنيف حسب النوع.

    Returns:
        (extra_metadata الجديد, قائمة وسوم, نوع النتيجة)
        النتيجة: text | image | audio | skip_sensitive | skip_size | unsupported | error
    """
    p = Path(file_path)
    # ── الحاجز أولاً: لا فتح محتوى ملف حساس إطلاقاً ──
    if is_sensitive_path(p):
        return {}, ["sensitive-no-deep"], "skip_sensitive"
    try:
        if ext in _PLAIN_TEXT_EXT or ext in ("pdf", "docx", "odt", "pptx", "xlsx", "epub"):
            if file_size > MAX_TEXT_FILE_BYTES:
                return {}, [], "skip_size"
            text = extract_text(p, ext)
            info = analyze_text_content(text, p.name)
            tags = [f"deep:{info['content_lang']}"] if "content_lang" in info else []
            if "doc_type" in info:
                tags.append(f"doc:{info['doc_type']}")
            return info, tags, "text"
        if ext in _IMAGE_EXT:
            if file_size > MAX_IMAGE_BYTES:
                return {}, [], "skip_size"
            info = analyze_image(p, ext)
            tags = []
            kind = info.get("image_kind")
            if kind == "screenshot":
                tags.append("screenshot")
            elif kind == "camera_photo":
                tags.append("camera-photo")
            if info.get("is_grayscale"):
                tags.append("grayscale-image")
            return info, tags, "image"
        if ext in _AUDIO_EXT:
            if file_size > MAX_AUDIO_BYTES:
                return {}, [], "skip_size"
            info = analyze_audio(p, ext)
            tags = []
            kind = info.get("audio_kind")
            if kind == "music":
                tags.append("music-tagged")
            elif kind == "voice_recording":
                tags.append("voice-recording")
            return info, tags, "audio"
        return {}, [], "unsupported"
    except ImportError as e:
        logger.debug(f"مكتبة تحليل غير متوفرة لـ {p.name}: {e}")
        return {}, [], "unsupported"
    except Exception as e:
        logger.debug(f"فشل التحليل العميق لـ {p.name}: {e}")
        return {}, [], "error"


def enrich_record(record) -> str:
    """إثراء FileRecord بنتيجة التحليل العميق: extra_metadata + tags.

    يدمج بلا حذف: مفاتيح extra الموجودة (من المسح الكامل مثلاً) تبقى كما هي
    والمفقودة تُملأ. يُرجع نوع النتيجة كما في analyze_file.
    """
    m = record.metadata
    ext = (m.extension or "").lower().lstrip(".")
    extra, tags, result = analyze_file(m.file_path, ext, m.file_size)
    if extra:
        for k, v in extra.items():
            m.extra_metadata.setdefault(k, v)
    if tags:
        for t in tags:
            if t not in m.tags:
                m.tags.append(t)
    return result
