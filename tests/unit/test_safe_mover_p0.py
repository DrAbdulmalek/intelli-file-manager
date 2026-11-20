"""اختبارات P0 لـSafeMover: حجز الوجهة ضد TOCTOU والاستبدال الآمن (IFM-006)."""
from __future__ import annotations

from pathlib import Path

import pytest

import src.core.safe_mover as sm
from src.core.safe_mover import SafeMover, _claim_destination


@pytest.fixture()
def mover():
    return SafeMover(verify_checksum=True, move_sidecar=True)


def test_move_race_claimed_destination_stops_without_replacing(tmp_path, mover, monkeypatch):
    """محاكاة الفائز في السباق: فحص التضارب مرّ والوجهة فارغة، ثم ظهر ملف قبل الحجز."""
    src = tmp_path / "src.txt"
    src.write_text("NEW")
    dst = tmp_path / "dst.txt"

    def resolve_after_race(d, s):
        # يحاكي مرور فحص التضارب بنجاح (الوجهة كانت فارغة لحظته) ثم ظهور ملف الفائز
        return dst, False

    monkeypatch.setattr(sm, "_resolve_collision", resolve_after_race)
    # ملف الفائز يظهر بين الفحص والتنفيذ — الحجز O_EXCL يجب أن يوقف العملية
    _claim_destination(dst)

    result = mover.move(src, dst)

    assert result.success is False
    assert "TOCTOU" in (result.error or "")
    assert src.read_text() == "NEW", "المصدر يجب أن يبقى سليمًا"
    assert dst.exists() and dst.stat().st_size == 0, "ملف الفائز لم يُستبدل"


def test_move_without_race_still_works(tmp_path, mover):
    src = tmp_path / "a.txt"
    src.write_text("data")
    dst = tmp_path / "sub" / "b.txt"
    result = mover.move(src, dst)
    assert result.success is True
    assert dst.read_text() == "data"
    assert not src.exists()


def test_collision_still_gets_suffix(tmp_path, mover):
    src = tmp_path / "a.txt"
    src.write_text("data")
    dst = tmp_path / "b.txt"
    dst.write_text("existing")
    result = mover.move(src, dst)
    assert result.success is True
    assert dst.read_text() == "existing", "الوجهة الموجودة لا تُستبدل افتراضيًا"
    assert result.renamed_due_to_collision is True
    assert Path(result.final_path).read_text() == "data"


def test_overwrite_success_replaces_and_cleans_backup(tmp_path, mover):
    src = tmp_path / "new.txt"
    src.write_text("NEW")
    dst = tmp_path / "old.txt"
    dst.write_text("OLD")

    result = mover.move(src, dst, overwrite=True)

    assert result.success is True
    assert dst.read_text() == "NEW"
    assert result.replaced_existing is True
    assert result.overwritten_backup is None, "الاحتياطية تُحذف بعد النجاح"
    assert not list(tmp_path.glob(".ifm_overwrite_*.bak")), "لا مخلفات"


def test_overwrite_failure_restores_original(tmp_path, mover, monkeypatch):
    """الفشل أثناء النقل مع overwrite=True يجب أن يعيد الوجهة القديمة كما كانت."""
    src = tmp_path / "new.txt"
    src.write_text("NEW")
    dst = tmp_path / "old.txt"
    dst.write_text("OLD")

    def boom(src_p, dst_p):
        raise OSError(5, "I/O error محاكى")

    monkeypatch.setattr(sm, "_atomic_move", boom)
    result = mover.move(src, dst, overwrite=True)

    assert result.success is False
    assert dst.read_text() == "OLD", "النسخة القديمة تُعاد عند الفشل — لا فقدان"
    assert src.read_text() == "NEW"
    assert not list(tmp_path.glob(".ifm_overwrite_*.bak")), "أُعيدت لا تُركت جانبًا"


def test_copy_overwrite_failure_restores_original(tmp_path, mover, monkeypatch):
    src = tmp_path / "new.txt"
    src.write_text("NEW")
    dst = tmp_path / "old.txt"
    dst.write_text("OLD")

    def boom(src_p, dst_p):
        raise OSError(5, "I/O error محاكى")

    monkeypatch.setattr(sm, "_atomic_copy", boom)
    result = mover.copy(src, dst, overwrite=True)

    assert result.success is False
    assert dst.read_text() == "OLD"
    assert src.read_text() == "NEW"


def test_same_file_move_is_noop(tmp_path, mover):
    src = tmp_path / "same.txt"
    src.write_text("x")
    result = mover.move(src, src)
    assert result.success is True
    assert src.read_text() == "x"
