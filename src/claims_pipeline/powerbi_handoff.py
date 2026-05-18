from __future__ import annotations

from pathlib import Path
from shutil import copy2
from typing import Dict


def create_pbix_handoff_package(
    project_root: Path,
    powerbi_dir: Path,
    outputs_dir: Path,
    pbix_file_name: str = "claims_dashboard.pbix",
) -> Dict[str, str]:
    package_dir = outputs_dir / "powerbi_handoff"
    data_dir = package_dir / "data"
    docs_dir = package_dir / "docs"
    data_dir.mkdir(parents=True, exist_ok=True)
    docs_dir.mkdir(parents=True, exist_ok=True)

    copied_data: list[str] = []
    for csv_path in sorted(powerbi_dir.glob("*.csv")):
        target = data_dir / csv_path.name
        copy2(csv_path, target)
        copied_data.append(str(target))

    source_docs = [
        project_root / "powerbi" / "theme_assignment.json",
        project_root / "powerbi" / "PHASE10_PBI_BUILD_GUIDE.md",
        project_root / "powerbi" / "DAX_MEASURES.md",
        project_root / "powerbi" / "PAGE_LAYOUT_CHECKLIST.md",
    ]
    copied_docs: list[str] = []
    for src in source_docs:
        if src.exists():
            target = docs_dir / src.name
            copy2(src, target)
            copied_docs.append(str(target))

    expected_pbix_path = outputs_dir / pbix_file_name
    guide_path = package_dir / "PBIX_BUILD_INSTRUCTIONS.md"
    guide = f"""# PBIX Build Instructions

This package prepares everything needed to build `{pbix_file_name}` manually in Power BI Desktop.

## What this package contains
- Data CSVs: `{data_dir}`
- Build docs + theme: `{docs_dir}`

## Steps to create the PBIX
1. Open **Power BI Desktop**.
2. Import all CSV files from `{data_dir}` using **Get Data > Text/CSV**.
3. Import theme file: `{docs_dir / "theme_assignment.json"}`.
4. Add DAX measures from `{docs_dir / "DAX_MEASURES.md"}`.
5. Build the 5 required pages using `{docs_dir / "PHASE10_PBI_BUILD_GUIDE.md"}`.
6. Run final QA using `{docs_dir / "PAGE_LAYOUT_CHECKLIST.md"}`.
7. Save the file as `{pbix_file_name}` at:
   `{expected_pbix_path}`

## Note
PBIX generation is not automated by Python because `.pbix` is authored and saved by Power BI Desktop.
"""
    guide_path.write_text(guide, encoding="utf-8")

    return {
        "package_dir": str(package_dir),
        "data_dir": str(data_dir),
        "docs_dir": str(docs_dir),
        "build_guide": str(guide_path),
        "expected_pbix_path": str(expected_pbix_path),
        "copied_data_files": str(len(copied_data)),
        "copied_doc_files": str(len(copied_docs)),
    }
