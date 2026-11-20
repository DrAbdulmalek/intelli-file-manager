"""اختبارات محرك البحث الهجين"""
import pytest
from src.core.hybrid_search import BM25Engine, SemanticSearchEngineV2, HybridSearchEngine, _normalize_arabic, _tokenize


class TestArabicNormalization:
    """اختبارات تطبيع النص العربي"""

    def test_normalize_alef(self):
        assert _normalize_arabic("إبراهيم") == "ابراهيم"
        assert _normalize_arabic("أحمد") == "احمد"
        assert _normalize_arabic("آدم") == "ادم"

    def test_normalize_taa_marbuta(self):
        assert _normalize_arabic("مدرسة") == "مدرسه"

    def test_normalize_yaa(self):
        assert _normalize_arabic("موسى") == "موسي"


class TestTokenize:
    """اختبارات تقسيم النص"""

    def test_arabic_tokens(self):
        tokens = _tokenize("المريض يعاني من كسر في عظم الفخذ")
        assert "المريض" in tokens
        assert "كسر" in tokens

    def test_english_tokens(self):
        tokens = _tokenize("patient has a fracture")
        assert "patient" in tokens
        assert "fracture" in tokens

    def test_mixed_tokens(self):
        tokens = _tokenize("Diabetes سكري")
        assert "diabetes" in tokens
        assert "سكري" in tokens


class TestBM25Engine:
    """اختبارات محرك BM25"""

    def test_add_documents(self):
        engine = BM25Engine()
        engine.add_documents([
            "المريض يعاني من كسر في عظم الفخذ",
            "تقرير أشعة صدر للمريض",
            "وصفة دواء باراسيتامول 500 ملغ",
        ])
        assert engine.document_count == 3

    def test_search_arabic(self):
        engine = BM25Engine()
        engine.add_documents([
            "المريض يعاني من كسر في عظم الفخذ",
            "تقرير أشعة صدر للمريض",
            "وصفة دواء باراسيتامول 500 ملغ",
        ])
        results = engine.search("كسر عظم")
        assert len(results) > 0
        # The first document should be the best match
        assert results[0][0] == 0

    def test_search_english(self):
        engine = BM25Engine()
        engine.add_documents([
            "Patient has a bone fracture",
            "Chest X-ray report",
            "Prescription paracetamol 500mg",
        ])
        results = engine.search("fracture")
        assert len(results) > 0
        assert results[0][0] == 0

    def test_empty_search(self):
        engine = BM25Engine()
        engine.add_documents(["مستند طبي"])
        results = engine.search("غير موجود")
        # May return 0 results if no match
        assert isinstance(results, list)

    def test_empty_engine(self):
        engine = BM25Engine()
        results = engine.search("أي شيء")
        assert results == []


class TestHybridSearchEngine:
    """اختبارات محرك البحث الهجين"""

    def test_init(self):
        engine = HybridSearchEngine()
        assert engine.bm25 is not None
        assert engine.semantic is not None
        assert engine.rrf_k == 60

    def test_extract_text_txt(self, tmp_path):
        # Create a temp text file
        txt_file = tmp_path / "test.txt"
        txt_file.write_text("محتوى طبي عربي", encoding="utf-8")
        engine = HybridSearchEngine()
        text = engine._extract_text(str(txt_file))
        assert "محتوى طبي عربي" in text

    def test_extract_text_pdf_missing(self, tmp_path):
        # Non-existent PDF should return empty string (was: filename, which
        # indexed filenames as document text — see PR #39 Kimi review fix).
        engine = HybridSearchEngine()
        text = engine._extract_text(str(tmp_path / "nonexistent.pdf"))
        assert text == ""


class TestArabicNormalizationExtended:
    """إزالة التشكيل والتطويل عند التطبيع (مراجعة كيمي — تحسينات صغيرة)"""

    def test_strip_diacritics_and_tatweel(self):
        assert _normalize_arabic("تقريرٌ") == _normalize_arabic("تقرير")
        assert _normalize_arabic("مُحَمَّد") == _normalize_arabic("محمد")
        assert _normalize_arabic("طــويل") == _normalize_arabic("طويل")

    def test_diacritics_match_in_bm25(self):
        engine = BM25Engine()
        engine.add_documents(["تقريرٌ طبي مهم"])
        results = engine.search("تقرير")
        assert len(results) == 1
        assert results[0][0] == 0

    def test_definite_article_documented_limitation(self):
        # موثَّق (مراجعة كيمي 2026-11): BM25 القياسي لا يزيل أداة التعريف "ال"،
        # فالاستعلام "التقرير" لا يطابق الوثيقة "تقرير" — إزالة بادئات العربية
        # تحسين مخطط للمرحلة التالية وليست خللاً في التطبيع الحالي.
        engine = BM25Engine()
        engine.add_documents(["تقرير أشعة صدر"])
        assert engine.search("التقرير") == []


class TestIdempotentIndexing:
    """الفهرسة المتكررة لا تكرر المستندات ولا تخل بترتيب _doc_ids (مراجعة كيمي — المرحلة 1)"""

    def test_reindex_same_directory_no_duplicates(self, tmp_path):
        (tmp_path / "a.txt").write_text("محتوى أول", encoding="utf-8")
        (tmp_path / "b.txt").write_text("محتوى ثانٍ", encoding="utf-8")
        engine = HybridSearchEngine()

        n1 = engine.index_files(str(tmp_path), extensions=(".txt",))
        n2 = engine.index_files(str(tmp_path), extensions=(".txt",))

        assert n1 == 2
        assert n2 == 2
        assert engine.bm25.document_count == 2
        assert len(engine._doc_ids) == 2
        # تطابق _doc_ids مع نصوص الفهرس يبقى سليماً بعد إعادة الفهرسة
        assert set(engine._doc_ids) == set(engine._doc_texts.keys())

    def test_reset_false_appends(self, tmp_path):
        (tmp_path / "a.txt").write_text("نص أول", encoding="utf-8")
        engine = HybridSearchEngine()
        engine.index_files(str(tmp_path), extensions=(".txt",))

        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "b.txt").write_text("نص آخر", encoding="utf-8")
        engine.index_files(str(sub), extensions=(".txt",), reset=False)

        assert engine.bm25.document_count == 2
        assert len(engine._doc_ids) == 2


class TestThreadSafety:
    """أقفال المحرك المشترك بين خيوط FastAPI المتوازية (مراجعة كيمي — المرحلة 1)"""

    def test_concurrent_search_is_safe(self, tmp_path):
        import threading

        (tmp_path / "a.txt").write_text("نص للاختبار", encoding="utf-8")
        engine = HybridSearchEngine()
        engine.index_files(str(tmp_path), extensions=(".txt",))

        errors: list[Exception] = []

        def worker():
            try:
                for _ in range(30):
                    res = engine.search("نص", top_k=3)
                    assert isinstance(res, list)
            except Exception as exc:  # pragma: no cover
                errors.append(exc)

        threads = [threading.Thread(target=worker) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
