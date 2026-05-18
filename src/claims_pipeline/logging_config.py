from __future__ import annotations

import logging
import logging.config
import os


def setup_logging(service_name: str = "claims-pipeline") -> None:
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "standard": {
                    "format": "%(asctime)s %(levelname)s %(name)s [service=%(service)s] %(message)s"
                }
            },
            "filters": {
                "service_ctx": {
                    "()": "claims_pipeline.logging_config.ServiceContextFilter",
                    "service_name": service_name,
                }
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "standard",
                    "filters": ["service_ctx"],
                }
            },
            "root": {"level": level, "handlers": ["console"]},
        }
    )


class ServiceContextFilter(logging.Filter):
    def __init__(self, service_name: str) -> None:
        super().__init__()
        self._service_name = service_name

    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "service"):
            record.service = self._service_name
        return True
