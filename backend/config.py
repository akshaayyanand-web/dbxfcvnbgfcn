"""Environment-based configuration (no secrets in code). See .env.example."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default)


def _env_list(name: str, default: str) -> list[str]:
    return [v.strip() for v in _env(name, default).split(",") if v.strip()]


@dataclass
class Settings:
    database_url: str = field(default_factory=lambda: _env(
        "FLAME_DATABASE_URL", f"sqlite:///{REPO_ROOT / 'storage' / 'flame.db'}"))
    storage_dir: Path = field(default_factory=lambda: Path(_env("FLAME_STORAGE_DIR", str(REPO_ROOT / "storage"))))
    data_dir: Path = field(default_factory=lambda: Path(_env("FLAME_DATA_DIR", str(REPO_ROOT / "data"))))
    models_dir: Path = field(default_factory=lambda: Path(_env("FLAME_MODELS_DIR", str(REPO_ROOT / "models"))))
    max_upload_bytes: int = field(default_factory=lambda: int(_env("FLAME_MAX_UPLOAD_MB", "500")) * 1024 * 1024)
    max_workers: int = field(default_factory=lambda: int(_env("FLAME_MAX_WORKERS", "2")))
    cors_origins: list[str] = field(default_factory=lambda: _env_list(
        "FLAME_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"))
    api_key: str | None = field(default_factory=lambda: os.environ.get("FLAME_API_KEY") or None)
    rate_limit_per_minute: int = field(default_factory=lambda: int(_env("FLAME_RATE_LIMIT_PER_MINUTE", "30")))
    telemetry_buffer: int = field(default_factory=lambda: int(_env("FLAME_TELEMETRY_BUFFER", "2000")))
    log_level: str = field(default_factory=lambda: _env("FLAME_LOG_LEVEL", "INFO"))

    @property
    def uploads_dir(self) -> Path:
        return self.storage_dir / "uploads"

    @property
    def results_dir(self) -> Path:
        return self.storage_dir / "results"

    def ensure_dirs(self) -> None:
        for d in (self.storage_dir, self.uploads_dir, self.results_dir):
            d.mkdir(parents=True, exist_ok=True)
