"""Configuration.

No secret ever has a default value here. A missing required credential should fail
loudly at startup rather than silently falling back to something that half-works.
"""

from __future__ import annotations

from enum import Enum
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Backend(str, Enum):
    """Which implementation a service resolves to.

    ``STUB`` is the default everywhere: the full pipeline runs, and the full test
    suite passes, with zero credentials. See docs/adr/0005-stub-first-service-protocols.md.
    """

    STUB = "stub"
    REAL = "real"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    log_level: str = "INFO"
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    database_url: str = "postgresql+asyncpg://pocket:pocket@localhost:5432/pocket_ai"
    media_root: Path = Path("./data/media")

    # Google Drive
    google_client_id: str = ""
    google_client_secret: str = ""
    google_oauth_redirect_uri: str = "http://localhost:8000/api/v1/drive/oauth/callback"
    drive_root_folder_name: str = "Pocket.ai Studio"

    # LLM
    anthropic_api_key: str = ""
    llm_model_reasoning: str = "claude-opus-5"
    llm_model_fast: str = "claude-haiku-4-5-20251001"

    # --- Pocket API (source of recordings) ---
    pocket_api_key: str = ""
    pocket_api_base_url: str = "https://api.heypocketai.com"
    # Shared secret for verifying webhook signatures. Without it the webhook refuses
    # every delivery rather than trusting unauthenticated callers.
    pocket_webhook_secret: str = ""
    pocket_webhook_signature_header: str = "X-Pocket-Signature"
    pocket_webhook_timestamp_header: str = "X-Pocket-Timestamp"
    # Deliveries older than this are rejected, so a captured request cannot be replayed.
    pocket_webhook_tolerance_seconds: int = 300

    # Diarization
    huggingface_token: str = ""
    diarization_backend: Backend = Backend.STUB
    min_snr_db: float = 10.0
    max_clipping_ratio: float = 0.05

    # Retrieval
    chroma_persist_dir: Path = Path("./data/chroma")

    @property
    def storage_backend(self) -> Backend:
        """Drive is usable only with a full OAuth client configured."""
        if self.google_client_id and self.google_client_secret:
            return Backend.REAL
        return Backend.STUB

    @property
    def llm_backend(self) -> Backend:
        return Backend.REAL if self.anthropic_api_key else Backend.STUB

    @property
    def pocket_backend(self) -> Backend:
        return Backend.REAL if self.pocket_api_key else Backend.STUB

    @property
    def webhook_configured(self) -> bool:
        return bool(self.pocket_webhook_secret)

    @property
    def is_development(self) -> bool:
        return self.app_env == "development"

    @property
    def drive_stub_root(self) -> Path:
        """Where StubStorageService mirrors the Drive folder contract."""
        return self.media_root / "drive-stub"

    def using_stubs(self) -> list[str]:
        """Names of services currently backed by stubs.

        Surfaced in API responses so stub output is never mistaken for real results.
        """
        active = []
        if self.pocket_backend is Backend.STUB:
            active.append("pocket")
        if self.storage_backend is Backend.STUB:
            active.append("storage")
        if self.llm_backend is Backend.STUB:
            active.append("llm")
        if self.diarization_backend is Backend.STUB:
            active.append("diarization")
        return active


@lru_cache
def get_settings() -> Settings:
    return Settings()
