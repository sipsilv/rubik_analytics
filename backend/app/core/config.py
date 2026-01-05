from pydantic_settings import BaseSettings
from typing import Optional, List, Union

import os

class Settings(BaseSettings):
    # Base directory calculation (backend/app/core/config.py -> backend/)
    BASE_DIR: str = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    # Project root (backend/ -> root/)
    PROJECT_ROOT: str = os.path.dirname(BASE_DIR)

    # Data directory - reads from DATA_DIR environment variable, falls back to default relative path
    # Normalize and strip to handle both mixed path separators and trailing whitespace
    # This is critical on Windows where batch scripts can introduce trailing spaces
    DATA_DIR: str = os.path.normpath(os.getenv("DATA_DIR", os.path.join(PROJECT_ROOT, "data")).strip())
    
    # Database (legacy - now using connection manager)
    DATABASE_URL: str = f"sqlite:///{os.path.join(DATA_DIR, 'auth/sqlite/auth.db')}"
    DUCKDB_PATH: str = os.path.join(DATA_DIR, "analytics/duckdb")
    
    # JWT
    JWT_SECRET_KEY: str
    JWT_SYSTEM_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480  # 8 hours
    IDLE_TIMEOUT_MINUTES: int = 30
    
    # Encryption (Fernet key for encrypting connection credentials)
    # Generate a new key with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    # IMPORTANT: Change this in production! Store in .env file as ENCRYPTION_KEY
    # Note: Fernet keys must be valid base64url-encoded strings (44 characters, no leading/trailing dashes)
    ENCRYPTION_KEY: str
    
    # CORS - can be comma-separated string or list
    CORS_ORIGINS: Union[str, List[str]] = "http://localhost:3000"
    
    # TrueData Connection Defaults
    TRUEDATA_DEFAULT_AUTH_URL: str = "https://auth.truedata.in/token"
    TRUEDATA_DEFAULT_WEBSOCKET_PORT: str = "8086"
    
    @property
    def cors_origins_list(self) -> List[str]:
        if not self.CORS_ORIGINS:
            return ["http://localhost:3000"]
        """Convert CORS_ORIGINS to list format"""
        if isinstance(self.CORS_ORIGINS, list):
            origins =  self.CORS_ORIGINS
        else:
            origins = [
                    origin.strip()
                    for origin in self.CORS_ORIGINS.split(",")
                    if origin.strip()
                    ]
        if "*" in origins:
            raise ValueError(
                "CORS_ORIGINS cannot contain '*' when allow_credentials=True. "
                "Use explicit origins like http://localhost:3000"
            )
            # Split by comma and strip whitespace
        return origins
    
    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
