"""Runtime configuration loaded from environment variables."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Settings for chainmind.

    All values overridable via env vars prefixed with ``CHAINMIND_``,
    except GROQ_API_KEY which is read raw (it is a third-party secret
    that other tools also expect at that name).
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="CHAINMIND_",
        case_sensitive=False,
        extra="ignore",
    )

    # Groq API. If GROQ_API_KEY is empty, the client will refuse to run
    # and print a helpful message rather than silently degrading.
    groq_api_key: str = Field(default="", description="From console.groq.com/keys")
    groq_model: str = Field(default="llama-3.3-70b-versatile")

    # On-chain
    rpc_url: str = Field(default="https://ethereum.publicnode.com")

    # Report
    blocks_to_scan: int = Field(default=5, gt=0, le=50)
    max_tokens: int = Field(default=2048, gt=0, le=8192)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
