"""
Core configuration using pydantic-settings v2.
All settings are loaded from environment variables / .env file.
"""
from typing import Any, List, Optional, Union
from pydantic import AnyHttpUrl, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Application
    APP_ENV: str = "development"
    SECRET_KEY: str = "changeme"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    ALGORITHM: str = "HS256"
    PROJECT_NAME: str = "Marketplace API"
    API_V1_STR: str = "/api/v1"

    # Database
    MYSQL_HOST: str = "localhost"
    MYSQL_PORT: int = 3306
    MYSQL_USER: str = "marketplace"
    MYSQL_PASSWORD: str = "marketplace_password"
    MYSQL_DB: str = "marketplace"
    DATABASE_URL: str = "mysql+asyncmy://marketplace:marketplace_password@localhost:3306/marketplace"

    # Redis / Celery
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

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

    # Object storage (optional — if unset, uploads go to the local ./uploads dir)
    S3_ENDPOINT: str = ""
    S3_BUCKET: str = ""
    S3_ACCESS_KEY: str = ""
    S3_SECRET_KEY: str = ""
    S3_PUBLIC_URL: str = ""

    # Full-text search (optional — if unset, search falls back to DB ILIKE)
    MEILI_URL: str = ""
    MEILI_KEY: str = ""

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            import json
            return json.loads(v)
        return v

    # Default admin credentials (used only for initial seed)
    FIRST_SUPERUSER_EMAIL: str = "admin@marketplace.com"
    FIRST_SUPERUSER_PASSWORD: str = "admin123"
    FIRST_SUPERUSER_NAME: str = "Super Admin"

    # File uploads
    UPLOAD_DIR: str = "/app/uploads"
    MAX_UPLOAD_SIZE_MB: int = 10

    @property
    def is_development(self) -> bool:
        return self.APP_ENV == "development"


settings = Settings()
