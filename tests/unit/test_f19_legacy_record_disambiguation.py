# -*- coding: utf-8 -*-
"""اختبارات F19: تمييز السجلات القديمة الملتبسة (Legacy Undo Record Disambiguation).

السيناريو المثبت من المالك: سجل قديم كُتب قبل F14 يحمل success=False لإجراء
نسخ ناجح فشل تراجعه (كان فشل التراجع يُلوّث success/error_message قبل فصل
النتائج). F18 كان يستهلكه no-op → فقدان قابلية الاسترداد. F19: يُحفظ السجل
بحالة recovery_required، لا عكس ولا استهلاك تلقائي، ولا حذف ملف/sidecar.

الاختبارات هنا تُحمّل سجلات **محفوظة فعلياً بصيغة ما قبل F14** على القرص
(بدون مفاتيح rollback_error_message/schema_version/recovery_state/
tags_already_present) — لا كائنات مبنية في الذاكرة فقط.

بيانات اصطناعية في tmp_path فقط.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.core.rule_engine import _sidecar_path
from src.core.rule_schemas import UndoEntry
from src.core.safe_mover import SafeMover, compute_sha256
from src.core.undo_log import UndoLog


# ─── أدوات: صيغة ما قبل F14 بالحرف ──────────────────────────────────────────

def _legacy_copy_dict(src: str, dest: str, sha: str, batch_id: str = "B-LEG") -> dict:
    """سجل COPY قديم: نسخ ناجح فشل تراجعه — success=False ملوّثة بفشل التراجع
    (سلوك rollback_last قبل F14). مفاتيح الصيغة القديمة فقط."""
    return {
        "action_type": "copy",
        "file_path": src,
        "file_path_after": dest,
        "rule_name": "legacy-rules",
        "old_category": "",
        "new_category": "",
        "tags_added": [],
        "tags_removed": [],
        "timestamp": "2026-11-01T10:00:00",
        "success": False,
        # نص خطأ التراجع (وليس خطأ التنفيذ الأصلي) — كما كان قبل F14
        "error_message": "فشل التراجع: عُدّل الملف بعد إنشائه — حماية من فقد تعديلات المستخدم",
        "checksum_after": sha,
        "batch_id": batch_id,
    }


def _write_legacy_log(path: Path, entries: list) -> None:
    """يكتب ملف سجل Undo بصيغة save() القديمة (version=1) بدون المفاتيح الجديدة"""
    path.write_text(json.dumps({
        "version": 1,
        "saved_at": "2026-11-01T10:00:00",
        "entries": entries,
    }, ensure_ascii=False, indent=2), encoding="utf-8")


def _make_copied_dest(tmp_path: Path, name: str = "report.pdf") -> tuple:
    """ملف منسوخ على القرص + sidecar له + بصمته (كأن النسخة الأصلية نجحت)"""
    dest = tmp_path / name
    dest.write_text("USER-EDITED-AFTER-COPY", encoding="utf-8")
    sc = _sidecar_path(str(dest))
    sc.write_text(json.dumps({"tags": ["keep-me"], "category": ""}),
                  encoding="utf-8")
    return dest, sc, compute_sha256(dest)


# ─── 1) التحميل: provenance + ختم الاسترداد ─────────────────────────────────

def test_f19_legacy_load_stamps_provenance_and_recovery(tmp_path):
    dest, sc, sha = _make_copied_dest(tmp_path)
    p = tmp_path / "undo.json"
    _write_legacy_log(p, [_legacy_copy_dict("/src/report.pdf", str(dest), sha)])
    log = UndoLog(p)  # تحميل تلقائي
    e = log.entries[0]
    assert e.schema_version == "1"
    assert e.recovery_state == "recovery_required"
    assert e.success is False
    assert e.rollback_error_message == ""
    assert e.checksum_after == sha


def test_f19_v2_record_not_marked_and_explicit_version_wins():
    # سجل بصيغة v2 (يحمل rollback_error_message): success=False موثوق — بلا ختم
    d2 = {"action_type": "copy", "file_path": "/x/a.txt",
          "file_path_after": "/x/b.txt", "success": False,
          "rollback_error_message": ""}
    e2 = UndoEntry.from_dict(d2)
    assert e2.schema_version == "2" and e2.recovery_state == ""
    # القيمة الصريحة schema_version تنتصر حتى بغياب مفتاح v2 المميز
    d3 = {"action_type": "copy", "file_path": "/x/a.txt", "success": False,
          "schema_version": "2"}
    e3 = UndoEntry.from_dict(d3)
    assert e3.schema_version == "2" and e3.recovery_state == ""
    # سجل قديم ناجح (success=True): غير ملتبس — بلا ختم استرداد
    d1 = {"action_type": "tag", "file_path": "/x/old.jpg",
          "tags_added": ["t"], "timestamp": "t", "success": True}
    e1 = UndoEntry.from_dict(d1)
    assert e1.schema_version == "1" and e1.recovery_state == ""


# ─── 2) rollback_last: حفظ السجل الملتبس بلا عكس ولا استهلاك ─────────────────

def test_f19_rollback_last_preserves_ambiguous_copy_no_deletion(tmp_path):
    dest, sc, sha = _make_copied_dest(tmp_path)
    p = tmp_path / "undo.json"
    _write_legacy_log(p, [_legacy_copy_dict("/src/report.pdf", str(dest), sha)])
    log = UndoLog(p)
    returned = log.rollback_last()
    # قبل F19 (سلوك F18): كان يُستهلك no-op → فقدان قابلية الاسترداد.
    # الآن: محفوظ، بلا عكس، والسبب موثق.
    assert returned is not None
    assert len(log) == 1  # لم يُستهلك
    assert "ملتبس" in returned.rollback_error_message
    assert returned.recovery_state == "recovery_required"
    assert returned.success is False  # لم يُقلب (لا ترحيل تخميني)
    # لا حذف: النسخة على القرص بمحتوى المستخدم + sidecar سليم
    assert dest.exists()
    assert dest.read_text(encoding="utf-8") == "USER-EDITED-AFTER-COPY"
    assert sc.exists()
    # إعادة المحاولة سلوك نفسه (idempotent) — لا استهلاك متأخر
    returned2 = log.rollback_last()
    assert returned2 is not None and len(log) == 1
    assert "ملتبس" in returned2.rollback_error_message
    assert dest.exists() and sc.exists()


def test_f19_rollback_all_stops_at_ambiguous_record(tmp_path):
    dest, sc, sha = _make_copied_dest(tmp_path)
    p = tmp_path / "undo.json"
    _write_legacy_log(p, [_legacy_copy_dict("/src/report.pdf", str(dest), sha)])
    log = UndoLog(p)
    # إجراء أحدث ناجح (v2): نقل حقيقي عبر SafeMover
    src_file = tmp_path / "doc.txt"
    src_file.write_text("body", encoding="utf-8")
    mover = SafeMover(verify_checksum=True, move_sidecar=False)
    res = mover.move(str(src_file), str(tmp_path / "d") + "/doc.txt")
    assert res.success
    moved_dest = Path(res.final_path)
    log.append(UndoEntry(action_type="move", file_path=str(src_file),
                         file_path_after=str(moved_dest), timestamp="t",
                         success=True))
    rolled = log.rollback_all()
    # الأحدث (v2 ناجح) عُكس فعلاً؛ ثم توقف عند القديم الملتبس
    assert src_file.exists() and not moved_dest.exists()
    assert len(log) == 1  # الملتبس فقط بقي
    assert log.entries[0].schema_version == "1"
    assert "ملتبس" in log.entries[0].rollback_error_message
    assert rolled[-1].recovery_state == "recovery_required"
    # نسخة السجل القديم لم تُمس إطلاقاً
    assert dest.exists() and sc.exists()


# ─── 3) rollback_batch: تصنيف recovery_required والسجل يبقى ──────────────────

def test_f19_rollback_batch_classifies_recovery_required(tmp_path):
    dest, sc, sha = _make_copied_dest(tmp_path)
    p = tmp_path / "undo.json"
    _write_legacy_log(p, [_legacy_copy_dict("/src/report.pdf", str(dest), sha,
                                            batch_id="B-MIX")])
    log = UndoLog(p)
    # نسخة v2 ناجحة في نفس الدفعة (أحدث): ملف موجود مطابق للبصمة
    v2_dest = tmp_path / "v2-copy.txt"
    v2_dest.write_text("clean-copy", encoding="utf-8")
    log.append(UndoEntry(action_type="copy", file_path="/src/v2.txt",
                         file_path_after=str(v2_dest), timestamp="t",
                         success=True, checksum_after=compute_sha256(v2_dest),
                         batch_id="B-MIX"))
    out = log.rollback_batch("B-MIX")
    # سجل v2 نُكس فعلاً؛ القديم الملتبس صُنّف وحُفظ
    assert out["rolled_back"] == ["copy"]          # سجل v2
    assert out["recovery_required"] == ["copy"]    # السجل القديم الملتبس
    assert out["skipped_failed"] == []
    assert out["remaining"] == 1
    assert len(log) == 1
    assert log.entries[0].recovery_state == "recovery_required"
    # نسخة v2 حُذفت (تراجع ناجح)؛ نسخة السجل القديم لم تُمس
    assert not v2_dest.exists()
    assert dest.exists()
    assert dest.read_text(encoding="utf-8") == "USER-EDITED-AFTER-COPY"
    assert sc.exists()


# ─── 4) الثبات عبر دورات حفظ/تحميل (لا يضيع التمييز) ─────────────────────────

def test_f19_provenance_survives_save_load_cycle(tmp_path):
    dest, sc, sha = _make_copied_dest(tmp_path)
    p = tmp_path / "undo.json"
    _write_legacy_log(p, [_legacy_copy_dict("/src/report.pdf", str(dest), sha)])
    log = UndoLog(p)
    assert log.entries[0].schema_version == "1"
    # بعد الحفظ: JSON أصبح يحتوي مفتاح rollback_error_message (asdict) —
    # القيمة الصريحة schema_version يجب أن تحفظ التمييز رغم ذلك
    log.save()
    log2 = UndoLog(p)
    e = log2.entries[0]
    assert e.schema_version == "1"           # لم يرقَّ إلى v2 خطأً
    assert e.recovery_state == "recovery_required"
    assert len(log2) == 1
    # والقرص ما زال يحمل السجل (لا حذف)
    disk = json.loads(p.read_text(encoding="utf-8"))
    assert len(disk["entries"]) == 1
    assert disk["entries"][0]["schema_version"] == "1"


# ─── 5) التوافق الخلفي: السجل القديم الناجح يتراجع طبيعياً ────────────────────

def test_f19_legacy_success_record_rolls_back_normally(tmp_path):
    # سجل MOVE قديم ناجح (بلا checksum_after — صيغة أقدم من DeepSeek 11)
    src_file = tmp_path / "pic.jpg"
    dest_dir = tmp_path / "صور"
    dest_dir.mkdir()
    src_file.write_text("img", encoding="utf-8")
    dest = dest_dir / "pic.jpg"
    mover = SafeMover(verify_checksum=True, move_sidecar=False)
    res = mover.move(str(src_file), str(dest))
    assert res.success
    p = tmp_path / "undo.json"
    _write_legacy_log(p, [{
        "action_type": "move",
        "file_path": str(src_file),
        "file_path_after": str(dest),
        "rule_name": "legacy",
        "old_category": "", "new_category": "",
        "tags_added": [], "tags_removed": [],
        "timestamp": "2025-01-01T00:00:00",
        "success": True,
        "error_message": "",
        "batch_id": "",
    }])
    log = UndoLog(p)
    e = log.entries[0]
    assert e.schema_version == "1" and e.recovery_state == ""  # غير ملتبس
    returned = log.rollback_last()
    assert returned is not None
    assert len(log) == 0  # استُهلك طبيعياً — عكس ناجح
    assert src_file.exists() and not dest.exists()


# ─── 6) انحدار F18: سجل v2 فاشل يُستهلك no-op كما هو ─────────────────────────

def test_f19_v2_failed_record_still_consumed(tmp_path, tmp_path_factory):
    log = UndoLog()
    log.append(UndoEntry(action_type="move", file_path="/ghost/x.txt",
                         file_path_after=None, timestamp="t",
                         success=False, error_message="الملف المصدر غير موجود"))
    assert log.entries[0].schema_version == "2"  # الكائنات الجديدة v2
    returned = log.rollback_last()
    assert returned is not None
    assert len(log) == 0  # استهلاك no-op — سلوك F18 لم يتغير


# ─── 7) عقد الإرجاع: تمييز آلي للمستدعي + rollback_n + sidecar قديم ─────────

def test_f19_contract_return_pattern_caller_distinguishes(tmp_path):
    # العقد المعتمد (نمط إرجاعي — لا استثناء يصل المستدعي): التمييز عبر
    # requires_recovery / rollback_error_message — توثيق rollback_last
    dest, sc, sha = _make_copied_dest(tmp_path)
    p = tmp_path / "undo.json"
    _write_legacy_log(p, [_legacy_copy_dict("/src/report.pdf", str(dest), sha)])
    log = UndoLog(p)
    returned = log.rollback_last()
    # الحالة 3 (ملتبس): يُعاد السجل نفسه بلا استثناء، ولا استهلاك ولا عكس
    assert isinstance(returned, UndoEntry)
    assert returned.requires_recovery is True
    assert returned.recovery_state == "recovery_required"
    assert "ملتبس" in returned.rollback_error_message
    assert len(log) == 1
    assert dest.exists() and sc.exists()
    # الحالة 1 (عكس ناجح): requires_recovery=False والسجل خارج القائمة
    log2 = UndoLog()
    log2.append(UndoEntry(action_type="move", file_path="/x/a.txt",
                          file_path_after="/x/b.txt", timestamp="t",
                          success=True))
    ok = log2.rollback_last()
    assert ok.requires_recovery is False
    assert len(log2) == 0


def test_f19_rollback_n_stops_at_ambiguous_last_record(tmp_path):
    # آخر سجل (الأحدث) ملتبس → يتوقف فوراً: محفوظ، وما قبله لم يُمس
    dest, sc, sha = _make_copied_dest(tmp_path)
    v2_dest = tmp_path / "v2.txt"
    v2_dest.write_text("clean", encoding="utf-8")
    p = tmp_path / "undo.json"
    _write_legacy_log(p, [
        {   # الأقدم: نسخة v2 ناجحة (تحمل مفتاح rollback_error_message)
            "action_type": "copy", "file_path": "/src/v2.txt",
            "file_path_after": str(v2_dest), "rule_name": "r",
            "old_category": "", "new_category": "",
            "tags_added": [], "tags_removed": [],
            "timestamp": "2026-11-01T09:00:00",
            "success": True, "error_message": "",
            "rollback_error_message": "",
            "checksum_after": compute_sha256(v2_dest), "batch_id": "",
        },
        _legacy_copy_dict("/src/report.pdf", str(dest), sha),  # الأحدث: ملتبس
    ])
    log = UndoLog(p)
    rolled = log.rollback_n(2)
    assert len(rolled) == 1
    assert rolled[0].requires_recovery is True
    assert len(log) == 2  # الملتبس محفوظ والأقدم لم يُستهلك
    assert dest.exists() and sc.exists()
    assert v2_dest.exists()  # التوقف قبل الوصول إلى الأقدم


def test_f19_legacy_mixed_json_tag_sidecar_untouched(tmp_path):
    # JSON قديم مختلط: MOVE ناجح + TAG ملتبس — sidecar لا يُعاد كتابته
    src_file = tmp_path / "pic.jpg"
    dest_dir = tmp_path / "صور"
    dest_dir.mkdir()
    src_file.write_text("img", encoding="utf-8")
    dest = dest_dir / "pic.jpg"
    mover = SafeMover(verify_checksum=True, move_sidecar=False)
    res = mover.move(str(src_file), str(dest))
    assert res.success
    sc = _sidecar_path(str(dest))
    sc.write_text(json.dumps({"tags": ["t-new", "keep"], "category": ""}),
                  encoding="utf-8")
    sidecar_before = sc.read_text(encoding="utf-8")
    p = tmp_path / "undo.json"
    _write_legacy_log(p, [
        {   # الأقدم: MOVE ناجح (غير ملتبس)
            "action_type": "move", "file_path": str(src_file),
            "file_path_after": str(dest), "rule_name": "legacy",
            "old_category": "", "new_category": "",
            "tags_added": [], "tags_removed": [],
            "timestamp": "2025-01-01T00:00:00",
            "success": True, "error_message": "", "batch_id": "",
        },
        {   # الأحدث: TAG ملتبس — إجراء ناجح فشل تراجعه قبل F14
            "action_type": "tag", "file_path": str(dest),
            "rule_name": "legacy", "old_category": "", "new_category": "",
            "tags_added": ["t-new"], "tags_removed": [],
            "timestamp": "2025-01-01T00:05:00",
            "success": False,
            "error_message": "فشل التراجع: تعذر تحديث sidecar",
            "batch_id": "",
        },
    ])
    log = UndoLog(p)
    returned = log.rollback_last()  # الأحدث = TAG الملتبس
    assert returned.requires_recovery is True
    assert len(log) == 2  # الملتبس محفوظ + الأقدم لم يُمس
    # sidecar لم يُعاد كتابته ولا مُسَّ: نفس البايتات، الوسمان باقيان
    assert sc.exists()
    assert sc.read_text(encoding="utf-8") == sidecar_before
    assert dest.exists()
    # الاستدعاء الثاني: الملتبس فوقي — يعاد السجل نفسه (التوقف fail-closed
    # يحجب الأقدم حتى يُحل الملتبس يدوياً)، وMOVE لا يُمس إطلاقاً
    again = log.rollback_last()
    assert again.action_type == "tag" and again.requires_recovery is True
    assert len(log) == 2
    assert sc.read_text(encoding="utf-8") == sidecar_before
    assert not src_file.exists() and dest.exists()  # الأقدم محجوب لم يُمس
