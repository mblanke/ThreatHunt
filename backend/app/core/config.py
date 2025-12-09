from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings"""
    app_name: str = "VelociCompanion"
    database_url: str = "postgresql://postgres:postgres@db:5432/velocicompanion"
    secret_key: str = "your-secret-key-change-in-production-min-32-chars-long"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 30
    algorithm: str = "HS256"
    
    # Email settings (for password reset)
    smtp_host: str = "localhost"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    from_email: str = "noreply@velocicompanion.com"
    
    # WebSocket settings
    ws_enabled: bool = True

    class Config:
        env_file = ".env"


settings = Settings()
