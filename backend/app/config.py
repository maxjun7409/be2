"""환경변수 설정. .env 파일 값을 읽어 settings 객체로 제공합니다."""
import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def _bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


class Settings:
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./matelier.db")
    public_base_url: str = os.getenv("PUBLIC_BASE_URL", "http://localhost:8000").rstrip("/")
    storage_dir: str = os.getenv("STORAGE_DIR", "./storage")
    max_upload_mb: int = int(os.getenv("MAX_UPLOAD_MB", "15"))
    max_image_side: int = int(os.getenv("MAX_IMAGE_SIDE", "2048"))
    ai_server_url: str = os.getenv("AI_SERVER_URL", "http://localhost:8001").rstrip("/")
    ai_timeout_seconds: float = float(os.getenv("AI_TIMEOUT_SECONDS", "60"))
    dev_auth: bool = _bool("DEV_AUTH", False)
    firebase_credentials: str = os.getenv("FIREBASE_CREDENTIALS", "")
    draft_ttl_hours: int = int(os.getenv("DRAFT_TTL_HOURS", "24"))


settings = Settings()
