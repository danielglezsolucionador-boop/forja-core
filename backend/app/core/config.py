from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    APP_NAME: str = 'FORJA'
    APP_VERSION: str = '0.1.0'
    APP_ENV: str = 'development'
    DEBUG: bool = True
    LOG_LEVEL: str = 'INFO'
    SECRET_KEY: str = ''
    ALLOWED_ORIGINS: str = 'http://localhost:3000,http://127.0.0.1:3000,https://forja-frontend.onrender.com'
    JWT_SECRET_KEY: str = ''
    JWT_ALGORITHM: str = 'HS256'
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    FORJA_ADMIN_USERNAME: str = ''
    FORJA_ADMIN_PASSWORD_HASH: str = ''
    OPENROUTER_API_KEY: str = ''
    OPENROUTER_MODEL: str = 'openrouter/auto'

    @property
    def auth_configured(self) -> bool:
        return bool(
            self.FORJA_ADMIN_USERNAME.strip()
            and self.FORJA_ADMIN_PASSWORD_HASH.strip()
            and self.JWT_SECRET_KEY.strip()
        )

    class Config:
        env_file = None
        env_file_encoding = 'utf-8'


@lru_cache()
def get_settings() -> Settings:
    return Settings()
