from pathlib import Path

from src.core.emergent_category import EmergentCategoryEngine


def touch(path: Path, content: str = "x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def test_analyze_directory_builds_categories_from_actual_stats(tmp_path):
    for i in range(3):
        touch(tmp_path / f"document-{i}.pdf")
        touch(tmp_path / f"image-{i}.jpg")
    result = EmergentCategoryEngine().analyze_directory(str(tmp_path))
    assert result["total_files"] == 6
    assert set(result["proposed_structure"]["categories"]) == {"مستندات", "صور"}
    assert result["proposed_structure"]["categories"]["مستندات"]["files_count"] == 3


def test_suggest_reorganization_never_proposes_hidden_tree_files(tmp_path):
    for i in range(3):
        touch(tmp_path / f"doc-{i}.pdf")
        touch(tmp_path / f"photo-{i}.jpg")
        touch(tmp_path / ".git" / "objects" / f"secret-{i}.pdf")
        touch(tmp_path / ".ssh" / f"key-{i}.jpg")
    result = EmergentCategoryEngine().suggest_reorganization(str(tmp_path))
    assert result["moves"]
    assert all(".git" not in move["file"] and ".ssh" not in move["file"] for move in result["moves"])
