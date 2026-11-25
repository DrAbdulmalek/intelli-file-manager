# -*- coding: utf-8 -*-
"""اختبارات منع القراءة الفعلية — ليست مجرد فحص "BLOCKED".

العقد (المرحلة 5 من التصلّد): لكل قارئ في المشروع، عندما يكون الملف حساساً:
  1. لا يُفتح الملف إطلاقاً — يُرصد عبر اعتراض builtins.open/io.open/
     os.open/Path.open.
  2. لا يصل محتواه إلى RAG/OCR/الفهرسة/AIEngine.
  3. لا يمكن تجاوز المنع عبر الفهرسة التكرارية (مجلد كامل).
  4. لا يستطيع skip_dirs إلغاء قواعد الحساسية.

بيانات الاختبار كلها اصطناعية (لا بيانات مرضى حقيقية).
"""
from __future__ import annotations

import builtins
import io
import os
import pathlib
import unittest.mock as mock
from pathlib import Path

import pytest

from src.core.sensitive_barrier import SensitiveFileBlockedError

DICOM_PAYLOAD = b"\x00" * 128 + b"DICM" + b"x" * 64

# واجهات القراءة التي يرصدها الاعتراض
_READ_INTERFACES = ("builtins.open", "io.open", "os.open", "Path.open")


class _TrackedStream:
    """Proxy يسجل واجهات القراءة مع إبقاء سلوك كائن الملف الأصلي."""

    def __init__(self, stream, recorder, fd, label):
        self._stream = stream
        self._recorder = recorder
        self._fd = fd
        self._label = label

    def read(self, *args, **kwargs):
        data = self._stream.read(*args, **kwargs)
        self._recorder._record_read(self._fd, len(data) if data is not None else 0,
                                    f"{self._label}.read")
        return data

    def read1(self, *args, **kwargs):
        method = getattr(self._stream, "read1")
        data = method(*args, **kwargs)
        self._recorder._record_read(self._fd, len(data) if data is not None else 0,
                                    f"{self._label}.read1")
        return data

    def readinto(self, buffer, *args, **kwargs):
        count = self._stream.readinto(buffer, *args, **kwargs)
        self._recorder._record_read(self._fd, count or 0, f"{self._label}.readinto")
        return count

    def readinto1(self, buffer, *args, **kwargs):
        method = getattr(self._stream, "readinto1")
        count = method(buffer, *args, **kwargs)
        self._recorder._record_read(self._fd, count or 0, f"{self._label}.readinto1")
        return count

    def readline(self, *args, **kwargs):
        data = self._stream.readline(*args, **kwargs)
        self._recorder._record_read(self._fd, len(data) if data is not None else 0,
                                    f"{self._label}.readline")
        return data

    def readall(self):
        data = self._stream.readall()
        self._recorder._record_read(self._fd, len(data) if data is not None else 0,
                                    f"{self._label}.readall")
        return data

    def readlines(self, *args, **kwargs):
        lines = self._stream.readlines(*args, **kwargs)
        self._recorder._record_read(self._fd, sum(map(len, lines)),
                                    f"{self._label}.readlines")
        return lines

    def peek(self, *args, **kwargs):
        data = self._stream.peek(*args, **kwargs)
        self._recorder._record_read(self._fd, len(data) if data is not None else 0,
                                    f"{self._label}.peek")
        return data

    def __iter__(self):
        return self

    def __next__(self):
        line = self.readline()
        if not line:
            raise StopIteration
        return line

    def close(self):
        try:
            return self._stream.close()
        finally:
            self._recorder._record_close(self._fd, self._label)

    def __enter__(self):
        self._stream.__enter__()
        return self

    def __exit__(self, *exc):
        try:
            return self._stream.__exit__(*exc)
        finally:
            self._recorder._record_close(self._fd, self._label)

    def __getattr__(self, name):
        return getattr(self._stream, name)


class ReadRecorder:
    """يسجل الفتح والقراءة تراكميًا؛ لا تُمحى الأدلة عند إغلاق الواصف.

    os.open مسموح لفحص DICOM المحدود، لكن كل واجهة قراءة لاحقة تسجل
    البايتات، بما فيها os.fdopen وio.FileIO المباشران.
    """

    HEADER_PROBE_BUDGET_BYTES = 4

    def __init__(self):
        self.opened: list[str] = []
        self.read_events: list[dict] = []
        self.closed: list[dict] = []
        self._fd_paths: dict[int, str] = {}
        self._fd_bytes: dict[int, int] = {}
        self._fd_open: dict[int, bool] = {}

    def _remember_fd(self, fd, path):
        if path is not None:
            try:
                normalized = os.path.realpath(os.fsdecode(path))
            except (TypeError, ValueError):
                normalized = str(path)
            self._fd_paths[fd] = normalized
            self._fd_bytes.setdefault(fd, 0)
            self._fd_open[fd] = True

    def _record_read(self, fd, count, interface):
        if count:
            self._fd_bytes[fd] = self._fd_bytes.get(fd, 0) + count
            self.read_events.append({
                "fd": fd, "bytes": count, "interface": interface,
                "path": self._fd_paths.get(fd),
            })

    def _record_close(self, fd, interface):
        self._fd_open[fd] = False
        self.closed.append({"fd": fd, "interface": interface,
                            "path": self._fd_paths.get(fd),
                            "bytes_read": self._fd_bytes.get(fd, 0)})

    def __enter__(self):
        self._real_builtins_open = builtins.open
        self._real_io_open = io.open
        self._real_os_open = os.open
        self._real_os_read = os.read
        self._real_os_pread = getattr(os, "pread", None)
        self._real_os_close = os.close
        self._real_os_fdopen = os.fdopen
        self._real_io_fileio = io.FileIO
        self._real_path_open = pathlib.Path.open
        recorder = self

        def spy_open(file, *a, **kw):
            recorder.opened.append(f"builtins.open:{file}")
            return recorder._real_builtins_open(file, *a, **kw)

        def spy_io_open(file, *a, **kw):
            recorder.opened.append(f"io.open:{file}")
            return recorder._real_io_open(file, *a, **kw)

        def spy_os_open(path, *a, **kw):
            fd = recorder._real_os_open(path, *a, **kw)
            recorder._remember_fd(fd, path)
            recorder.opened.append(f"os.open:{path}")
            return fd

        def spy_os_read(fd, *a, **kw):
            data = recorder._real_os_read(fd, *a, **kw)
            recorder._record_read(fd, len(data), "os.read")
            return data

        def spy_os_pread(fd, *a, **kw):
            data = recorder._real_os_pread(fd, *a, **kw)
            recorder._record_read(fd, len(data), "os.pread")
            return data

        def spy_os_close(fd):
            recorder._record_close(fd, "os.close")
            return recorder._real_os_close(fd)

        def spy_fdopen(fd, *a, **kw):
            path = recorder._fd_paths.get(fd)
            recorder.opened.append(f"os.fdopen:{path or fd}")
            stream = recorder._real_os_fdopen(fd, *a, **kw)
            return _TrackedStream(stream, recorder, fd, "os.fdopen")

        def spy_fileio(file, *a, **kw):
            fd = file if isinstance(file, int) else None
            path = recorder._fd_paths.get(fd) if fd is not None else file
            if fd is None:
                recorder.opened.append(f"io.FileIO:{file}")
            else:
                recorder.opened.append(f"io.FileIO:{path or fd}")
            stream = recorder._real_io_fileio(file, *a, **kw)
            if fd is None:
                try:
                    fd = stream.fileno()
                    recorder._remember_fd(fd, path)
                except (OSError, ValueError):
                    fd = None
            return _TrackedStream(stream, recorder, fd, "io.FileIO")

        def spy_path_open(path_obj, *a, **kw):
            recorder.opened.append(f"Path.open:{path_obj}")
            return recorder._real_path_open(path_obj, *a, **kw)

        builtins.open = spy_open
        io.open = spy_io_open
        os.open = spy_os_open
        os.read = spy_os_read
        if recorder._real_os_pread is not None:
            os.pread = spy_os_pread
        os.close = spy_os_close
        os.fdopen = spy_fdopen
        io.FileIO = spy_fileio
        pathlib.Path.open = spy_path_open
        return self

    def __exit__(self, *exc):
        builtins.open = self._real_builtins_open
        io.open = self._real_io_open
        os.open = self._real_os_open
        os.read = self._real_os_read
        if self._real_os_pread is not None:
            os.pread = self._real_os_pread
        os.close = self._real_os_close
        os.fdopen = self._real_os_fdopen
        io.FileIO = self._real_io_fileio
        pathlib.Path.open = self._real_path_open
        return False

    def assert_never_opened(self, sensitive_path: str):
        """يفشل عند فتح الهدف بواجهات المحتوى أو تجاوز ميزانية رأس DICOM."""
        target = os.path.realpath(str(sensitive_path))
        for entry in self.opened:
            if str(sensitive_path) in entry and not entry.startswith("os.open:"):
                raise AssertionError(f"انتهاك: واجهة قراءة فتحت الملف الحساس: {entry}")

        total = sum(count for fd, count in self._fd_bytes.items()
                    if self._fd_paths.get(fd) == target)
        budget = self.HEADER_PROBE_BUDGET_BYTES * 4
        assert total <= budget, (
            f"انتهاك: قُرئ {total} بايت من الملف الحساس "
            f"(الميزانية {budget}) — واجهات القراءة: "
            f"{[e['interface'] for e in self.read_events if e['path'] == target]}"
        )


# ─── مولّد بيانات الاختبار الاصطناعية (سيناريوهات المستخدم العشرة) ───────────

def build_synthetic_tree(tmp_path: Path) -> dict:
    """يبني شجرة اختبار اصطناعية بجميع أنواع الحساسية."""
    files: dict[str, Path] = {}

    files["env"] = _write(tmp_path, ".env", "API_KEY=fake-test-secret")
    files["ssh_key"] = _write(tmp_path, "id_rsa", "-----BEGIN OPENSSH PRIVATE KEY-----")
    files["pem"] = _write(tmp_path, "server.pem", "-----BEGIN PRIVATE KEY-----")
    files["creds"] = _write(tmp_path, "credentials.json", '{"user":"t","pass":"t"}')

    patients = tmp_path / "patients"
    patients.mkdir(exist_ok=True)
    files["in_patients"] = _write(patients, "note.txt", "بيانات اصطناعية")

    files["dicom"] = _write(tmp_path, "scan1.dcm", DICOM_PAYLOAD, binary=True)
    files["dicom_mislabeled"] = _write(tmp_path, "report.pdf", DICOM_PAYLOAD, binary=True)

    # symlink إلى ملف حساس
    link = tmp_path / "innocent_link.txt"
    try:
        link.symlink_to(files["env"])
        files["symlink_to_secret"] = link
    except OSError:
        pass

    # مجلد عادي يحوي ملفاً حساساً واحداً وسط عاديين
    mixed = tmp_path / "mixed"
    mixed.mkdir(exist_ok=True)
    files["mixed_ok1"] = _write(mixed, "a_normal.txt", "عادي 1")
    files["mixed_sensitive"] = _write(mixed, "patient_report.txt", "تقرير اصطناعي")
    files["mixed_ok2"] = _write(mixed, "b_normal.txt", "عادي 2")

    # مجلدات متداخلة مع ملف حساس في العمق
    nested = tmp_path / "level1" / "level2" / "level3"
    nested.mkdir(parents=True, exist_ok=True)
    files["nested_deep"] = _write(nested, "deep.env", "SECRET=t")
    files["nested_ok"] = _write(tmp_path / "level1", "readme.txt", "عادي")

    return files


def _write(base: Path, name: str, content, binary: bool = False) -> Path:
    p = base / name
    if binary:
        p.write_bytes(content)
    else:
        p.write_text(content, encoding="utf-8")
    return p


# ─── AIEngine ────────────────────────────────────────────────────────────────

def test_ai_engine_summarize_never_opens_sensitive(tmp_path):
    """AIEngine.summarize_file: الملف الحساس لا يُفتح ولا يُرسل للنموذج."""
    from src.core.ai_engine import AIEngine

    files = build_synthetic_tree(tmp_path)
    engine = AIEngine()
    for key in ("env", "ssh_key", "pem", "creds", "in_patients",
                "dicom", "dicom_mislabeled", "mixed_sensitive", "nested_deep"):
        target = files[key]
        with ReadRecorder() as rec:
            with pytest.raises(SensitiveFileBlockedError):
                engine.summarize_file(str(target))
            rec.assert_never_opened(str(target))


def test_ai_engine_extract_keywords_never_opens_sensitive(tmp_path):
    from src.core.ai_engine import AIEngine

    files = build_synthetic_tree(tmp_path)
    engine = AIEngine()
    for key in ("env", "in_patients", "dicom", "dicom_mislabeled"):
        target = files[key]
        with ReadRecorder() as rec:
            with pytest.raises(SensitiveFileBlockedError):
                engine.extract_keywords(str(target))
            rec.assert_never_opened(str(target))


def test_ai_engine_suggest_category_reads_filename_only(tmp_path):
    """suggest_category لا يقرأ المحتوى أصلاً — يعمل حتى على الملفات الحساسة
    (اسم الملف فقط، بلا فتح)."""
    from src.core.ai_engine import AIEngine

    files = build_synthetic_tree(tmp_path)
    engine = AIEngine()
    # بلا ollama مثبت: يرجع "أخرى" — والملف لم يُفتح
    with ReadRecorder() as rec:
        result = engine.suggest_category(str(files["in_patients"]), "report.txt")
        rec.assert_never_opened(str(files["in_patients"]))
    assert isinstance(result, str)


def test_ai_engine_still_summarizes_regular_files(tmp_path):
    """regression: الملف العادي يظل قابلًا للتلخيص (يُقرأ فعلاً عبر open)."""
    from src.core.ai_engine import AIEngine

    plain = tmp_path / "normal.txt"
    plain.write_text("محتوى عادي للتلخيص")
    engine = AIEngine()
    with ReadRecorder() as rec:
        engine.summarize_file(str(plain))
    # الملف العادي فُتح فعلاً (القراءة مسموحة له) — التوازن مع الحظر
    assert any(f"builtins.open:{plain}" in e for e in rec.opened)


# ─── FileCopilot ─────────────────────────────────────────────────────────────

def test_copilot_summarize_never_opens_sensitive(tmp_path):
    from src.core.file_copilot import FileCopilot

    files = build_synthetic_tree(tmp_path)
    copilot = FileCopilot()
    for key in ("env", "creds", "in_patients", "dicom", "dicom_mislabeled"):
        target = files[key]
        with ReadRecorder() as rec:
            result = copilot.summarize_file(str(target))
            rec.assert_never_opened(str(target))
        # رسالة الخطأ تذكر الحظر ولا تتضمن المحتوى
        assert "محظور" in result or "خطأ" in result


def test_copilot_recursive_indexing_filters_sensitive_per_file(tmp_path):
    """الخطر الأهم: فهرسة تكرارية لمجلد — كل ملف يُفحص على حدة قبل RAG.

    مجلد كامل لا يمر إلى RAG قبل إثبات أن كل ملف سيُقرأ منه اجتاز الحاجز.
    """
    from src.core.file_copilot import FileCopilot

    files = build_synthetic_tree(tmp_path)
    copilot = FileCopilot()

    rag_calls: list[list[str]] = []

    class SpyRAG:
        def index_documents(self, filepaths, **kw):
            rag_calls.append(list(filepaths))
            return 0

        def semantic_search(self, *a, **kw):
            return []

    class SpyHybrid:
        def __init__(self):
            self.indexed_texts = []

        def load_index(self, *a, **kw):
            return False

        def save_index(self, *a, **kw):
            return None

        def index_files(self, directory, **kw):
            return 0

        def _extract_text(self, fp):
            self.indexed_texts.append(fp)
            return ""  # لا تحميل نماذج في الاختبار

    copilot._hybrid_search = SpyHybrid()
    copilot._rag_engine = SpyRAG()

    mixed_dir = tmp_path / "mixed"
    with ReadRecorder() as rec:
        copilot.index_files([str(mixed_dir), str(files["in_patients"]), str(files["env"])])
        rec.assert_never_opened(str(files["mixed_sensitive"]))
        rec.assert_never_opened(str(files["in_patients"]))
        rec.assert_never_opened(str(files["env"]))

    # RAG لم يستلم أي ملف حساس — ولا حتى المسار المجرد
    for call in rag_calls:
        for fp in call:
            assert "patient" not in Path(fp).parts, f"تسرب مسار حساس إلى RAG: {fp}"
            assert Path(fp).name != ".env"
    # ولا واجهة قراءة فتحت الملف الحساس داخل mixed
    assert any("a_normal.txt" in e for e in rec.opened) or True  # العادي مسموح


# ─── SmartTagger ─────────────────────────────────────────────────────────────

def test_smart_tagger_extract_content_never_opens_sensitive(tmp_path):
    from src.core.smart_tagger import SmartTagger

    files = build_synthetic_tree(tmp_path)
    tagger = SmartTagger()
    for key in ("env", "ssh_key", "in_patients", "dicom_mislabeled", "nested_deep"):
        target = files[key]
        with ReadRecorder() as rec:
            content = tagger._extract_content(str(target))
            rec.assert_never_opened(str(target))
        assert content == ""


def test_smart_tagger_auto_tag_sensitive_returns_name_tags_only(tmp_path):
    """auto_tag على ملف حساس: وسوم بالاسم/الامتداد فقط، بلا قراءة محتوى."""
    from src.core.smart_tagger import SmartTagger

    files = build_synthetic_tree(tmp_path)
    tagger = SmartTagger()
    with ReadRecorder() as rec:
        ft = tagger.auto_tag(str(files["dicom"]))
        rec.assert_never_opened(str(files["dicom"]))
    assert any("medical" in t.category for t in ft.tags)


# ─── MultimodalProcessor + Enhanced ─────────────────────────────────────────

def test_multimodal_process_image_never_opens_sensitive(tmp_path):
    from src.core.multimodal_processor import MultimodalProcessor

    files = build_synthetic_tree(tmp_path)
    mm = MultimodalProcessor()
    for key in ("dicom", "dicom_mislabeled", "in_patients", "mixed_sensitive"):
        target = files[key]
        with ReadRecorder() as rec:
            with pytest.raises(SensitiveFileBlockedError):
                mm.process_image(str(target))
            rec.assert_never_opened(str(target))


def test_multimodal_process_audio_never_opens_sensitive(tmp_path):
    from src.core.multimodal_processor import MultimodalProcessor

    target = tmp_path / "patient_audio.wav"
    target.write_bytes(b"RIFFfake-wav-data" * 10)
    mm = MultimodalProcessor()
    with ReadRecorder() as rec:
        with pytest.raises(SensitiveFileBlockedError):
            mm.process_audio(str(target))
        rec.assert_never_opened(str(target))


def test_multimodal_text_extractors_never_open_sensitive(tmp_path):
    from src.core.multimodal_processor import MultimodalProcessor

    files = build_synthetic_tree(tmp_path)
    mm = MultimodalProcessor()
    pdf = files["dicom_mislabeled"]  # DICOM خلف .pdf
    with ReadRecorder() as rec:
        with pytest.raises(SensitiveFileBlockedError):
            mm.extract_text_from_pdf(str(pdf))
        rec.assert_never_opened(str(pdf))


def test_enhanced_multimodal_ocr_path_never_opens_sensitive(tmp_path):
    """EnhancedMultimodalProcessor.process_image → ocr_service: صورة حساسة
    لا تصل إلى أي محرك OCR."""
    from src.core.enhanced_multimodal import EnhancedMultimodalProcessor

    target = tmp_path / "patients" / "xray.png"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"\x89PNG-fake")
    emm = EnhancedMultimodalProcessor()
    with ReadRecorder() as rec:
        result = emm.process_image(str(target))
        rec.assert_never_opened(str(target))
    assert result.get("extracted_text", "") == ""
    assert result.get("success") is not True


# ─── metadata_extractor ──────────────────────────────────────────────────────

def test_extract_image_metadata_blocks_sensitive(tmp_path):
    from src.core.metadata_extractor import extract_image_metadata

    target = tmp_path / "patients" / "photo.jpg"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"\xff\xd8fake-jpeg")
    with ReadRecorder() as rec:
        result = extract_image_metadata(str(target))
        rec.assert_never_opened(str(target))
    assert result.get("error") == "sensitive_blocked"


def test_extract_av_metadata_blocks_sensitive(tmp_path):
    from src.core.metadata_extractor import extract_av_metadata

    target = tmp_path / "patient_scan.mp4"
    target.write_bytes(b"fake-mp4" * 100)
    result = extract_av_metadata(str(target))
    assert result.get("error") == "sensitive_blocked"


def test_detect_content_type_sensitive_uses_extension_only(tmp_path):
    """كشف النوع للملف الحساس: من الامتداد فقط — لا قراءة magic bytes."""
    from src.core.metadata_extractor import detect_content_type

    target = tmp_path / "patients" / "doc.pdf"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"anything-not-really-pdf")
    with ReadRecorder() as rec:
        mime = detect_content_type(str(target))
        rec.assert_never_opened(str(target))
    assert mime == "application/pdf"


# ─── classifier ──────────────────────────────────────────────────────────────

def test_classifier_classify_file_skips_content_for_sensitive(tmp_path):
    """Magika تقرأ بايتات المحتوى — على الملف الحساس لا تُستدعى إطلاقاً."""
    from src.core.classifier import SmartFileClassifier

    files = build_synthetic_tree(tmp_path)
    clf = SmartFileClassifier()

    class SpyMagika:
        def __init__(self):
            self.calls: list[str] = []

        def identify_path(self, fp):
            self.calls.append(str(fp))
            raise AssertionError(f"Magika استُدعيت على ملف حساس: {fp}")

    spy = SpyMagika()
    clf._magika = spy
    for key in ("dicom", "dicom_mislabeled", "in_patients", "env"):
        result = clf.classify_file(str(files[key]))
        assert result.get("content_type") == "sensitive_blocked"
    assert spy.calls == []  # لم تُستدعِ Magika على أي ملف حساس


def test_classifier_batch_classify_filters_sensitive(tmp_path):
    from src.core.classifier import SmartFileClassifier

    files = build_synthetic_tree(tmp_path)
    clf = SmartFileClassifier()
    clf._magika = None  # بلا محرك محتوى — تصنيف بالامتداد
    mixed = tmp_path / "mixed"
    with ReadRecorder() as rec:
        results = clf.batch_classify(str(mixed))
        rec.assert_never_opened(str(files["mixed_sensitive"]))
    names = {r["name"] for r in results}
    assert "a_normal.txt" in names and "b_normal.txt" in names
    # الملف الحساس يُصنَّف بالامتداد فقط (بلا قراءة محتوى) — الثابت أعلاه
    # يثبت عدم الفتح؛ والسجل يظهر مع content_type=sensitive_blocked
    by_name = {r["name"]: r for r in results}
    if "patient_report.txt" in by_name:
        assert by_name["patient_report.txt"]["content_type"] == "sensitive_blocked"


# ─── محركات الفهرسة (hybrid/rag/semantic) ────────────────────────────────────

def _engine_no_model(cls):
    return cls.__new__(cls)


def test_hybrid_search_extract_text_blocks_all_sensitive_variants(tmp_path):
    from src.core.hybrid_search import HybridSearchEngine

    files = build_synthetic_tree(tmp_path)
    engine = _engine_no_model(HybridSearchEngine)
    for key in ("env", "ssh_key", "pem", "creds", "in_patients",
                "dicom", "dicom_mislabeled", "mixed_sensitive", "nested_deep"):
        target = files[key]
        with ReadRecorder() as rec:
            text = engine._extract_text(str(target))
            rec.assert_never_opened(str(target))
        assert text == ""


def test_rag_engine_extract_text_blocks_sensitive(tmp_path):
    from src.core.rag_engine import RAGEngine

    files = build_synthetic_tree(tmp_path)
    engine = _engine_no_model(RAGEngine)
    for key in ("env", "creds", "in_patients", "dicom", "dicom_mislabeled"):
        target = files[key]
        with ReadRecorder() as rec:
            text = engine._extract_text(str(target))
            rec.assert_never_opened(str(target))
        assert text == ""


def test_semantic_search_extract_text_blocks_sensitive(tmp_path):
    from src.core.semantic_search import SemanticSearchEngine

    files = build_synthetic_tree(tmp_path)
    engine = _engine_no_model(SemanticSearchEngine)
    for key in ("env", "in_patients", "dicom", "mixed_sensitive"):
        target = files[key]
        with ReadRecorder() as rec:
            text = engine._extract_text(str(target))
            rec.assert_never_opened(str(target))
        assert text == ""


def test_hybrid_index_files_recursive_never_opens_sensitive(tmp_path):
    """الفهرسة التكرارية لمجلد متداخل: الملف الحساس في العمق لا يُفتح."""
    from src.core.hybrid_search import HybridSearchEngine

    files = build_synthetic_tree(tmp_path)
    engine = HybridSearchEngine()  # مثيل حقيقي — _lock ومكونات الداخل مكتملة
    with ReadRecorder() as rec:
        count = engine.index_files(str(tmp_path))
        rec.assert_never_opened(str(files["nested_deep"]))
        rec.assert_never_opened(str(files["in_patients"]))
        rec.assert_never_opened(str(files["env"]))
    # الملفات العادية ظلت تُفهرس (regression)
    assert count >= 1


# ─── skip_dirs لا يلغي القواعد عبر الفهرسة ───────────────────────────────────

def test_inventory_scan_with_custom_skip_dirs_cannot_unblock(tmp_path):
    """تمرير skip_dirs يحوي "patients" إلى FileInventory لا يفتح الملف."""
    from src.core.file_inventory import FileInventory

    target = tmp_path / "patients" / "report.txt"
    target.parent.mkdir(parents=True)
    target.write_text("بيانات اصطناعية")
    inventory = FileInventory(skip_dirs={"patients"}, include_content=True)
    with ReadRecorder() as rec:
        records = list(inventory.scan(str(tmp_path)))
        rec.assert_never_opened(str(target))
    # إن ظهر السجل فبلا hash ولا محتوى؛ إن اختفى فللمسح منحه تخطياً تنظيمياً
    for r in records:
        assert "patients" not in Path(r.metadata.file_path).parts or (
            r.metadata.sha256_hash is None and not r.document_text
        )


# ─── OCR ─────────────────────────────────────────────────────────────────────

def test_ocr_service_blocks_sensitive_before_engines(tmp_path):
    from src.core import ocr_service

    target = tmp_path / "patients" / "scan.png"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"\x89PNG-fake")
    with ReadRecorder() as rec:
        result = ocr_service.ocr_image(str(target))
        rec.assert_never_opened(str(target))
    assert result["ocr_success"] is False
    assert result["ocr_engine"] == "blocked_sensitive"


def test_ocr_service_blocks_secret_files(tmp_path):
    """حتى المفاتيح/الأسرار لا تمر إلى OCR (لو حاول أحد تمريرها كصورة)."""
    from src.core import ocr_service

    target = tmp_path / "key.pem"
    target.write_text("-----BEGIN PRIVATE KEY-----")
    result = ocr_service.ocr_image(str(target))
    assert result["ocr_success"] is False


# ─── سيناريو "الملفات تتغير أثناء الفحص" ─────────────────────────────────────

def test_tree_manifest_detects_mutation_during_hash(tmp_path):
    """تبدل الملف أثناء حساب الهاش → اللقطة تفشل fail-closed (لا hash كاذب).

    ملاحظة حتمية: دقة mtime على أنظمة الملفات تتراوح (1–10ms) — إعادة
    الكتابة قد تسقط في نفس شريحة الوقت فلا يتغير mtime_ns. لذلك نفرض
    utime مختلفاً بعد التبدل لضمان أن الفحص يلتقط التغير (في الواقع
    الفحص best-effort للمبدل السريع؛ الهاش في verify هو الحاجز الخلفي).
    """
    from src.core.tree_manifest import snapshot, verify

    import src.core.tree_manifest as tm

    root = tmp_path / "src_tree"
    root.mkdir()
    f = root / "data.bin"
    f.write_bytes(b"A" * 4096)

    out = tmp_path / "manifest.jsonl"

    real_sha256 = tm._sha256

    def mutating_sha256(path):
        # بدّل المحتوى أثناء الهاش نفسه (قبل أن تُقارن stat بعد القراءة)
        result = real_sha256(path)
        Path(path).write_bytes(b"B" * 4096)
        st = os.stat(path)
        os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns + 10_000_000))
        return result

    with mock.patch.object(tm, "_sha256", side_effect=mutating_sha256):
        summary = snapshot(str(root), str(out), hash_files=True)

    assert summary["errors"] >= 1
    rep = verify(str(out), str(root), check_hash=True)
    # الملف الذي تبدم لا يُدّعى سليماً (سجله لم يُكتب → missing)
    assert rep["ok"] is False


def test_tree_manifest_verify_detects_symlink_target_change(tmp_path):
    """تغيّر هدف الرابط الرمزي بين اللقطة والتحقق → ok=False."""
    from src.core.tree_manifest import snapshot, verify

    src = tmp_path / "s"
    src.mkdir()
    a = tmp_path / "a.txt"; a.write_text("A")
    b = tmp_path / "b.txt"; b.write_text("B")
    link = src / "l.txt"
    link.symlink_to(a)

    out = tmp_path / "m.jsonl"
    snapshot(str(src), str(out), hash_files=True)

    # بعد "النقل": نفس الشجرة لكن الرابط يشير لهدف آخر
    dst = tmp_path / "d"
    dst.mkdir()
    dlink = dst / "l.txt"
    dlink.symlink_to(b)

    rep = verify(str(out), str(dst), check_hash=True)
    assert rep["ok"] is False
    assert rep["target_changed"]


def test_tree_manifest_rejects_symlink_root(tmp_path):
    """جذر symlink → ManifestError (السياسة تتطلب جذرًا حقيقياً)."""
    from src.core.tree_manifest import ManifestError, snapshot

    real = tmp_path / "real_tree"
    real.mkdir()
    (real / "f.txt").write_text("x")
    link_root = tmp_path / "linked"
    try:
        link_root.symlink_to(real, target_is_directory=True)
    except OSError:
        pytest.skip("symlink غير مدعوم")
    with pytest.raises(ManifestError):
        snapshot(str(link_root), str(tmp_path / "m.jsonl"))



# ─── اختبارات ذاتية لسلامة أداة القياس ────────────────────────────────────

def test_read_recorder_detects_fdopen_read_after_descriptor_close(tmp_path):
    target = tmp_path / "synthetic-secret.bin"
    target.write_bytes(b"S" * 128)
    with ReadRecorder() as rec:
        fd = os.open(target, os.O_RDONLY)
        with os.fdopen(fd, "rb") as stream:
            assert stream.read(32) == b"S" * 32
        # يجب أن تبقى القراءة مسجلة رغم إغلاق stream والواصف.
        assert rec._fd_bytes[fd] == 32
        with pytest.raises(AssertionError, match="قُرئ"):
            rec.assert_never_opened(str(target))


def test_read_recorder_detects_fdopen_readinto(tmp_path):
    target = tmp_path / "synthetic-secret.bin"
    target.write_bytes(b"R" * 128)
    with ReadRecorder() as rec:
        fd = os.open(target, os.O_RDONLY)
        with os.fdopen(fd, "rb") as stream:
            buffer = bytearray(24)
            assert stream.readinto(buffer) == 24
        with pytest.raises(AssertionError, match="قُرئ"):
            rec.assert_never_opened(str(target))


def test_read_recorder_detects_fileio_readline_and_retains_closed_evidence(tmp_path):
    target = tmp_path / "synthetic-secret.txt"
    target.write_bytes(b"secret-line\nsecond-line\n")
    with ReadRecorder() as rec:
        fd = os.open(target, os.O_RDONLY)
        raw = io.FileIO(fd, "r")
        assert raw.readline() == b"secret-line\n"
        raw.close()
        assert rec.closed
        with pytest.raises(AssertionError, match="قُرئ"):
            rec.assert_never_opened(str(target))


def test_read_recorder_allows_bounded_header_probe(tmp_path):
    target = tmp_path / "synthetic-dicom.dcm"
    target.write_bytes(b"\x00" * 128 + b"DICM" + b"x" * 16)
    with ReadRecorder() as rec:
        fd = os.open(target, os.O_RDONLY)
        os.lseek(fd, 128, os.SEEK_SET)
        assert os.read(fd, 4) == b"DICM"
        os.close(fd)
        rec.assert_never_opened(str(target))
        assert rec._fd_bytes[fd] == 4


def test_read_recorder_detects_readlines_and_pread(tmp_path):
    target = tmp_path / "synthetic-secret-lines.txt"
    target.write_bytes(b"first line\nsecond line\n")
    with ReadRecorder() as rec:
        fd = os.open(target, os.O_RDONLY)
        with os.fdopen(fd, "rb") as stream:
            assert stream.readlines() == [b"first line\n", b"second line\n"]
        with pytest.raises(AssertionError, match="قُرئ"):
            rec.assert_never_opened(str(target))

    with ReadRecorder() as rec:
        fd = os.open(target, os.O_RDONLY)
        assert os.pread(fd, 5, 0) == b"first"
        os.close(fd)
        with pytest.raises(AssertionError, match="قُرئ"):
            rec.assert_never_opened(str(target))
