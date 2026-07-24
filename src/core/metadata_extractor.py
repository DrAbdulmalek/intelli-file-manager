"""MetadataExtractor — مستخرج الميتاداتا الموحّد

هذه الوحدة هي المسؤول الوحيد عن استخراج الميتاداتا الخاصة بنوع الوسيط:
  - الصور: أبعاد + صيغة + EXIF (كاميرا، GPS، تاريخ الالتقاط، ...)
  - الصوت/الفيديو: المدة + الترميز + معدل البت + الأبعاد (للفيديو) عبر ffprobe
  - نوع المحتوى (MIME): عبر python-magic (يقرأ magic bytes) مع fallback للامتداد

التصميم:
  - جميع الدوال stateless وآمنة للاستدعاء المتوازي
  - استيراد كسول لكل تبعية (graceful degradation لو المكتبة غير مثبتة)
  - تسامح تام مع الأخطاء: ملف تالف لا يُرجّع استثناء، فقط قاموس جزئي
  - لا AI، لا OCR، لا ميزات طبية — مسؤولية الطبقات الأخرى

PR-03 من development-roadmap-v1.0
"""
from __future__ import annotations

import json
import logging
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# ─── ثوابت ─────────────────────────────────────────────────────────────────
FFPROBE_TIMEOUT_SECONDS = 10
FFPROBE_BIN = shutil.which("ffprobe") or ""

# حد أقصى لطول قائمة EXIF لمنع تضخيم السجل
MAX_EXIF_ENTRIES = 64


# ─── استخراج ميتاداتا الصور ────────────────────────────────────────────────

def extract_image_metadata(file_path: Path | str) -> Dict[str, Any]:
    """يستخرج ميتاداتا الصورة عبر Pillow + EXIF

    Args:
        file_path: مسار ملف الصورة

    Returns:
        قاموس قد يحتوي:
          - width, height (int)
          - format (str): JPEG, PNG, ...
          - mode (str): RGB, RGBA, L, ...
          - exif (dict): وسوم EXIF المعروفة (Make, Model, DateTime, GPSInfo, ...)
          - exif_count (int): عدد وسوم EXIF الخام

    ملاحظة: الملفات التالفة تُرجع قاموسًا جزئيًا (ربما فقط {"error": "..."})
    """
    path = Path(file_path)
    result: Dict[str, Any] = {}

    try:
        from PIL import Image, ExifTags
    except ImportError:
        logger.debug("Pillow غير مثبت — تخطي ميتاداتا الصورة")
        return {"error": "PIL_unavailable"}

    try:
        with Image.open(str(path)) as img:
            result["width"] = img.width
            result["height"] = img.height
            result["format"] = img.format or ""
            result["mode"] = img.mode or ""

            # استخراج EXIF (إن وُجد)
            try:
                raw_exif = img.getexif() if hasattr(img, "getexif") else None
            except Exception as ex:
                logger.debug(f"فشل قراءة EXIF من {path.name}: {ex}")
                raw_exif = None

            if raw_exif:
                exif_dict: Dict[str, Any] = {}
                for tag_id, value in raw_exif.items():
                    if len(exif_dict) >= MAX_EXIF_ENTRIES:
                        break
                    tag_name = ExifTags.TAGS.get(tag_id, f"Tag_{tag_id}")
                    # تحويل القيم غير القابلة للتسلسل إلى نص
                    if isinstance(value, bytes):
                        try:
                            value = value.decode("utf-8", errors="replace")
                        except Exception:
                            value = f"<{len(value)} bytes>"
                    elif isinstance(value, tuple):
                        # مثل قيم GPS (degrees, minutes, seconds)
                        try:
                            value = list(value)
                        except Exception:
                            value = str(value)
                    elif not isinstance(value, (str, int, float, bool, list, dict)):
                        value = str(value)
                    exif_dict[tag_name] = value

                if exif_dict:
                    result["exif"] = exif_dict
                    result["exif_count"] = len(exif_dict)

                    # استخراج حقول شائعة للاستخدام السريع
                    if "DateTime" in exif_dict:
                        result["captured_at"] = exif_dict["DateTime"]
                    if "Make" in exif_dict:
                        result["camera_make"] = exif_dict["Make"]
                    if "Model" in exif_dict:
                        result["camera_model"] = exif_dict["Model"]
                    if "GPSInfo" in exif_dict:
                        result["has_gps"] = True
    except Exception as e:
        logger.debug(f"فشل استخراج ميتاداتا الصورة {path.name}: {e}")
        result["error"] = str(e)[:200]

    return result


# ─── استخراج ميتاداتا الصوت/الفيديو ────────────────────────────────────────

def extract_av_metadata(file_path: Path | str) -> Dict[str, Any]:
    """يستخرج ميتاداتا الصوت/الفيديو عبر ffprobe

    Args:
        file_path: مسار ملف الصوت أو الفيديو

    Returns:
        قاموس قد يحتوي:
          - duration_seconds (float)
          - bit_rate (int)
          - format_name (str)
          - size_bytes (int)
          - video (dict): codec, width, height, fps, ...
          - audio (dict): codec, sample_rate, channels, ...
          - tags (dict): وسوم مثل title, artist, album (إن وُجدت)

    ملاحظة: لو ffprobe غير مثبت يُرجع {"error": "ffprobe_unavailable"}
    """
    path = Path(file_path)

    if not FFPROBE_BIN:
        logger.debug("ffprobe غير مثبت — تخطي ميتاداتا AV")
        return {"error": "ffprobe_unavailable"}

    cmd = [
        FFPROBE_BIN,
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        str(path),
    ]

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=FFPROBE_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        logger.debug(f"ffprobe انتهت مهلته على {path.name}")
        return {"error": "ffprobe_timeout"}
    except Exception as e:
        logger.debug(f"ffprobe فشل على {path.name}: {e}")
        return {"error": f"ffprobe_failed: {e}"}

    if proc.returncode != 0:
        return {"error": f"ffprobe_returncode_{proc.returncode}"}

    if not proc.stdout:
        return {"error": "ffprobe_empty_output"}

    try:
        info = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        logger.debug(f"ffprobe أرجع JSON غير صالح لـ {path.name}: {e}")
        return {"error": "ffprobe_invalid_json"}

    return _parse_ffprobe_info(info)


def _parse_ffprobe_info(info: dict) -> Dict[str, Any]:
    """يحلّل مخرجات ffprobe JSON إلى قاموس مبسّط"""
    result: Dict[str, Any] = {}

    fmt = info.get("format", {})
    if fmt:
        # المدة (نص → float)
        duration_str = fmt.get("duration")
        if duration_str:
            try:
                result["duration_seconds"] = float(duration_str)
            except (TypeError, ValueError):
                pass

        # معدل البت
        bit_rate_str = fmt.get("bit_rate")
        if bit_rate_str:
            try:
                result["bit_rate"] = int(bit_rate_str)
            except (TypeError, ValueError):
                pass

        if fmt.get("format_name"):
            result["format_name"] = fmt["format_name"]
        if fmt.get("format_long_name"):
            result["format_long_name"] = fmt["format_long_name"]

        size_str = fmt.get("size")
        if size_str:
            try:
                result["size_bytes"] = int(size_str)
            except (TypeError, ValueError):
                pass

        # وسوم (title, artist, album, ...)
        tags = fmt.get("tags", {})
        if tags and isinstance(tags, dict):
            # نأخذ فقط الوسوم الشائعة لتجنب تضخيم القاموس
            common_tags = {
                k: v for k, v in tags.items()
                if k.lower() in {
                    "title", "artist", "album", "album_artist",
                    "genre", "track", "date", "comment", "language",
                    "composer", "encoder", "copyright",
                }
            }
            if common_tags:
                result["tags"] = common_tags

    # تدفقات الفيديو والصوت
    streams = info.get("streams", [])
    if not isinstance(streams, list):
        streams = []

    for stream in streams:
        if not isinstance(stream, dict):
            continue
        codec_type = stream.get("codec_type")
        if codec_type == "video" and "video" not in result:
            result["video"] = _parse_video_stream(stream)
        elif codec_type == "audio" and "audio" not in result:
            result["audio"] = _parse_audio_stream(stream)

    return result


def _parse_video_stream(stream: dict) -> Dict[str, Any]:
    """يحلّل تدفق فيديو من ffprobe"""
    v: Dict[str, Any] = {}
    if stream.get("codec_name"):
        v["codec"] = stream["codec_name"]
    if stream.get("width"):
        v["width"] = int(stream["width"])
    if stream.get("height"):
        v["height"] = int(stream["height"])
    if stream.get("pix_fmt"):
        v["pixel_format"] = stream["pix_fmt"]

    # معدل الإطارات (framerate) — نص مثل "30000/1001"
    fps_str = stream.get("avg_frame_rate") or stream.get("r_frame_rate")
    if fps_str and "/" in fps_str:
        try:
            num, den = fps_str.split("/")
            den_f = float(den)
            if den_f > 0:
                v["fps"] = round(float(num) / den_f, 3)
        except (ValueError, ZeroDivisionError):
            pass
    elif fps_str:
        try:
            v["fps"] = float(fps_str)
        except (ValueError, TypeError):
            pass

    if stream.get("duration"):
        try:
            v["duration_seconds"] = float(stream["duration"])
        except (TypeError, ValueError):
            pass

    if stream.get("bit_rate"):
        try:
            v["bit_rate"] = int(stream["bit_rate"])
        except (TypeError, ValueError):
            pass

    return v


def _parse_audio_stream(stream: dict) -> Dict[str, Any]:
    """يحلّل تدفق صوت من ffprobe"""
    a: Dict[str, Any] = {}
    if stream.get("codec_name"):
        a["codec"] = stream["codec_name"]
    if stream.get("sample_rate"):
        try:
            a["sample_rate"] = int(stream["sample_rate"])
        except (TypeError, ValueError):
            pass
    if stream.get("channels"):
        try:
            a["channels"] = int(stream["channels"])
        except (TypeError, ValueError):
            pass
    if stream.get("channel_layout"):
        a["channel_layout"] = stream["channel_layout"]

    if stream.get("duration"):
        try:
            a["duration_seconds"] = float(stream["duration"])
        except (TypeError, ValueError):
            pass

    if stream.get("bit_rate"):
        try:
            a["bit_rate"] = int(stream["bit_rate"])
        except (TypeError, ValueError):
            pass

    return a


# ─── كشف نوع المحتوى (MIME) ────────────────────────────────────────────────

# قاموس احتياطي للامتدادات الشائعة (يُستخدم لو python-magic غير مثبت)
_EXT_MIME_FALLBACK: Dict[str, str] = {
    "txt": "text/plain", "md": "text/markdown", "csv": "text/csv",
    "log": "text/plain", "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
    "gif": "image/gif", "bmp": "image/bmp", "svg": "image/svg+xml",
    "webp": "image/webp", "tiff": "image/tiff", "tif": "image/tiff",
    "mp4": "video/mp4", "avi": "video/x-msvideo", "mkv": "video/x-matroska",
    "mov": "video/quicktime", "webm": "video/webm", "wmv": "video/x-ms-wmv",
    "flv": "video/x-flv",
    "mp3": "audio/mpeg", "wav": "audio/wav", "flac": "audio/flac",
    "aac": "audio/aac", "ogg": "audio/ogg", "wma": "audio/x-ms-wma",
    "m4a": "audio/mp4", "opus": "audio/opus",
    "zip": "application/zip", "rar": "application/vnd.rar", "7z": "application/x-7z-compressed",
    "tar": "application/x-tar", "gz": "application/gzip", "bz2": "application/x-bzip2",
    "py": "text/x-python", "js": "application/javascript", "ts": "application/typescript",
    "json": "application/json", "xml": "application/xml", "yaml": "application/x-yaml",
    "yml": "application/x-yaml", "html": "text/html", "htm": "text/html",
    "css": "text/css", "sh": "application/x-sh", "bash": "application/x-sh",
    "sql": "application/sql", "java": "text/x-java-source", "c": "text/x-c",
    "cpp": "text/x-c++", "h": "text/x-c", "hpp": "text/x-c++",
    "exe": "application/x-msdownload", "dll": "application/x-msdownload",
    "msi": "application/x-msi", "deb": "application/vnd.debian.binary-package",
    "rpm": "application/x-rpm",
    "ttf": "font/ttf", "otf": "font/otf", "woff": "font/woff", "woff2": "font/woff2",
    "iso": "application/x-iso9660-image", "img": "application/octet-stream",
    "bin": "application/octet-stream",
}


def detect_content_type(file_path: Path | str, ext: Optional[str] = None) -> str:
    """يكشف نوع محتوى الملف (MIME) عبر python-magic مع fallback للامتداد

    الأولوية:
      1. python-magic (يقرأ magic bytes من أول ~1KB من الملف)
      2. قاموس الامتدادات (لو magic غير مثبت أو فشل)

    Args:
        file_path: مسار الملف
        ext: الامتداد (مثل ".pdf" أو "pdf") — يُستخرج من المسار لو لم يُمرّر

    Returns:
        سلسلة MIME مثل "application/pdf" أو "application/octet-stream"
    """
    path = Path(file_path)

    # المحاولة 1: python-magic
    try:
        import magic
        m = magic.Magic(mime=True)
        mime = m.from_file(str(path))
        if mime and isinstance(mime, str) and "/" in mime:
            return mime
    except ImportError:
        logger.debug("python-magic غير مثبت — استخدام fallback للامتداد")
    except Exception as e:
        logger.debug(f"python-magic فشل على {path.name}: {e}")

    # المحاولة 2: fallback للامتداد
    if ext is None:
        ext = path.suffix
    ext_clean = ext.lower().lstrip(".")
    return _EXT_MIME_FALLBACK.get(ext_clean, "application/octet-stream")


# ─── واجهة موحّدة ───────────────────────────────────────────────────────────

# امتدادات الصور المدعومة
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tiff", ".tif"}

# امتدادات الصوت/الفيديو المدعومة (تُعالَج عبر ffprobe)
AV_EXTENSIONS = {
    # فيديو
    ".mp4", ".avi", ".mkv", ".mov", ".webm", ".wmv", ".flv", ".m4v",
    # صوت
    ".mp3", ".wav", ".flac", ".aac", ".ogg", ".wma", ".m4a", ".opus",
}


def extract_extended_metadata(file_path: Path | str, ext: Optional[str] = None) -> Dict[str, Any]:
    """واجهة موحّدة: تستدعي المستخرج المناسب حسب نوع الملف

    Args:
        file_path: مسار الملف
        ext: الامتداد (يُستخرج من المسار لو لم يُمرّر)

    Returns:
        قاموس بالميتاداتا الموسّعة. قد يكون فارغًا {} للملفات غير المدعومة
        (مثل txt/pdf/docx — لا ميتاداتا موسّعة لها).
    """
    path = Path(file_path)
    if ext is None:
        ext = path.suffix.lower()

    if ext in IMAGE_EXTENSIONS:
        return extract_image_metadata(path)
    if ext in AV_EXTENSIONS:
        return extract_av_metadata(path)
    # الملفات الأخرى (txt, pdf, docx, xlsx, pptx, code, archives) ليس لها ميتاداتا موسّعة
    return {}
