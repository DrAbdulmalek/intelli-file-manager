"""Base installation must not force a remote VCS dependency."""
from pathlib import Path


def test_ocr_core_vcs_dependency_is_opt_in_and_commit_pinned():
    base = Path("requirements.txt").read_text(encoding="utf-8")
    optional = Path("requirements-ocr-core.txt").read_text(encoding="utf-8")

    assert "git+" not in base
    assert "marathon-ocr-core[tesseract]" in optional
    assert "@5613a1c05f7b657678a810b96c6ba5cab3b92e53" in optional
