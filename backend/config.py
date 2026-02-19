"""Configuration management for VibeCheck backend.

Loads environment variables from .env file and provides application settings.
"""
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Settings:
    """Application settings loaded from environment variables."""

    def __init__(self):
        self.DATABASE_URL = os.getenv(
            "DATABASE_URL",
            "postgresql+asyncpg://vibecheck:password@postgres:5432/vibecheck"
        )
        self.ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
        self.SQL_ECHO = os.getenv("SQL_ECHO", "false").lower() == "true"


# Export settings instance for import by other modules
settings = Settings()
