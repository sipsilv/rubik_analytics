from pydantic_settings import BaseSettings
from typing import Optional, List, Union

class Settings(BaseSettings):
    # Data directory
    DATA_DIR: str = r"C:/Users/jallu/OneDrive/pgp/Python/Stock predictor/rubik-analytics/data"
    
    # Database (legacy - now using connection manager)
    DATABASE_URL: str = "sqlite:///C:/Users/jallu/OneDrive/pgp/Python/Stock predictor/rubik-analytics/data/auth/sqlite/auth.db"
    DUCKDB_PATH: str = r"C:/Users/jallu/OneDrive/pgp/Python/Stock predictor/rubik-analytics/data/analytics/duckdb"
    
    # JWT
    JWT_SECRET_KEY: str = "your-secret-key-change-in-production"
    JWT_SYSTEM_SECRET_KEY: str = "your-system-secret-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480  # 8 hours
    IDLE_TIMEOUT_MINUTES: int = 30
    
    # Encryption (Fernet key for encrypting connection credentials)
    # Generate a new key with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    # IMPORTANT: Change this in production! Store in .env file as ENCRYPTION_KEY
    ENCRYPTION_KEY: str = "-zvS8bDaaYPj2qyeuZxkKYKq6npYXC5GuBwnWUJsyck="
    
    # CORS - can be comma-separated string or list
    CORS_ORIGINS: Union[str, List[str]] = "http://localhost:3000"
    
    @property
    def cors_origins_list(self) -> List[str]:
        """Convert CORS_ORIGINS to list format"""
        if isinstance(self.CORS_ORIGINS, list):
            return self.CORS_ORIGINS
        elif isinstance(self.CORS_ORIGINS, str):
            # Split by comma and strip whitespace
            return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]
        return ["http://localhost:3000"]
    
    class Config:
        env_file = ".env"

settings = Settings()
