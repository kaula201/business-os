# backend/app/core/config.py
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

# Known placeholders. The process must not boot with any of these.
_INSECURE_JWT_SECRETS = {
    "jwt-secret-change-me",
    "jwt-secret-change-me-in-production-min-32-characters",
    "change-me",
    "change-me-in-production",
    "changeme",
    "secret",
    "your-super-secret-key-change-in-production",
    "change-me-to-a-random-64-char-hex-string-now-1234567890abcdef",
}

RELAXED_ENVS = {"development", "dev", "test", "sandbox"}
PRODUCTION_ENVS = {"production", "prod"}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    # Application
    APP_NAME: str = "Business OS"
    APP_VERSION: str = "1.0.0"
    # Production-safe default. Development and tests must set APP_ENV explicitly.
    APP_ENV: str = "production"
    DEBUG: bool = False
    SECRET_KEY: str = ""
    
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/business_os"
    # Optional superuser URL used only by migrate_schema / Alembic.
    # Production compose sets this so the first boot can create business_os_app.
    # Empty means "use DATABASE_URL" (local dev and CI).
    MIGRATION_DATABASE_URL: str = ""
    DATABASE_ECHO: bool = False
    # Connection pool for 20-30 concurrent users / 100K+ records
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_TIMEOUT: int = 30
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # JWT — no insecure default. Empty or a known placeholder refuses to start.
    JWT_SECRET_KEY: str = ""
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    
    # OpenAI
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o"
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"

    # Revenue Service (RS.ge) WayBill SOAP API
    RS_WAYBILL_URL: str = "https://services.rs.ge/WayBillService/WayBillService.asmx"
    RS_SERVICE_USER: str = ""
    RS_SERVICE_PASSWORD: str = ""

    # National Bank of Georgia unattended daily sync
    NBG_AUTO_SYNC_ENABLED: bool = True
    NBG_SYNC_HOUR: int = 18
    NBG_SYNC_MINUTE: int = 5
    NBG_SYNC_TIMEZONE: str = "Asia/Tbilisi"

    # Monthly financial period-close automation (depreciation + FX + deferred)
    FINANCIAL_AUTO_ENABLED: bool = True
    
    # CORS — explicit allowlist only. "*" is rejected at startup.
    CORS_ORIGINS: str = "http://localhost:5173"
    FRONTEND_URL: str = "http://localhost:5173"
    # Optional extra restriction for outbound webhooks (comma-separated hosts).
    # Private, link-local, and metadata targets are blocked even when unset.
    WEBHOOK_URL_ALLOWLIST: str = ""
    # Payment gateway (Stripe). When STRIPE_SECRET_KEY is set, real charges are
    # attempted; otherwise the checkout falls back to sandbox (demo) mode.
    STRIPE_SECRET_KEY: str = ""
    STRIPE_PUBLISHABLE_KEY: str = ""
    # SaaS billing webhook signature secret (HMAC-SHA256). When set, incoming
    # /saas/webhook payloads must carry a valid signature; unset = sandbox-only.
    SAAS_WEBHOOK_SECRET: str = ""
    # Daily SaaS billing scheduler (expire lapsed trials, bill due active subs).
    SAAS_BILLING_AUTO_ENABLED: bool = True
    SAAS_BILLING_HOUR: int = 3
    SAAS_BILLING_MINUTE: int = 0
    SAAS_BILLING_TIMEZONE: str = "Asia/Tbilisi"
    # POS payment terminals — TBC Pay / BOG Pay merchant credentials.
    # When set, terminal charges hit the real provider API; otherwise sandbox.
    TBC_MERCHANT_ID: str = ""
    TBC_SECRET_KEY: str = ""
    BOG_CLIENT_ID: str = ""
    BOG_SECRET_KEY: str = ""
    # Certified fiscal device (Georgia fiscal receipt printer).
    FISCAL_DEVICE_URL: str = ""
    FISCAL_DEVICE_TOKEN: str = ""
    
    # SMTP (real email sending; falls back to sandbox when unset)
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_USE_TLS: bool = True
    FROM_EMAIL: str = "noreply@business-os.ge"
    FROM_NAME: str = "Business OS"

    # Pagination
    DEFAULT_PAGE_SIZE: int = 20
    MAX_PAGE_SIZE: int = 100

    @model_validator(mode="after")
    def _reject_insecure_defaults(self):
        key = (self.JWT_SECRET_KEY or "").strip()
        if not key or key.lower() in _INSECURE_JWT_SECRETS:
            raise ValueError(
                "JWT_SECRET_KEY is empty or uses an insecure default. "
                "Set a unique secret (python -c \"import secrets; print(secrets.token_urlsafe(48))\") "
                "before starting the app."
            )
        env = (self.APP_ENV or "production").strip().lower()
        if env in PRODUCTION_ENVS and len(key) < 32:
            raise ValueError(
                "JWT_SECRET_KEY must be at least 32 characters when APP_ENV is production."
            )
        origins = [part.strip() for part in (self.CORS_ORIGINS or "").split(",") if part.strip()]
        if not origins or any(origin == "*" for origin in origins):
            raise ValueError(
                "CORS_ORIGINS must be an explicit comma-separated allowlist. "
                "Wildcard '*' is not allowed."
            )
        self.JWT_SECRET_KEY = key
        self.APP_ENV = env
        self.CORS_ORIGINS = ",".join(origins)
        return self

    def migration_database_url(self) -> str:
        """URL for schema migrations. Runtime traffic stays on DATABASE_URL."""
        configured = (self.MIGRATION_DATABASE_URL or "").strip()
        return configured or self.DATABASE_URL

    def is_production(self) -> bool:
        return self.APP_ENV in PRODUCTION_ENVS

    def is_relaxed_env(self) -> bool:
        """Development, test, and sandbox may keep demo-only shortcuts."""
        return self.APP_ENV in RELAXED_ENVS

    def allows_demo_seed(self) -> bool:
        return self.APP_ENV in {"development", "dev"}

    def cors_origin_list(self) -> list[str]:
        return [part.strip() for part in self.CORS_ORIGINS.split(",") if part.strip()]


settings = Settings()
