from __future__ import annotations
from dotenv import load_dotenv
import os
from pydantic_settings import BaseSettings, SettingsConfigDict
load_dotenv()

class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_env: str = os.getenv("ENVIRONMENT", "development")
    app_name: str = "pantry-server"

    supabase_url: str | None = os.getenv("SUPABASE_URL", "")
    supabase_anon_key: str | None = os.getenv("SUPABASE_ANON_KEY", "")

    google_genai_api_key: str | None = os.getenv("GOOGLE_GENERATIVE_AI_API_KEY", "")
    port: int = int(os.getenv("PORT", "8000"))

settings = AppSettings()
