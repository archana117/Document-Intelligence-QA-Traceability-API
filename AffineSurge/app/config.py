import os
from typing import Optional

class Settings:
    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./sqlite_data.db")
    
    # Directories
    WORKSPACE_DIR: str = "c:/Users/vyshn/Downloads/AffineSurge"
    OUTPUT_DIR: str = os.path.join(WORKSPACE_DIR, "output")
    LOG_DIR: str = os.path.join(WORKSPACE_DIR, "logs")
    
    # Gemini API Key
    GEMINI_API_KEY: Optional[str] = os.getenv("GEMINI_API_KEY", None)

settings = Settings()

# Ensure directories exist
os.makedirs(settings.OUTPUT_DIR, exist_ok=True)
os.makedirs(settings.LOG_DIR, exist_ok=True)
