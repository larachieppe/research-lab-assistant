import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    anthropic_api_key: str | None
    anthropic_model: str
    ncbi_api_key: str | None
    ncbi_email: str | None
    max_papers: int = 8
    max_search_queries: int = 4


def load_settings() -> Settings:
    return Settings(
        anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY"),
        anthropic_model=os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5"),
        ncbi_api_key=os.environ.get("NCBI_API_KEY"),
        ncbi_email=os.environ.get("NCBI_EMAIL"),
    )
