import os
from pathlib import Path
from dotenv import load_dotenv

# Path to the backend directory
BACKEND_DIR = Path(__file__).resolve().parent.parent.parent

# Load environment variables from .env file
load_dotenv(BACKEND_DIR / ".env")

class Settings:
    PROJECT_NAME: str = "Legal Metrology Compliance Checker"
    VERSION: str = "0.1.0"
    API_V1_STR: str = "/api"
    
    # Secret keys and API keys (will be populated from .env)
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    
    # Uploads directory
    UPLOAD_DIR: Path = BACKEND_DIR / "uploads"

settings = Settings()
