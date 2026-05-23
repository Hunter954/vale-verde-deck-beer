import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-change-me")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///vale_verde_dev.db")
    if SQLALCHEMY_DATABASE_URI.startswith("postgres://"):
        SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI.replace("postgres://", "postgresql://", 1)

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = os.getenv("RAILWAY_VOLUME_MOUNT_PATH", os.getenv("UPLOAD_FOLDER", "uploads"))
    MAX_CONTENT_LENGTH = 8 * 1024 * 1024

    Path(UPLOAD_FOLDER).mkdir(parents=True, exist_ok=True)
