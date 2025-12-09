from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings"""
    app_name: str = "VelociCompanion"
    database_url: str = "postgresql://postgres:postgres@db:5432/velocicompanion"
    secret_key: str = "your-secret-key-change-in-production-min-32-chars-long"
    access_token_expire_minutes: int = 30
    algorithm: str = "HS256"

    class Config:
        env_file = ".env"


settings = Settings()
