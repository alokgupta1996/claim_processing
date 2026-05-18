# 2GB Load Test (Locust API Upload + LLM Usage Logging)

This package includes a reproducible end-to-end load test flow:

- `scripts/locustfile.py` (multipart upload profile to `/api/upload-and-run`)
- `scripts/run_locust_loadtest_2gb.ps1` (runs API under 2GB, executes Locust, runs optional pipeline passes, and writes summaries)

## Run

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run_locust_loadtest_2gb.ps1 -Image claims-pipeline-ui:newfolder -Users 8 -SpawnRate 2 -RunTime 60s -RunMode pdf_only -MaxFilesPerRequest 3 -PipelineRuns 2
```

## Outputs

Generated under `outputs/<run_id>/`:

- `load_test_summary.json`
- `load_test_summary.md`
- `usage_metrics.json`
- Locust raw CSV stats (`locust_*.csv`)

## Token / API Call Metrics

Token and API usage are tracked in pipeline code and written to `usage_metrics.json`:

- `api_calls_total`
- `api_calls_by_kind` (`chat_completions`, `embeddings`)
- `input_tokens`
- `output_tokens`
- `total_tokens`

If OpenAI/Azure OpenAI keys are not configured, counts will remain `0`.

## Notes

- Locust now sends real `.xlsx` uploads to `POST /api/upload-and-run`.
- The endpoint auto-detects templates, auto-maps columns, and runs the same backend pipeline.
- `-PipelineRuns N` still performs additional direct pipeline runs under the same 2GB cap to capture stable token/API usage samples.
