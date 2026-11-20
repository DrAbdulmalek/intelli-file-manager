"""Regression guard: secret scanner output must never include matched values."""
from pathlib import Path


def test_verify_secret_scan_reports_paths_not_secret_lines():
    script = Path("scripts/verify.sh").read_text(encoding="utf-8")
    assert 'git grep -I -l -E "$SECRET_PATTERNS"' in script
    assert "SECRET_HITS" not in script
    assert 'git grep -I -n -E "$SECRET_PATTERNS"' not in script
