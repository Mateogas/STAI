"""Relay settings. Every value overridable with a RELAY_-prefixed env var."""

from __future__ import annotations

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="RELAY_", extra="ignore")

    # Bearer token required on /log-batch. Unset disables auth (dev only -
    # always set this before exposing the relay past localhost).
    shared_secret: SecretStr | None = None
    # The mlflow server this relay forwards runs to - must be reachable from
    # this process, but should itself stay bound to localhost/internal-only
    # (OSS MLflow's own tracking API has no auth of its own).
    mlflow_tracking_uri: str = "http://127.0.0.1:5000"


settings = Settings()
