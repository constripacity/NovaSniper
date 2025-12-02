from pydantic import BaseSettings, Field


class Settings(BaseSettings):
    database_url: str = Field("sqlite:///./tracked_products.db", env="DATABASE_URL")
    check_interval_seconds: int = Field(300, env="CHECK_INTERVAL_SECONDS")

    smtp_host: str | None = Field(None, env="SMTP_HOST")
    smtp_port: int | None = Field(None, env="SMTP_PORT")
    smtp_user: str | None = Field(None, env="SMTP_USER")
    smtp_password: str | None = Field(None, env="SMTP_PASSWORD")
    from_email: str | None = Field(None, env="FROM_EMAIL")

    amazon_access_key: str | None = Field(None, env="AMAZON_ACCESS_KEY")
    amazon_secret_key: str | None = Field(None, env="AMAZON_SECRET_KEY")
    amazon_partner_tag: str | None = Field(None, env="AMAZON_PARTNER_TAG")
    ebay_app_id: str | None = Field(None, env="EBAY_APP_ID")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


def get_settings() -> Settings:
    return Settings()
