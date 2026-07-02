"""
Core configuration using pydantic-settings v2.
All settings are loaded from environment variables / .env file.
"""
import ssl as ssl_lib
from typing import Any, List, Optional, Union
from pydantic import AliasChoices, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    APP_ENV: str = "development"
    SECRET_KEY: str = "changeme"
    # JWT signing secret for refresh tokens. The deploy infra passes it separately
    # (REFRESH_SECRET_KEY); if empty it falls back to SECRET_KEY (single-secret mode).
    REFRESH_SECRET_KEY: str = ""
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    # Infra passes JWT_ALGORITHM; locally ALGORITHM also works.
    ALGORITHM: str = Field(
        default="HS256",
        validation_alias=AliasChoices("ALGORITHM", "JWT_ALGORITHM"),
    )
    PROJECT_NAME: str = "Marketplace API"
    API_V1_STR: str = "/api/v1"

    # Database — PostgreSQL (Yandex Managed PostgreSQL via the 6432 pooler port).
    # In the cloud, Ansible passes a fully-formed DATABASE_URL plus the DB_* parts.
    # Locally, DATABASE_URL is assembled from the DB_* parts if left empty.
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_USER: str = "marketplace"
    DB_PASSWORD: str = "marketplace_password"
    DB_NAME: str = "marketplace"
    DATABASE_URL: str = ""
    # Yandex Managed PostgreSQL requires TLS. Set DB_SSL=true in the cloud and point
    # DB_SSL_ROOT_CERT at the Yandex CA bundle (e.g. /app/certs/root.crt) for full
    # verification; with DB_SSL=true and no cert, the system trust store is used.
    DB_SSL: bool = False
    DB_SSL_ROOT_CERT: str = ""

    # Redis / Celery. Infra passes a single REDIS_URL (with password); the Celery
    # broker/result backend default to it when not set explicitly.
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = ""
    CELERY_RESULT_BACKEND: str = ""

    # YooKassa
    YOOKASSA_SHOP_ID: str = ""
    YOOKASSA_SECRET_KEY: str = ""
    YOOKASSA_RETURN_URL: str = "http://localhost:3000/payment/return"

    # Фискализация чеков (54-ФЗ) через встроенную фискализацию ЮKassa.
    # Если выключено — объект receipt не прикладывается к платежу и чеки не пробиваются.
    FISCAL_ENABLED: bool = True
    # Платформенные значения по умолчанию (используются, если у продавца не заданы свои).
    # vat_code: 1=без НДС, 2=0%, 3=10%, 4=20%, 5=10/110, 6=20/120.
    FISCAL_VAT_CODE: int = 1
    # tax_system_code: 1=ОСН, 2=УСН доход, 3=УСН доход-расход, 4=ЕНВД, 5=ЕСХН, 6=Патент.
    # 0 — не передавать СНО в чеке (допустимо, если на кассе одна СНО).
    FISCAL_TAX_SYSTEM_CODE: int = 0
    # Признак предмета расчёта для товаров (commodity) и услуг доставки (service).
    FISCAL_PAYMENT_SUBJECT: str = "commodity"
    # Признак способа расчёта: full_prepayment (полная предоплата) для онлайн-оплаты до отгрузки.
    FISCAL_PAYMENT_MODE: str = "full_prepayment"
    # Агентская схема (маркетплейс как агент): прикладывать к позициям supplier+agent_type.
    # Требует, чтобы касса платформы была настроена на агентскую схему в ОФД.
    FISCAL_AGENT_SCHEME: bool = False

    # Поддержка: SLA (часы). Если за это время нет первого ответа / решения — эскалация.
    SUPPORT_SLA_FIRST_RESPONSE_HOURS: int = 4
    SUPPORT_SLA_RESOLUTION_HOURS: int = 24
    # Авто-назначать просроченные неназначенные обращения наименее загруженному агенту.
    SUPPORT_AUTO_ASSIGN: bool = True

    # CDEK
    CDEK_CLIENT_ID: str = ""
    CDEK_CLIENT_SECRET: str = ""
    CDEK_API_URL: str = "https://api.edu.cdek.ru/v2"

    # Ozon Delivery
    OZON_API_KEY: str = ""
    OZON_CLIENT_ID: str = ""

    # Yandex Delivery
    YANDEX_DELIVERY_TOKEN: str = ""

    # Russian Post (Почта России)
    RUSSIAN_POST_TOKEN: str = ""
    RUSSIAN_POST_ACCESS_KEY: str = ""

    # CORS
    BACKEND_CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:8000"]

    # Frontend URL (used to build links in emails, e.g. password reset)
    FRONTEND_URL: str = "http://localhost:3000"

    # SMTP (optional — if SMTP_HOST is empty, emails are logged instead of sent)
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "no-reply@marketplace.com"

    # Object storage (optional — if unset, uploads go to the local ./uploads dir).
    # S3_BUCKET holds PUBLIC assets (product images, media — per-object public-read).
    # S3_PRIVATE_BUCKET holds PRIVATE assets (digital goods, HLS, KYC) served only
    # via presigned URLs / gated proxy. If S3_PRIVATE_BUCKET is empty it falls back
    # to S3_BUCKET (single-bucket mode), preserving older deployments.
    S3_ENDPOINT: str = ""
    S3_BUCKET: str = ""
    S3_PRIVATE_BUCKET: str = ""
    S3_ACCESS_KEY: str = ""
    S3_SECRET_KEY: str = ""
    S3_PUBLIC_URL: str = ""

    # Full-text search (optional — if unset, search falls back to DB ILIKE)
    MEILI_URL: str = ""
    MEILI_KEY: str = ""

    # VK Market import (optional — empty app id disables the integration UI).
    # Register the app at dev.vk.com; the redirect URI must EXACTLY match the
    # one configured there (HTTPS in production).
    VK_APP_ID: str = ""
    VK_APP_SECRET: str = ""
    VK_REDIRECT_URI: str = ""  # e.g. https://<домен>/api/v1/seller/integrations/vk/callback
    VK_API_VERSION: str = "5.199"

    # Caching (Redis). When enabled, hot read paths (categories, currency rates,
    # homepage) are cached. Falls back transparently if Redis is unreachable.
    CACHE_ENABLED: bool = True
    CACHE_DEFAULT_TTL: int = 300

    # Observability
    SENTRY_DSN: str = ""                 # empty → Sentry disabled
    SENTRY_TRACES_SAMPLE_RATE: float = 0.0
    METRICS_ENABLED: bool = True         # expose Prometheus /metrics per service
    APP_VERSION: str = "1.0.0"

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            v = v.strip()
            if v.startswith("["):
                import json
                return json.loads(v)
            # Allow a plain comma-separated list too (easier to pass via env).
            return [o.strip() for o in v.split(",") if o.strip()]
        return v

    @model_validator(mode="after")
    def _assemble_derived(self) -> "Settings":
        # Build the SQLAlchemy URL from parts if the infra didn't pass a full one.
        if not self.DATABASE_URL:
            self.DATABASE_URL = (
                f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}"
                f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
            )
        # Refresh tokens fall back to the access secret in single-secret mode.
        if not self.REFRESH_SECRET_KEY:
            self.REFRESH_SECRET_KEY = self.SECRET_KEY
        # Celery shares the single REDIS_URL the infra provides unless overridden.
        if not self.CELERY_BROKER_URL:
            self.CELERY_BROKER_URL = self.REDIS_URL
        if not self.CELERY_RESULT_BACKEND:
            self.CELERY_RESULT_BACKEND = self.REDIS_URL
        return self

    @property
    def db_connect_args(self) -> dict:
        """asyncpg connect_args for TLS. asyncpg takes an ssl context/flag, not a
        URL `sslmode`, so SSL is configured here rather than in DATABASE_URL."""
        if not self.DB_SSL:
            return {}
        if self.DB_SSL_ROOT_CERT:
            return {"ssl": ssl_lib.create_default_context(cafile=self.DB_SSL_ROOT_CERT)}
        return {"ssl": True}

    # Default admin credentials (used only for initial seed)
    FIRST_SUPERUSER_EMAIL: str = "admin@marketplace.com"
    FIRST_SUPERUSER_PASSWORD: str = "admin123"
    FIRST_SUPERUSER_NAME: str = "Super Admin"

    # File uploads
    UPLOAD_DIR: str = "/app/uploads"
    MAX_UPLOAD_SIZE_MB: int = 10
    # Max size for a single digital-product file (PDF/zip/video/etc.). Stored
    # privately and delivered only to entitled buyers.
    MAX_DIGITAL_UPLOAD_MB: int = 500

    @property
    def is_development(self) -> bool:
        return self.APP_ENV == "development"


settings = Settings()
