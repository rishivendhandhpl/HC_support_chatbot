"""Application configuration loaded from environment variables."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Repo root = two levels up from this file (backend/app/config.py -> repo root).
_REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Strongly-typed settings sourced from the environment / .env file."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # OpenAI
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    openai_embed_model: str = "text-embedding-3-small"
    embedding_dim: int = 1536

    # Database
    database_url: str = "postgresql://hc:hc@localhost:5432/hc_chatbot"

    # CORS / security
    allowed_origins: str = "https://www.haircompounds.com"
    rate_limit_per_min: int = 20

    # Shopify App Proxy: when enabled, /chat requires a valid Shopify-signed
    # request and derives is_pro from the verified logged_in_customer_id instead
    # of trusting the client body. Set the shared secret from your Shopify app.
    require_proxy_signature: bool = False
    shopify_app_secret: str = ""

    # Retrieval
    retrieval_top_k: int = 5

    # Storage backend: "pgvector" (Postgres) or "memory" (file-backed, no DB).
    store_backend: str = "pgvector"
    vector_store_path: str = str(_REPO_ROOT / ".hc_vectorstore.pkl")

    # Knowledge base source files. Absolute by default so /ingest works
    # regardless of the process working directory. Override with FAQ_PATH /
    # SYSTEM_INSTRUCTION_PATH env vars (e.g. in Docker).
    faq_path: str = str(_REPO_ROOT / "HC_FAQ.md")
    system_instruction_path: str = str(_REPO_ROOT / "HC_SYSTEM_INSTRUCTION.md")

    # Company wiki: a directory of long-form markdown docs (one chunk per
    # topic heading). Every *.md file in here is scanned at /ingest time.
    # Override with WIKI_DIR (e.g. in Docker).
    wiki_dir: str = str(_REPO_ROOT / "companyWiki")

    @property
    def allowed_origins_list(self) -> list[str]:
        """ALLOWED_ORIGINS is a comma-separated string; expose it as a list."""
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    def validate_runtime(self) -> list[str]:
        """Return a list of fatal misconfiguration messages.

        Called at startup to fail fast instead of serving a broken deployment.
        Catches the mistakes that silently degrade production: a missing OpenAI
        key, proxy verification turned on without a shared secret, a wildcard
        CORS origin combined with credentialed requests, or selecting the
        Postgres backend without a database URL.
        """
        errors: list[str] = []
        if not self.openai_api_key:
            errors.append("OPENAI_API_KEY is not set.")
        if self.require_proxy_signature and not self.shopify_app_secret:
            errors.append(
                "REQUIRE_PROXY_SIGNATURE is true but SHOPIFY_APP_SECRET is empty; "
                "/chat would reject every request."
            )
        if "*" in self.allowed_origins_list:
            errors.append(
                "ALLOWED_ORIGINS contains '*', which is invalid with credentialed "
                "CORS requests. List explicit origins instead."
            )
        if self.store_backend == "pgvector" and not self.database_url:
            errors.append("STORE_BACKEND is 'pgvector' but DATABASE_URL is empty.")
        return errors


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
