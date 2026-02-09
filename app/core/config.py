from __future__ import annotations
from dotenv import load_dotenv
import os
import ast
from pydantic_settings import BaseSettings, SettingsConfigDict

# Load environment variables from a .env file into the process environment
load_dotenv()


def str_to_bool(value: str) -> bool:
    """Convert a string value from an environment variable to a boolean."""
    return value.lower() in {"true", "1", "yes", "y", "on"}


def parse_int_or_none(value: str) -> int | None:
    """Safely parse an int; allow None for 'None' (str) input."""
    if value is None:
        return None
    value_stripped = value.strip().lower()
    if value_stripped == "none":
        return None
    try:
        return int(value)
    except Exception:
        return None

def parse_cors_origins(value: str) -> list[str]:
    """
    Parses CORS_ORIGINS from environment variable.
    Accepts Python list literal (e.g. "['a','b']", JSON won't work), or comma-separated string.
    """
    value = value.strip()
    try:
        # Handles .env default and likely .env file input
        origins = ast.literal_eval(value)
        if isinstance(origins, list):
            return [origin.strip(' "\'') for origin in origins]
    except Exception:
        pass
    # fallback: comma-separated
    return [item.strip(' "\'') for item in value.split(",") if item.strip(' "\'')]

class AppSettings(BaseSettings):
    """
    Centralized application settings loaded from environment vars or .env using Pydantic's BaseSettings.
    """
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = os.getenv("APP_ENV", "development")
    app_name: str = os.getenv("APP_NAME", "pantry-server")

    supabase_url: str = os.getenv("SUPABASE_URL", "")
    supabase_anon_key: str = os.getenv("SUPABASE_ANON_KEY", "")
    supabase_service_role_key: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

    google_genai_api_key: str = os.getenv("GOOGLE_GENERATIVE_AI_API_KEY", "")

    port: int = int(os.getenv("PORT", "8000"))

    host: str = os.getenv("HOST", "0.0.0.0")
    reload: bool = str_to_bool(os.getenv("RELOAD", "True"))

    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    gemini_temperature: float = float(os.getenv("GEMINI_TEMPERATURE", "0.0"))
    gemini_max_tokens: int | None = parse_int_or_none(os.getenv("GEMINI_MAX_TOKENS", "1000"))
    gemini_max_retries: int = int(os.getenv("GEMINI_MAX_RETRIES", "2"))
    gemini_embeddings_model: str = os.getenv("GEMINI_EMBEDDINGS_MODEL", "gemini-embedding-001")
    gemini_embeddings_output_dimensionality: int = int(os.getenv("GEMINI_EMBEDDINGS_OUTPUT_DIMENSIONALITY", "768"))

    rate_limit_enabled: bool = str_to_bool(os.getenv("RATE_LIMIT_ENABLED", "True"))
    rate_limit_per_minute: int = int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))

    enable_background_workers: bool = str_to_bool(os.getenv("ENABLE_BACKGROUND_WORKERS", "True"))
    embedding_batch_size: int = int(os.getenv("EMBEDDING_BATCH_SIZE", "50"))
    embedding_worker_interval: int = int(os.getenv("EMBEDDING_WORKER_INTERVAL", "5"))

    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    debug: bool = str_to_bool(os.getenv("DEBUG", "False"))

    cors_origins: list[str] = parse_cors_origins(
        os.getenv(
            "CORS_ORIGINS",
            "['http://localhost:3000', 'http://localhost:5173', '*']"
        )
    )

settings = AppSettings()


def get_settings() -> AppSettings:
    """Return the application settings instance."""
    return settings
