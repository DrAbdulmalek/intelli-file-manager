# -*- coding: utf-8 -*-
"""اختبارات حارس no-op في SafeMover — إغلاق بند DeepSeek (الجولة 5 ← 12).

المطلوب: symlink/hardlink/تهجئة المسار — العقد: **بلا فقد بيانات** بأي حالة،
والـno-op الأصلي (نفس المسار المحلول) ينجح idempotent دون لاحقة.

الحارس: `src.resolve() == dst.resolve()` (safe_mover:477 داخل move، و:190
داخل _resolve_collision).
"""
import os
from pathlib import Path

import pytest

from src.core.safe_mover import SafeMover


def _mover() -> SafeMover:
    return SafeMover(verify_checksum=True, move_sidecar=False)


def test_noop_same_path_different_spelling_is_idempotent(tmp_path):
    """`dir/./f.txt` و `dir/f.txt` نفس الملف المحلول — نجاح بلا لاحقة ولا تكرار."""
    mover = _mover()
    real = tmp_path / "dir" / "f.txt"
    real.parent.mkdir()
    real.write_text("DATA")

    result = mover.move(str(tmp_path / "dir" / "." / "f.txt"), str(real))

    assert result.success
    assert result.final_path == str(real)
    assert real.read_text() == "DATA"
    assert list(tmp_path.rglob("*.txt")) == [real]  # لا نسخة ثانية ولا لاحقة


def test_noop_symlink_destination_resolves_to_source(tmp_path):
    """الوجهة symlink للمصدر نفسه — نفس الملف المحلول → no-op، لا استبدال الرابط."""
    mover = _mover()
    real = tmp_path / "real.txt"
    real.write_text("CONTENT")
    link = tmp_path / "alias.txt"
    os.symlink(real, link)

    result = mover.move(str(real), str(link))

    assert result.success
    assert real.read_text() == "CONTENT"          # لا فقد بيانات
    assert link.is_symlink() and link.resolve() == real.resolve()
    assert not list(tmp_path.glob("alias_*.txt"))  # لا لاحقة


def test_hardlink_move_suffixes_instead_of_losing_data(tmp_path):
    """hardlink: مساران مختلفان لنفس الـinode — الحارس لا يعتبرهما no-op
    (resolve يقارن المسارات لا الـinodes)، فالتضارب يأخذ لاحقة:
    **الشاغل يبقى سليماً والمصدر ينتقل باسم ملحق — صفر فقد**."""
    mover = _mover()
    a = tmp_path / "a.txt"
    a.write_text("SOURCE-DATA")
    b = tmp_path / "b.txt"
    os.link(a, b)  # نفس الـinode
    assert os.stat(a).st_ino == os.stat(b).st_ino

    result = mover.move(str(a), str(b))

    assert result.success
    final = Path(result.final_path)
    assert final.name.startswith("b_")                         # لاحقة لا استبدال
    assert final.read_text() == "SOURCE-DATA"                  # بيانات المصدر محفوظة
    assert b.read_text() == "SOURCE-DATA"                      # الشاغل (نفس الـinode) سليم


def test_hardlink_copy_never_overwrites_either_link(tmp_path):
    """نسخ بين hardlinkين: المصدر يبقى، الشاغل يبقى، النسخة بمسار ملحق."""
    mover = _mover()
    a = tmp_path / "a.txt"
    a.write_text("X")
    b = tmp_path / "b.txt"
    os.link(a, b)

    result = mover.copy(str(a), str(b))

    assert result.success
    assert Path(result.final_path).name.startswith("b_")
    assert a.exists() and b.read_text() == "X"  # لا شيء استُبدل


def test_broken_symlink_destination_treated_as_collision(tmp_path):
    """وجهة symlink ميتة: exists()=False لكن resolve يفشل أو يعيد المسار الهدف —
    العقد: لا فقد بيانات؛ السلوك المقبول نجاح بلا استبدال للمصدر."""
    mover = _mover()
    src = tmp_path / "src.txt"
    src.write_text("S")
    dead = tmp_path / "dead.txt"
    os.symlink(tmp_path / "nowhere.txt", dead)

    result = mover.move(str(src), str(dead))

    # المصدر لن يُفقد في أي نتيجة: إما no-op/نجاح بمسار نهائي يحمل البيانات
    # أو فشل صريح والمصدر باقٍ
    if result.success:
        assert Path(result.final_path).read_text() == "S"
    else:
        assert src.read_text() == "S"
