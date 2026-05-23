import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-change-me")

    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'vale_verde_dev.db'}")
    if SQLALCHEMY_DATABASE_URI.startswith("postgres://"):
        SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI.replace("postgres://", "postgresql://", 1)

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Uploads/fotos:
    # - Railway: usa o volume persistente injetado em RAILWAY_VOLUME_MOUNT_PATH.
    # - Local: usa ./uploads dentro do projeto.
    raw_upload_folder = os.getenv("RAILWAY_VOLUME_MOUNT_PATH") or os.getenv("UPLOAD_FOLDER") or "uploads"
    UPLOAD_FOLDER = str(Path(raw_upload_folder) if Path(raw_upload_folder).is_absolute() else BASE_DIR / raw_upload_folder)
    MAX_CONTENT_LENGTH = 8 * 1024 * 1024

    Path(UPLOAD_FOLDER).mkdir(parents=True, exist_ok=True)
