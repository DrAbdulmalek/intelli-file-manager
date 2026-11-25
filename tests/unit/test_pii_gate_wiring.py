#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""اختبارات دائمة لدفعة الإصلاح: ربط بوابة PII + رفع _SAFE_CATEGORY_RE

- test_pii_gate_wired_into_ingest_file_mask: مع mask تُفهرس المقاطع بلا أي PII خام
- test_pii_gate_wired_into_ingest_file_block: مع block يتوقف الاستيعاب (0 مقطع)
- test_safe_category_re_defined_before_create_app: التعريف يسبق create_app()
  (إغلاق بند P0-5 من docs/REVIEW.md — NameError محتمل وقت الاستيراد)
"""
from __future__ import annotations

import importlib
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# 1) ربط بوابة PII داخل RAGEngine.ingest_file
# ---------------------------------------------------------------------------
class _StubCollection:
    def __init__(self):
        self.added: list[list[str]] = []

    def add(self, ids, documents, metadatas):
        self.added.append(list(documents))


class _StubClient:
    def __init__(self):
        self.collection = _StubCollection()

    def get_or_create_collection(self, name, metadata=None):
        return self.collection


def _engine_with_stub_client():
    from src.core.rag_engine import RAGEngine

    engine = RAGEngine.__new__(RAGEngine)  # بلا تهيئة شبكة/نماذج
    client = _StubClient()
    engine._client = client
    engine._embedding_function = None
    return engine, client


PII_TEXT = (
    "تقرير المريض أحمد: للتواصل doctor@example.com أو 0512345678. "
    "الجرعة اليومية 500 ملغ."
)


@pytest.mark.unit
def test_pii_gate_wired_into_ingest_file_mask(tmp_path, monkeypatch):
    from src.plugins import pii_gate
    pii_gate.set_mode("mask")
    f = tmp_path / "report.txt"
    f.write_text(PII_TEXT, encoding="utf-8")

    engine, client = _engine_with_stub_client()
    chunks = engine.ingest_file(str(f))

    assert chunks > 0, "وضع mask يجب أن يفهرس النص بعد الإخفاء"
    stored = "\n".join(doc for docs in client.collection.added for doc in docs)
    assert "doctor@example.com" not in stored, "بريد خام تسرب إلى الفهرس!"
    assert "0512345678" not in stored, "هاتف خام تسرب إلى الفهرس!"
    assert "[PII:" in stored, "الإخفاء لم يُطبَّق (لا عنصر نائب)"
    pii_gate.set_mode(pii_gate.DEFAULT_MODE)


@pytest.mark.unit
def test_pii_gate_wired_into_ingest_file_block(tmp_path, monkeypatch):
    from src.plugins import pii_gate
    pii_gate.set_mode("block")
    f = tmp_path / "report.txt"
    f.write_text(PII_TEXT, encoding="utf-8")

    engine, client = _engine_with_stub_client()
    chunks = engine.ingest_file(str(f))

    assert chunks == 0, "وضع block يجب أن يحجب الفهرسة كلياً"
    assert client.collection.added == [], "دخل نص محجوب إلى ChromaDB!"
    pii_gate.set_mode(pii_gate.DEFAULT_MODE)


@pytest.mark.unit
def test_pii_gate_clean_text_passes_through(tmp_path, monkeypatch):
    """النص النظيف بلا PII يُفهرس كما هو (لا حجب زائف)."""
    from src.plugins import pii_gate
    pii_gate.set_mode("block")
    f = tmp_path / "clean.txt"
    f.write_text("الجرعة اليومية 500 ملغ بعد الطعام.", encoding="utf-8")

    engine, client = _engine_with_stub_client()
    chunks = engine.ingest_file(str(f))
    assert chunks > 0, "نص نظيف حُجب خطأً (إيجاب كاذب)"
    stored = "\n".join(doc for docs in client.collection.added for doc in docs)
    assert "500" in stored
    pii_gate.set_mode(pii_gate.DEFAULT_MODE)


# ---------------------------------------------------------------------------
# 2) ترتيب التعريف: _SAFE_CATEGORY_RE قبل create_app()
# ---------------------------------------------------------------------------
@pytest.mark.unit
def test_safe_category_re_defined_before_create_app():
    """بند P0-5 من docs/REVIEW.md: كان التعريف بعد create_app() — أي استدعاء
    أثناء بناء التطبيق كان سيوقعت NameError. الآن: تعريف على مستوى الوحدة
    يسبق الاستدعاء."""
    src = Path("src/api/server.py").read_text(encoding="utf-8")
    lines = src.splitlines()
    def_line = next(i for i, l in enumerate(lines, 1)
                    if "_SAFE_CATEGORY_RE = re.compile" in l)
    app_line = next(i for i, l in enumerate(lines, 1)
                    if l.startswith("app = create_app()"))
    assert def_line < app_line, (
        f"_SAFE_CATEGORY_RE (سطر {def_line}) يجب أن يسبق create_app (سطر {app_line})"
    )


@pytest.mark.unit
def test_safe_category_re_functional():
    """التعبير يعمل على مستوى الوحدة بعد الاستيراد (عربي + لاتيني + رفض)."""
    import src.api.server as srv

    assert srv._SAFE_CATEGORY_RE.match("فواتير")
    assert srv._SAFE_CATEGORY_RE.match("Invoices-2026")
    assert not srv._SAFE_CATEGORY_RE.match("../escape")
    assert not srv._SAFE_CATEGORY_RE.match("a b/c")
