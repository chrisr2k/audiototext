"""
Application configuration.

Reads settings from environment variables (with .env file fallback).
Supports both SQLite (development) and PostgreSQL (production).
"""

import os
import tempfile
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


class Settings:
    # OCI Configuration
    OCI_USER_OCID: str = os.getenv("OCI_USER_OCID", "")
    OCI_TENANCY_OCID: str = os.getenv("OCI_TENANCY_OCID", "")
    OCI_FINGERPRINT: str = os.getenv("OCI_FINGERPRINT", "")
    OCI_PRIVATE_KEY_PATH: str = os.getenv("OCI_PRIVATE_KEY_PATH", "")
    OCI_REGION: str = os.getenv("OCI_REGION", "us-ashburn-1")
    OCI_NAMESPACE: str = os.getenv("OCI_NAMESPACE", "")
    OCI_BUCKET: str = os.getenv("OCI_BUCKET", "")

    # Support passing the private key as an environment variable (for Docker)
    # If OCI_PRIVATE_KEY is set, write it to a temp file and use that path
    _OCI_PRIVATE_KEY: str = os.getenv("OCI_PRIVATE_KEY", "")

    # App Configuration
    SECRET_KEY: str = os.getenv("SECRET_KEY", "super-secret-key-change-in-production")
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./audiototext.db")
    DEMO_MODE: bool = os.getenv("DEMO_MODE", "true").lower() == "true"

    # Upload settings
    UPLOAD_DIR: str = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "uploads"
    )
    MAX_UPLOAD_SIZE: int = 500 * 1024 * 1024  # 500 MB
    ALLOWED_EXTENSIONS: set = {
        ".mp3", ".wav", ".m4a", ".flac", ".ogg",
        ".aac", ".webm", ".amr", ".opus",
        # Video formats (audio track will be extracted by OCI)
        ".mp4", ".mov", ".avi", ".mkv", ".wmv",
        ".flv", ".mpeg", ".mpg", ".3gp",
    }

    # Supported languages for OCI Speech
    SUPPORTED_LANGUAGES: dict = {
        "en-US": "English (US)",
        "es-ES": "Spanish",
        "fr-FR": "French",
        "de-DE": "German",
        "it-IT": "Italian",
        "pt-BR": "Portuguese (Brazil)",
        "ja-JP": "Japanese",
        "ko-KR": "Korean",
        "zh-CN": "Chinese (Simplified)",
        "ar-SA": "Arabic",
        "hi-IN": "Hindi",
        "nl-NL": "Dutch",
        "ru-RU": "Russian",
    }

    def __init__(self):
        # If OCI_PRIVATE_KEY is provided as env var (for Docker), write to temp file
        if self._OCI_PRIVATE_KEY and not self.OCI_PRIVATE_KEY_PATH:
            # Write the key to a temporary file
            tmp_dir = Path(tempfile.gettempdir()) / "oci_keys"
            tmp_dir.mkdir(parents=True, exist_ok=True)
            key_file = tmp_dir / "oci_api_key.pem"
            key_file.write_text(self._OCI_PRIVATE_KEY)
            key_file.chmod(0o600)
            self.OCI_PRIVATE_KEY_PATH = str(key_file)
            print(f"OCI private key written to {key_file}")


settings = Settings()
