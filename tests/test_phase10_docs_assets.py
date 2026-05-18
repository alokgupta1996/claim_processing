from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]


def test_powerbi_docs_assets_exist() -> None:
    required = [
        ROOT_DIR / "powerbi" / "PHASE10_PBI_BUILD_GUIDE.md",
        ROOT_DIR / "powerbi" / "DAX_MEASURES.md",
        ROOT_DIR / "powerbi" / "PAGE_LAYOUT_CHECKLIST.md",
        ROOT_DIR / "powerbi" / "theme_assignment.json",
    ]
    for path in required:
        assert path.exists(), f"Missing Power BI asset: {path}"

