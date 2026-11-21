import os
from typing import List, Tuple
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./data/app.db"
    LLM_API_KEYS: str = "test-key-1,test-key-2"
    ALLOWED_ORIGINS: str = "*"
    ENABLE_FAILURE_SIMULATION: bool = True
    LLM_MODEL: str = "gemini/gemini-2.0-flash"
    DEFAULT_SYSTEM_PROMPT: str = "You are a helpful and concise AI assistant."
    PORT: int = 8000
    HOST: str = "0.0.0.0"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    def get_api_keys(self) -> List[Tuple[str, str]]:
        """
        Returns an ordered list of (key_id, api_key) pairs, e.g.
        [("key_1", "key-val-1"), ("key_2", "key-val-2")]
        Key IDs are key_1, key_2, ... strictly in order.
        """
        raw_keys = [k.strip() for k in self.LLM_API_KEYS.split(",") if k.strip()]
        if not raw_keys:
            raw_keys = ["test-key-1", "test-key-2"]
        return [(f"key_{i+1}", key) for i, key in enumerate(raw_keys)]

    def get_allowed_origins(self) -> List[str]:
        if not self.ALLOWED_ORIGINS or self.ALLOWED_ORIGINS.strip() == "*":
            return ["*"]
        origins = []
        for o in self.ALLOWED_ORIGINS.split(","):
            cleaned = o.strip()
            if cleaned:
                origins.append(cleaned)
                stripped = cleaned.rstrip("/")
                if stripped != cleaned:
                    origins.append(stripped)
        return origins


settings = Settings()
