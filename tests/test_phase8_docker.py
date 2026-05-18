from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]


def test_dockerfile_contains_required_runtime_contract() -> None:
    dockerfile = (ROOT_DIR / "Dockerfile").read_text(encoding="utf-8")
    assert "FROM python:3.12-slim" in dockerfile
    assert "ENV PYTHONPATH=/app/src" in dockerfile
    assert "EXPOSE 8501" in dockerfile
    assert "streamlit" in dockerfile


def test_compose_defines_streamlit_and_pipeline_services() -> None:
    compose = (ROOT_DIR / "docker-compose.yml").read_text(encoding="utf-8")
    assert "streamlit:" in compose
    assert "pipeline:" in compose
    assert "8501:8501" in compose
    assert "profiles: [\"batch\"]" in compose
    assert "OPENAI_API_KEY" in compose


def test_dockerignore_excludes_generated_artifacts() -> None:
    dockerignore = (ROOT_DIR / ".dockerignore").read_text(encoding="utf-8")
    assert "outputs/" in dockerignore
    assert "data/processed/" in dockerignore
    assert ".pytest_cache/" in dockerignore

