# Clean GitHub Upload Package

This folder is a clean, upload-ready package for GitHub.

## Build Docker image

```bash
docker build -t claims-pipeline-ui:latest .
```

## Run Streamlit service

```bash
docker run -d --name claims-pipeline-ui -p 8501:8501 claims-pipeline-ui:latest
```

## Optional Docker Compose

```bash
docker compose up -d streamlit
```

Generated/runtime files are excluded by `.gitignore`.

## 2GB Load Test

Locust-based load test and usage logging are included.

See:
- `docs/LOAD_TEST_2GB.md`
- `scripts/run_locust_loadtest_2gb.ps1`
