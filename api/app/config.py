"""Settings for the API service.

The repo-root .env is resolved from this file's location (not the CWD), so the
server can be started from any directory — `pnpm dev:api`, `uv run` from api/,
a container, etc. Real environment variables still take precedence over .env
values (pydantic-settings precedence).
"""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]  # api/app/config.py -> app -> api -> repo root


class Settings(BaseSettings):
	model_config = SettingsConfigDict(
		env_file=REPO_ROOT / ".env",
		env_file_encoding="utf-8",
		case_sensitive=False,
		extra="ignore",
	)

	atlas_uri: str = ""
	atlas_db: str = ""
	mongodb_uri: str = ""
	mongodb_db: str = ""


settings = Settings()


def resolve_db_config() -> tuple[str, str, str]:
	"""Mirror web/src/lib/server/db.ts: Atlas if ATLAS_URI is set, else local.

	Returns (uri, database-name, target-label). DB name falls back to
	root-cause_db. Raises RuntimeError if both URIs are empty, so the app
	fails fast at startup.
	"""
	if s := settings.atlas_uri.strip():
		return (
			s,
			settings.atlas_db.strip() or settings.mongodb_db.strip() or "root-cause_db",
			"Atlas",
		)
	if s := settings.mongodb_uri.strip():
		return (s, settings.mongodb_db.strip() or "root-cause_db", "Local")
	raise RuntimeError(
		"Database configuration missing: set ATLAS_URI or MONGODB_URI in the repo-root .env"
	)
