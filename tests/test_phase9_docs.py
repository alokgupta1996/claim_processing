from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]


def test_readme_contains_required_sections() -> None:
    readme = (ROOT_DIR / "README.md").read_text(encoding="utf-8")
    required_markers = [
        "# Health Insurance Claims Automation Pipeline",
        "## Architecture",
        "```mermaid",
        "## Local Run (CLI)",
        "## Streamlit UI Run",
        "## Docker Run",
        "## Testing",
        "## Submission Notes",
    ]
    for marker in required_markers:
        assert marker in readme


def test_phase9_checklist_exists() -> None:
    checklist_path = ROOT_DIR / "docs" / "PHASE9_SUBMISSION_CHECKLIST.md"
    assert checklist_path.exists()
    text = checklist_path.read_text(encoding="utf-8")
    assert "Final Assignment Layer (To Complete)" in text

