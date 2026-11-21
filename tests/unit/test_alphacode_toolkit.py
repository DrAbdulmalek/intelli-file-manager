"""اختبارات وحدة لعدة تكامل AlphaCode: sync + ingest + apply.

تعمل دون شبكة: مستودع git مؤقت على القرص، مجلدات عمل مؤقتة، والتسجيل
في FeedbackEngine يُختبر بمسارات معزولة. بوابة apply تُختبر بجعل
_run_tests ترجع نتيجة محددة (لا pytest حقيقي داخل الاختبار).
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPTS = REPO / "scripts"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


alphacode_sync = _load("alphacode_sync")
alphacode_ingest = _load("alphacode_ingest")
alphacode_apply = _load("alphacode_apply")


# ─── أدوات مساعدة ──────────────────────────────────────────────────────────

def _init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "tester"], cwd=repo, check=True)
    (repo / "src").mkdir()
    (repo / "src" / "demo.py").write_text("VALUE = 1\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=repo, check=True)
    return repo


def _workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    (ws / "data" / "alphacode" / "outbox").mkdir(parents=True)
    return ws


def _git(*args: str, cwd: Path) -> str:
    return subprocess.run(["git", *args], cwd=cwd, check=True,
                          capture_output=True, text=True).stdout


# ─── sync: المسح الأمني ────────────────────────────────────────────────────

def test_scan_rejects_sensitive_names(tmp_path):
    outbox = tmp_path / "outbox"
    outbox.mkdir()
    for name in (".env", "id_rsa.pub", "secrets/creds.json", "patient_report.pdf",
                 "server.pem", "db.sqlite"):
        target = outbox / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("x", encoding="utf-8")
    (outbox / "normal_report.md").write_text("# تقرير\n", encoding="utf-8")

    accepted, rejected = alphacode_sync.scan_outbox(outbox)
    assert [f.name for f in accepted] == ["normal_report.md"]
    assert len(rejected) == 6
    assert all(reason for _, reason in rejected)


def test_scan_rejects_symlink_and_oversize(tmp_path):
    outbox = tmp_path / "outbox"
    outbox.mkdir()
    real = tmp_path / "outside.txt"
    real.write_text("s", encoding="utf-8")
    (outbox / "link.md").symlink_to(real)
    big = outbox / "huge.bin"
    big.write_bytes(b"\0" * (alphacode_sync.MAX_FILE_BYTES + 1))

    accepted, rejected = alphacode_sync.scan_outbox(outbox)
    assert accepted == []
    reasons = {name for name, _ in rejected}
    assert {"link.md", "huge.bin"} <= reasons


def test_scan_enforces_batch_count_cap(tmp_path):
    outbox = tmp_path / "outbox"
    outbox.mkdir()
    for i in range(alphacode_sync.MAX_BATCH_FILES + 7):
        (outbox / f"f{i:03d}.txt").write_text("x", encoding="utf-8")

    accepted, rejected = alphacode_sync.scan_outbox(outbox)
    assert len(accepted) == alphacode_sync.MAX_BATCH_FILES
    assert len(rejected) == 7


def test_sync_local_moves_outbox_to_inbox(tmp_path):
    repo = _init_repo(tmp_path)
    ws = _workspace(tmp_path)
    (ws / "data" / "alphacode" / "outbox" / "session-report.md").write_text(
        "# جلسة\nالنتيجة: ناجحة\n", encoding="utf-8")
    (ws / "data" / "alphacode" / "outbox" / ".env").write_text(
        "TOKEN=x\n", encoding="utf-8")

    result = alphacode_sync.sync(repo, ws, push=False)
    assert result["pushed"] is False
    assert len(result["accepted"]) == 1

    inbox = ws / "data" / "alphacode" / "inbox"
    moved = list(inbox.iterdir())
    assert len(moved) == 1 and moved[0].name.endswith("__session-report.md")
    assert not list((ws / "data" / "alphacode" / "outbox").iterdir())
    rejected_dir = ws / "data" / "alphacode" / "rejected"
    # الملف المرفوض ينتقل إلى rejected/ محلياً + سجل السبب
    assert any(p.name.endswith("__.env") for p in rejected_dir.iterdir())
    assert any(p.name.endswith(".rejected.txt") for p in rejected_dir.iterdir())

    # فرع الأيتام أُنشئ وفيه دفعة manifest
    branches = _git("branch", "--list", "alphacode/artifacts", cwd=repo).strip()
    assert "alphacode/artifacts" in branches
    log = _git("log", "--oneline", "alphacode/artifacts", cwd=repo).strip().splitlines()
    assert "alphacode: batch " in log[0]
    manifest = json.loads(_git(
        "show", f"alphacode/artifacts:files/{result['batch_id']}/manifest.json",
        cwd=repo))
    assert manifest["batch"] == result["batch_id"]
    assert manifest["files"][0]["sha256"]


def test_sync_requires_token_for_push(tmp_path):
    repo = _init_repo(tmp_path)
    ws = _workspace(tmp_path)
    (ws / "data" / "alphacode" / "outbox" / "a.md").write_text("x", encoding="utf-8")
    import os
    saved = {k: os.environ.pop(k) for k in ("ALPHACODE_GH_TOKEN", "GITHUB_TOKEN")
             if k in os.environ}
    try:
        with pytest.raises(alphacode_sync.SyncError, match="توكن"):
            alphacode_sync.sync(repo, ws, push=True)
    finally:
        os.environ.update(saved)


# ─── ingest: الأرشفة غير القابلة للتغيير + اللوحة ──────────────────────────

def test_ingest_archives_immutably_and_writes_summary(tmp_path):
    ws = _workspace(tmp_path)
    inbox = ws / "data" / "alphacode" / "inbox"
    inbox.mkdir(parents=True)
    (inbox / "report.md").write_text("محتوى", encoding="utf-8")

    result = alphacode_ingest.ingest(ws)
    assert result["archived"] == 1

    processed = ws / "data" / "alphacode" / "processed"
    archived = [p for p in processed.iterdir() if p.name != "manifest.jsonl"]
    assert len(archived) == 1
    name_parts = archived[0].name.split("__")
    assert len(name_parts) == 3 and name_parts[2] == "report.md"
    assert not list(inbox.iterdir())

    lines = (processed / "manifest.jsonl").read_text(encoding="utf-8").strip().splitlines()
    record = json.loads(lines[-1])
    assert record["sha256"] and record["original"] == "report.md"

    summary = (ws / "data" / "alphacode" / "summary.md").read_text(encoding="utf-8")
    assert "لوحة تكامل AlphaCode" in summary and "processed" in summary


def test_ingest_empty_inbox_is_safe(tmp_path):
    ws = _workspace(tmp_path)
    result = alphacode_ingest.ingest(ws)
    assert result["archived"] == 0
    assert (ws / "data" / "alphacode" / "summary.md").exists()


# ─── apply: بوابة الموافقة ─────────────────────────────────────────────────

def _make_proposal(ws: Path, repo: Path, proposal_id: str = "p1") -> Path:
    """إنشاء patch حقيقي عبر git diff (مضمون الصلاحية) وتجهيز proposal."""
    demo = repo / "src" / "demo.py"
    demo.write_text("VALUE = 2\n", encoding="utf-8")
    patch = _git("diff", cwd=repo)
    _git("checkout", "--", "src/demo.py", cwd=repo)

    proposals = ws / "data" / "alphacode" / "proposals" / proposal_id
    proposals.mkdir(parents=True)
    (proposals / "patch.diff").write_text(patch, encoding="utf-8")
    (proposals / "meta.json").write_text(json.dumps(
        {"rationale": "ضبط قيمة تجريبية", "test_plan": "tests/unit"}, ensure_ascii=False),
        encoding="utf-8")
    return proposals


def _approve(ws: Path, proposal_id: str, sha: str,
             decision: str = "approved") -> None:
    approvals = ws / "data" / "alphacode" / "approvals.jsonl"
    with approvals.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"id": proposal_id, "sha256": sha,
                             "decision": decision, "ts": "2026-11-21T00:00:00Z"},
                            ensure_ascii=False) + "\n")


def test_apply_refuses_without_approval(tmp_path):
    repo = _init_repo(tmp_path)
    ws = _workspace(tmp_path)
    _make_proposal(ws, repo)
    with pytest.raises(alphacode_apply.ApplyError, match="لا موافقة"):
        alphacode_apply.apply_proposal(ws, repo, "p1")
    assert (repo / "src" / "demo.py").read_text(encoding="utf-8") == "VALUE = 1\n"


def test_apply_refuses_sha_mismatch(tmp_path):
    repo = _init_repo(tmp_path)
    ws = _workspace(tmp_path)
    _make_proposal(ws, repo)
    _approve(ws, "p1", "0" * 64)
    with pytest.raises(alphacode_apply.ApplyError, match="تجزئة"):
        alphacode_apply.apply_proposal(ws, repo, "p1")
    assert (repo / "src" / "demo.py").read_text(encoding="utf-8") == "VALUE = 1\n"


def test_apply_refuses_rejected_decision(tmp_path):
    repo = _init_repo(tmp_path)
    ws = _workspace(tmp_path)
    _make_proposal(ws, repo)
    sha = alphacode_apply._sha256(
        ws / "data" / "alphacode" / "proposals" / "p1" / "patch.diff")
    _approve(ws, "p1", sha, decision="rejected")
    with pytest.raises(alphacode_apply.ApplyError, match="ليس approved"):
        alphacode_apply.apply_proposal(ws, repo, "p1")


def test_apply_applies_with_valid_approval(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path)
    ws = _workspace(tmp_path)
    _make_proposal(ws, repo)
    sha = alphacode_apply._sha256(
        ws / "data" / "alphacode" / "proposals" / "p1" / "patch.diff")
    _approve(ws, "p1", sha)
    monkeypatch.setattr(alphacode_apply, "_run_tests", lambda root, full: (True, "ok"))

    outcome = alphacode_apply.apply_proposal(ws, repo, "p1")
    assert outcome["tests_ok"] is True and outcome["rolled_back"] is False
    assert (repo / "src" / "demo.py").read_text(encoding="utf-8") == "VALUE = 2\n"
    assert (ws / "data" / "alphacode" / "backups" / "p1" / "src" / "demo.py").exists()

    # التراجع اليدوي يعيد الأصل بايت-بايت
    alphacode_apply._rollback(ws / "data" / "alphacode", repo, "p1")
    assert (repo / "src" / "demo.py").read_text(encoding="utf-8") == "VALUE = 1\n"
    assert not (ws / "data" / "alphacode" / "backups" / "p1").exists()


def test_apply_auto_rolls_back_on_test_failure(tmp_path, monkeypatch):
    repo = _init_repo(tmp_path)
    ws = _workspace(tmp_path)
    _make_proposal(ws, repo)
    sha = alphacode_apply._sha256(
        ws / "data" / "alphacode" / "proposals" / "p1" / "patch.diff")
    _approve(ws, "p1", sha)
    monkeypatch.setattr(alphacode_apply, "_run_tests", lambda root, full: (False, "FAILED"))

    outcome = alphacode_apply.apply_proposal(ws, repo, "p1")
    assert outcome["rolled_back"] is True
    assert (repo / "src" / "demo.py").read_text(encoding="utf-8") == "VALUE = 1\n"


def test_apply_blocks_escaping_and_sensitive_targets(tmp_path):
    repo = _init_repo(tmp_path)
    with pytest.raises(alphacode_apply.ApplyError, match="غير سليم|حساس|ممنوع|جذر"):
        alphacode_apply._validate_target("../outside.py", repo)
    with pytest.raises(alphacode_apply.ApplyError, match="حساس"):
        alphacode_apply._validate_target("src/.env", repo)
    with pytest.raises(alphacode_apply.ApplyError, match="حساس|حظر"):
        alphacode_apply._validate_target("data/thing.db", repo)


def test_list_proposals_reports_decision(tmp_path):
    repo = _init_repo(tmp_path)
    ws = _workspace(tmp_path)
    _make_proposal(ws, repo, "p1")
    sha = alphacode_apply._sha256(
        ws / "data" / "alphacode" / "proposals" / "p1" / "patch.diff")
    _approve(ws, "p1", sha)

    items = alphacode_apply.list_proposals(ws)
    assert len(items) == 1
    assert items[0]["id"] == "p1"
    assert items[0]["targets"] == ["src/demo.py"]
    assert items[0]["decision"] == "approved"
