"""P0 (مراجعة 2026-11-21): انهيار أول تشغيل + مصدر إصدار واحد. تُشغَّل كعمليات فرعية فعلية."""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _run(args, home):
    env = {**os.environ, "HOME": str(home), "USERPROFILE": str(home)}
    return subprocess.run([sys.executable, "-m", "src.main", *args], cwd=ROOT, env=env,
                          capture_output=True, text=True, timeout=120, check=False)


def test_first_run_with_clean_home_creates_data_dir_and_does_not_crash(tmp_path):
    r = _run(["--cli"], tmp_path)
    assert "FileNotFoundError" not in r.stderr + r.stdout
    assert (tmp_path / ".intellifile").is_dir()
    assert (tmp_path / ".intellifile" / "app.log").exists()


def test_cli_version_matches_package_version(tmp_path):
    from src import __version__
    r = _run(["--version"], tmp_path)
    assert r.returncode == 0 and __version__ in (r.stdout + r.stderr)


def test_no_hardcoded_version_literals_remain_in_entry_points():
    """الإصدار من src (src/__init__.py) فقط: لا '2.0.0'/'2.1.0'/'1.0.0' مكتوبة في نقاط الدخول."""
    for rel in ("src/main.py", "src/api/server.py"):
        text = (ROOT / rel).read_text(encoding="utf-8")
        hits = re.findall(r'version\s*=\s*["\'](\d+\.\d+\.\d+)["\']|setApplicationVersion\(["\']', text)
        assert not hits, f"{rel}: إصدار مكتوب يدويًا {hits}"


def test_health_reports_package_version():
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from src import __version__
    from src.api import server
    app = getattr(server, "app", None) or server.create_app()
    r = TestClient(app).get("/api/health")
    assert r.status_code == 200 and r.json()["version"] == __version__
