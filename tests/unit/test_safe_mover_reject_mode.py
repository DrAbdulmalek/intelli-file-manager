# -*- coding: utf-8 -*-
"""اختبارات وضع الرفض في SafeMover (نطاق P0-B المنفصل — مهمة التفضيلات §2-B)

السلوك الافتراضي (suffix) **لا يتغير** — التوافق مع UndoLog والاختبارات
القائمة. وضع reject يرفض الوجهة الموجودة صراحةً وفق سياسة المستخدم.
"""
from __future__ import annotations

import pytest

from src.core.safe_mover import SafeMover, OverwriteForbiddenError


@pytest.fixture
def mover() -> SafeMover:
    return SafeMover()


def _files(tmp_path):
    src = tmp_path / "src" / "doc.txt"
    src.parent.mkdir(exist_ok=True)
    src.write_text("source content")
    return src


# ─── السلوك الافتراضي سليم (انحدار) ────────────────────────────────────────

def test_default_suffix_behavior_unchanged(tmp_path):
    src = _files(tmp_path)
    dst = tmp_path / "dst" / "doc.txt"
    dst.parent.mkdir()
    dst.write_text("existing occupant")
    mover = SafeMover()
    result = mover.move(str(src), str(dst))
    assert result.success is True
    assert result.renamed_due_to_collision is True  # لاحقة تلقائية كما قبل
    assert dst.read_text() == "existing occupant"   # الشاغل لم يُمس
    # المصدر انتقل إلى اللاحقة
    assert not src.exists()


def test_reject_mode_not_the_default(tmp_path):
    src = _files(tmp_path)
    dst = tmp_path / "dst" / "doc.txt"
    dst.parent.mkdir()
    dst.write_text("occupant")
    result = SafeMover().move(str(src), str(dst))
    assert result.success is True  # الافتراضي ينجح باللاحقة


# ─── وضع الرفض ─────────────────────────────────────────────────────────────

def test_reject_mode_refuses_existing_destination(tmp_path):
    src = _files(tmp_path)
    dst = tmp_path / "dst" / "doc.txt"
    dst.parent.mkdir()
    dst.write_text("occupant")
    mover = SafeMover()
    result = mover.move(str(src), str(dst), on_conflict="reject")
    assert result.success is False
    assert "destination_exists" in result.error
    # المصدر لم يتحرك، والشاغل لم يُمس، ولا لاحقة أُنشئت
    assert src.exists() and src.read_text() == "source content"
    assert dst.read_text() == "occupant"
    assert list(dst.parent.iterdir()) == [dst]


def test_reject_mode_succeeds_on_free_destination(tmp_path):
    src = _files(tmp_path)
    dst = tmp_path / "dst" / "doc.txt"
    dst.parent.mkdir()
    result = SafeMover().move(str(src), str(dst), on_conflict="reject")
    assert result.success is True
    assert result.renamed_due_to_collision is False
    assert dst.read_text() == "source content"
    assert not src.exists()


def test_instance_level_reject_policy(tmp_path):
    src = _files(tmp_path)
    dst = tmp_path / "dst" / "doc.txt"
    dst.parent.mkdir()
    dst.write_text("occupant")
    mover = SafeMover(on_conflict="reject")
    result = mover.move(str(src), str(dst))
    assert result.success is False
    assert "destination_exists" in result.error


def test_move_level_policy_overrides_instance(tmp_path):
    src = _files(tmp_path)
    dst = tmp_path / "dst" / "doc.txt"
    dst.parent.mkdir()
    dst.write_text("occupant")
    mover = SafeMover(on_conflict="reject")
    # تجاوز لكل عملية نحو suffix مسموح
    result = mover.move(str(src), str(dst), on_conflict="suffix")
    assert result.success is True and result.renamed_due_to_collision is True


def test_invalid_on_conflict_value_rejected_at_construction():
    with pytest.raises(ValueError):
        SafeMover(on_conflict="overwrite_quietly")


def test_invalid_on_conflict_value_rejected_at_move(tmp_path):
    src = _files(tmp_path)
    dst = tmp_path / "dst" / "doc.txt"
    result = SafeMover().move(str(src), str(dst), on_conflict="explode")
    assert result.success is False
    assert "on_conflict" in result.error
    assert src.exists()  # المصدر سليم


def test_overwrite_still_forbidden_in_reject_mode(tmp_path):
    src = _files(tmp_path)
    dst = tmp_path / "dst" / "doc.txt"
    dst.parent.mkdir()
    dst.write_text("occupant")
    mover = SafeMover(on_conflict="reject")
    # move(overwrite=True) يفشل بنتيجة صريحة (الاستثناء للمنشئ فقط — عقد قائم)
    result = mover.move(str(src), str(dst), overwrite=True)
    assert result.success is False
    assert "محظور" in result.error
    assert src.exists() and dst.read_text() == "occupant"
