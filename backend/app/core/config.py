# backend/app/core/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    # Application
    APP_NAME: str = "Business OS"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    SECRET_KEY: str = "change-me-in-production"
    
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/business_os"
    DATABASE_ECHO: bool = False
    # Connection pool for 20-30 concurrent users / 100K+ records
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_TIMEOUT: int = 30
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # JWT
    JWT_SECRET_KEY: str = "jwt-secret-change-me"
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
    
    # CORS
    CORS_ORIGINS: str = "*"
    FRONTEND_URL: str = "http://localhost:5173"
    # Payment gateway (Stripe). When STRIPE_SECRET_KEY is set, real charges are
    # attempted; otherwise the checkout falls back to sandbox (demo) mode.
    STRIPE_SECRET_KEY: str = ""
    STRIPE_PUBLISHABLE_KEY: str = ""
    # SaaS billing webhook signature secret (HMAC-SHA256). When set, incoming
    # /saas/webhook payloads must carry a valid signature; unset = sandbox-only.
    SAAS_WEBHOOK_SECRET: str = ""
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
    
settings = Settings()
