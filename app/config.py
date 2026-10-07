from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "Vending Machine IoT Lab")
    api_host: str = os.getenv("API_HOST", "0.0.0.0")
    api_port: int = int(os.getenv("API_PORT", "8000"))
    hmac_secret: str = os.getenv("HMAC_SECRET", "change-me-local-only")
    nonce_ttl_seconds: int = int(os.getenv("NONCE_TTL_SECONDS", "60"))
    storage_backend: str = os.getenv("STORAGE_BACKEND", "memory")
    sqlite_path: str = os.getenv("SQLITE_PATH", "./vending_lab.db")


settings = Settings()
