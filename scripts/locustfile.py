from __future__ import annotations

import os
import random
from pathlib import Path

from locust import HttpUser, between, task


def _discover_input_excels(input_dir: Path) -> list[tuple[str, bytes]]:
    if not input_dir.exists():
        return []
    payloads: list[tuple[str, bytes]] = []
    for file_path in sorted(input_dir.glob("*.xlsx")):
        if file_path.name.lower() == "master_schema_template.xlsx":
            continue
        try:
            payloads.append((file_path.name, file_path.read_bytes()))
        except Exception:
            continue
    return payloads


class UploadAndRunUser(HttpUser):
    wait_time = between(1.0, 2.5)

    def on_start(self) -> None:
        input_dir = Path(os.getenv("LOCUST_INPUT_DIR", "/mnt/input"))
        self.upload_endpoint = os.getenv("LOCUST_UPLOAD_ENDPOINT", "/api/upload-and-run")
        self.run_mode = os.getenv("LOCUST_RUN_MODE", "pdf_only")
        self.use_llm_narrative = os.getenv("LOCUST_USE_LLM_NARRATIVE", "true")
        self.max_files_per_request = int(os.getenv("LOCUST_MAX_FILES_PER_REQUEST", "3"))
        self.excel_payloads = _discover_input_excels(input_dir)

    @task(4)
    def upload_and_run(self) -> None:
        if not self.excel_payloads:
            self.client.get("/api/health", name="GET /api/health")
            return

        k = min(len(self.excel_payloads), max(1, self.max_files_per_request))
        selected = random.sample(self.excel_payloads, k=k)
        files = [
            (
                "files",
                (
                    filename,
                    content,
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                ),
            )
            for filename, content in selected
        ]
        data = {
            "run_mode": self.run_mode,
            "use_llm_narrative": self.use_llm_narrative,
            "auto_accept_low_confidence": "true",
            "ai_engine": "sentence_transformer",
        }
        self.client.post(
            self.upload_endpoint,
            files=files,
            data=data,
            timeout=180,
            name="POST /api/upload-and-run",
        )

    @task(1)
    def api_health(self) -> None:
        self.client.get("/api/health", name="GET /api/health")
