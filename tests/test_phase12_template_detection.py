from pathlib import Path

from claims_pipeline.config import get_underwriter_specs
from claims_pipeline.template_detection import detect_underwriter_template


ROOT_DIR = Path(__file__).resolve().parents[1]


def test_detect_underwriter_template_uw1() -> None:
    specs = get_underwriter_specs()
    path = ROOT_DIR / specs["UW1"].file_name
    detection = detect_underwriter_template(path.read_bytes(), specs)
    assert detection["detected_uw"] == "UW1"
    assert detection["detected_score"] >= 0.85


def test_detect_underwriter_template_uw2() -> None:
    specs = get_underwriter_specs()
    path = ROOT_DIR / specs["UW2"].file_name
    detection = detect_underwriter_template(path.read_bytes(), specs)
    assert detection["detected_uw"] == "UW2"
    assert detection["detected_score"] >= 0.85


def test_detect_underwriter_template_uw3() -> None:
    specs = get_underwriter_specs()
    path = ROOT_DIR / specs["UW3"].file_name
    detection = detect_underwriter_template(path.read_bytes(), specs)
    assert detection["detected_uw"] == "UW3"
    assert detection["detected_score"] >= 0.85

