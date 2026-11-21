# -*- coding: utf-8 -*-
"""اختبارات PreferenceStore — بيانات اصطناعية فقط (متطلب المهمة §9A)

تغطي: مخطط صالح/حقول ناقصة/حقول زائدة/أنواع خاطئة/JSON تالف/كتابة مقطوعة/
استبدال ذرّي/استعادة نسخة احتياطية/كتابة متزامنة/ترحيل v1→v2/إصدار غير معروف/
حالة SAFE READ-ONLY (لا حفظ فوق الأصل، لا قواعد جديدة)/سجل التغييرات والاستعادة.
"""
from __future__ import annotations

import copy
import json
import threading
from pathlib import Path

import pytest

from src.core.preference_store import (
    BackupCorruptedError,
    InvalidRuleError,
    PreferenceStore,
    PreferenceStoreError,
    StoreReadOnlyError,
    SCHEMA_VERSION,
    new_rule_id,
)


def _rule(**overrides) -> dict:
    rule = {
        "rule_id": new_rule_id(),
        "created_at": "2026-11-20T10:00:00+00:00",
        "updated_at": "2026-11-20T10:00:00+00:00",
        "status": "provisional",
        "match": {"kind": "extension", "value": ".xyz", "case_insensitive": True},
        "scope": {"kind": "global", "value": None},
        "destination": {"category": "صور"},
        "confidence": {"independent_sessions": 1, "total_confirmations": 1, "score": 0.5},
        "source": {"origin": "user_correction", "feedback_ids": []},
        "history": [],
    }
    rule.update(overrides)
    return rule


@pytest.fixture
def store(tmp_path) -> PreferenceStore:
    s = PreferenceStore(tmp_path / "prefs.json")
    s.load()
    return s


# ─── مخطط صالح والحقول ──────────────────────────────────────────────────────

def test_valid_schema_roundtrip(store):
    store.add_rule(_rule())
    report = store.load()
    assert report["ok"] and not report["read_only"]
    assert report["rule_count"] == 1
    rules = store.list_rules()
    assert rules[0]["destination"]["category"] == "صور"


def test_missing_required_field_rejected(store):
    bad = _rule()
    del bad["destination"]
    with pytest.raises(InvalidRuleError):
        store.add_rule(bad)
    assert store.list_rules() == []


def test_extra_unknown_fields_are_preserved(store):
    rule = _rule()
    rule["vendor_note"] = {"custom_section": [1, 2, 3]}
    store.add_rule(rule)
    reloaded = store.load()
    assert reloaded["ok"]
    stored = store.list_rules()[0]
    assert stored["vendor_note"] == {"custom_section": [1, 2, 3]}


def test_invalid_types_rejected(store):
    bad = _rule(confidence="high")
    with pytest.raises(InvalidRuleError):
        store.add_rule(bad)
    bad2 = _rule(status="ultra_stable")
    with pytest.raises(InvalidRuleError):
        store.add_rule(bad2)


def test_unknown_match_kind_rejected(store):
    bad = _rule()
    bad["match"]["kind"] = "content_hash"
    with pytest.raises(InvalidRuleError):
        store.add_rule(bad)


# ─── التلف والحالة الآمنة ────────────────────────────────────────────────────

def test_corrupted_json_enters_safe_read_only(tmp_path):
    path = tmp_path / "prefs.json"
    path.write_text("{corrupted json!!", encoding="utf-8")
    s = PreferenceStore(path)
    report = s.load()
    assert not report["ok"] and report["read_only"]
    assert s.load_errors
    with pytest.raises(StoreReadOnlyError):
        s.add_rule(_rule())
    with pytest.raises(StoreReadOnlyError):
        s.save()
    # الملف الأصلي بقي دون تغيير
    assert path.read_text(encoding="utf-8") == "{corrupted json!!"


def test_invalid_rule_in_file_enters_safe_read_only(tmp_path):
    """مخطط صالح JSON لكن قاعدة تخالف المخطط → read-only، لا حفظ فوقه."""
    path = tmp_path / "prefs.json"
    doc = {
        "schema_version": SCHEMA_VERSION,
        "preferences": {"rules": [{"rule_id": "x"}]},  # قاعدة ناقصة
        "change_log": [],
    }
    path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    s = PreferenceStore(path)
    report = s.load()
    assert not report["ok"] and report["read_only"]
    assert any("rule[0]" in e for e in s.load_errors)
    original_bytes = path.read_bytes()
    with pytest.raises(StoreReadOnlyError):
        s.save()
    assert path.read_bytes() == original_bytes


def test_unknown_schema_version_refused_and_file_untouched(tmp_path):
    path = tmp_path / "prefs.json"
    doc = {
        "schema_version": 99,
        "preferences": {"rules": [_rule()]},
        "unknown_future_section": {"keep": True},
    }
    original = json.dumps(doc, ensure_ascii=False)
    path.write_text(original, encoding="utf-8")
    s = PreferenceStore(path)
    report = s.load()
    assert not report["ok"] and report["read_only"]
    assert any("غير مدعوم" in e or "bad:schema_version" in e for e in s.load_errors)
    assert path.read_text(encoding="utf-8") == original


def test_non_object_root_enters_read_only(tmp_path):
    path = tmp_path / "prefs.json"
    path.write_text("[1, 2, 3]", encoding="utf-8")
    s = PreferenceStore(path)
    assert not s.load()["ok"] and s.read_only


# ─── الكتابة المقطوعة والذرّية ──────────────────────────────────────────────

def test_interrupted_write_leaves_original_intact(store, tmp_path):
    """محاكاة انقطاع أثناء الكتابة: ملف tmp متروك + الملف الأصلي سليم."""
    store.add_rule(_rule())
    good = store.path.read_bytes()
    stale_tmp = store.path.parent / (store.path.name + ".tmp-orphan")
    stale_tmp.write_bytes(b"half written{")
    s2 = PreferenceStore(store.path)
    report = s2.load()
    assert report["ok"] and report["rule_count"] == 1
    assert store.path.read_bytes() == good
    stale_tmp.unlink()


def test_atomic_replacement_no_tmp_leftovers(store):
    store.add_rule(_rule())
    store.add_rule(_rule())
    leftovers = [p for p in store.path.parent.iterdir() if ".tmp-" in p.name]
    assert leftovers == []
    assert store.load()["rule_count"] == 2


def test_save_creates_backup_with_hash(store):
    # الحفظ الأول ينشئ الملف (لا حالة سابقة على القرص تُنسخ احتياطيًا)؛
    # الحفظ الثاني ينسخ احتياطيًا الحالة السابقة ويحفظ بصمتها.
    store.add_rule(_rule())
    store.add_rule(_rule())
    assert store.backup_path.exists()
    assert store.backup_hash_path.exists()
    stored = store.backup_hash_path.read_text(encoding="utf-8").strip()
    import hashlib
    assert stored == hashlib.sha256(store.backup_path.read_bytes()).hexdigest()


# ─── الاستعادة ──────────────────────────────────────────────────────────────

def test_backup_recovery_restores_previous_state(store):
    store.add_rule(_rule(match={"kind": "extension", "value": ".a", "case_insensitive": True}))
    first_bytes = store.path.read_bytes()
    store.update_rule(store.list_rules()[0]["rule_id"],
                      lambda r: r["destination"].__setitem__("category", "فيديو"))
    assert store.list_rules()[0]["destination"]["category"] == "فيديو"
    decision = store.restore_backup()
    assert decision["restored"] is True and decision["hash_match"] is True
    assert store.path.read_bytes() == first_bytes


def test_corrupted_backup_is_refused_and_decision_logged(store, tmp_path):
    store.add_rule(_rule())
    store.backup_path.write_bytes(b"tampered content!")
    with pytest.raises(BackupCorruptedError):
        store.restore_backup()
    log_lines = store.restore_log_path.read_text(encoding="utf-8").splitlines()
    entry = json.loads(log_lines[-1])
    assert entry["restored"] is False and entry["reason"] == "backup_corrupted_refused"


# ─── الكتابة المتزامنة ──────────────────────────────────────────────────────

def test_concurrent_writes_all_survive(tmp_path):
    """6 خيوط تكتب قواعد متزامنة — لا فقدان ولا تلف (قفل flock)."""
    s = PreferenceStore(tmp_path / "prefs.json")
    s.load()
    errors: list = []

    def writer(i: int) -> None:
        try:
            local = PreferenceStore(tmp_path / "prefs.json")
            local.load()
            local.add_rule(_rule(match={"kind": "extension", "value": f".ext{i}",
                                        "case_insensitive": True}))
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=writer, args=(i,)) for i in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == []
    final = PreferenceStore(tmp_path / "prefs.json")
    report = final.load()
    assert report["ok"]
    assert report["rule_count"] == 6


# ─── الترحيل ────────────────────────────────────────────────────────────────

def test_v1_migration_preserves_rules_and_unknown_sections(tmp_path):
    path = tmp_path / "prefs.json"
    v1_doc = {
        "schema_version": 1,
        "rules": [_rule(status="stable",
                        confidence={"independent_sessions": 3,
                                    "total_confirmations": 5, "score": 0.9})],
        "legacy_section": {"keep_me": "yes"},
    }
    path.write_text(json.dumps(v1_doc, ensure_ascii=False), encoding="utf-8")
    s = PreferenceStore(path)
    report = s.load()
    assert report["ok"] and report.get("migrated_from") == 1
    assert report["rule_count"] == 1
    assert s.list_rules()[0]["status"] == "stable"
    # القسم غير المعروف لم يفقد، والحفظ المرقّى يكتبه كما هو
    s.add_rule(_rule(match={"kind": "extension", "value": ".b", "case_insensitive": True}))
    on_disk = json.loads(path.read_text(encoding="utf-8"))
    assert on_disk["legacy_section"] == {"keep_me": "yes"}
    assert on_disk["schema_version"] == SCHEMA_VERSION
    assert any(m["from"] == 1 for m in on_disk.get("migrations_applied", []))


def test_migration_does_not_destroy_old_file_on_unsupported_version(tmp_path):
    """v0.9 الشبح: يُرفض ولا يُلمس الملف (ترحيل غير مدمِر)."""
    path = tmp_path / "prefs.json"
    original = '{"schema_version": 1, "rules": [], "x": 1}'
    path.write_text(original, encoding="utf-8")
    # نعدل المستند في الذاكرة فقط لاختبار الرفض دون كتابة
    doc = json.loads(original)
    doc["schema_version"] = 777
    with pytest.raises(PreferenceStoreError):
        PreferenceStore.migrate(doc)
    assert path.read_text(encoding="utf-8") == original


# ─── سجل التغييرات والاستعادة ───────────────────────────────────────────────

def test_change_log_records_and_revert_restores(store):
    created = store.add_rule(_rule())
    rid = created["rule_id"]
    store.update_rule(rid, lambda r: r["destination"].__setitem__("category", "أنظمة"))
    store.update_rule(rid, lambda r: r["confidence"].__setitem__("score", 0.9))
    log = store._document["change_log"]
    actions = [e["action"] for e in log]
    assert actions == ["rule_created", "rule_updated", "rule_updated"]
    assert "before" in log[1]["details"]  # لقطة «قبل» قابلة للتتبع
    # استعادة خطوتين
    reverted = store.revert_last_change()
    assert reverted["confidence"]["score"] == 0.5
    reverted2 = store.revert_last_change()
    assert reverted2["destination"]["category"] == "صور"
    # لقطة الإنشاء لا حالة سابقة لها
    assert store.revert_last_change() is None


def test_deleted_rules_hidden_from_list_but_kept_on_disk(store):
    created = store.add_rule(_rule())
    rid = created["rule_id"]
    store.update_rule(rid, lambda r: r.__setitem__("status", "deleted"),
                      change_action="rule_deleted")
    assert store.list_rules() == []
    assert store.list_rules(include_deleted=True)[0]["rule_id"] == rid
    on_disk = json.loads(store.path.read_text(encoding="utf-8"))
    assert on_disk["preferences"]["rules"][0]["status"] == "deleted"
