"""Конфигурация discovery-модуля из переменных окружения (issue #17,
по образцу ds_ingestion/src/gar_client/config.py)."""
from __future__ import annotations

import os
from dataclasses import dataclass

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


@dataclass(frozen=True)
class Settings:
    core_api_url: str
    tenant_id: str | None
    user_id: str
    request_timeout_s: float
    probe_max_bytes: int
    probe_timeout_s: float


def load_settings() -> Settings:
    return Settings(
        core_api_url=os.environ.get("GAR_CORE_API_URL", "http://127.0.0.1:8100"),
        tenant_id=os.environ.get("GAR_TENANT_ID") or None,
        user_id=os.environ.get("GAR_USER_ID", "ds-search-discovery"),
        request_timeout_s=float(os.environ.get("GAR_REQUEST_TIMEOUT_S", "30")),
        probe_max_bytes=int(os.environ.get("PROBE_MAX_BYTES", str(2 * 1024 * 1024))),
        probe_timeout_s=float(os.environ.get("PROBE_TIMEOUT_S", "15")),
    )
