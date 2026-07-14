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
    site_username: str | None
    site_password: str | None
    session_secret: str | None
    google_client_id: str | None
    google_client_secret: str | None
    allowed_email: str | None
    max_papers: int = 8
    max_search_queries: int = 4


def load_settings() -> Settings:
    return Settings(
        anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY"),
        anthropic_model=os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5"),
        ncbi_api_key=os.environ.get("NCBI_API_KEY"),
        ncbi_email=os.environ.get("NCBI_EMAIL"),
        site_username=os.environ.get("SITE_USERNAME"),
        site_password=os.environ.get("SITE_PASSWORD"),
        session_secret=os.environ.get("SESSION_SECRET"),
        google_client_id=os.environ.get("GOOGLE_CLIENT_ID"),
        google_client_secret=os.environ.get("GOOGLE_CLIENT_SECRET"),
        allowed_email=os.environ.get("ALLOWED_EMAIL"),
    )
