"""Central settings + editable YAML config loading (scoring weights, compliance rules)."""
import os
from functools import lru_cache
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"


def _load_dotenv() -> None:
    """Tiny .env loader so the app runs without python-dotenv."""
    env_file = PROJECT_ROOT / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


_load_dotenv()


class Settings:
    database_url: str = os.environ.get("DATABASE_URL", f"sqlite:///{PROJECT_ROOT / 'wallart.db'}")
    anthropic_api_key: str | None = os.environ.get("ANTHROPIC_API_KEY")
    gemini_api_key: str | None = os.environ.get("GEMINI_API_KEY")
    gemini_image_model: str = os.environ.get("GEMINI_IMAGE_MODEL", "gemini-2.5-flash-image")
    etsy_api_key: str | None = os.environ.get("ETSY_API_KEY")
    etsy_shop_id: str | None = os.environ.get("ETSY_SHOP_ID")
    etsy_access_token: str | None = os.environ.get("ETSY_ACCESS_TOKEN")
    storage_dir: Path = Path(os.environ.get("STORAGE_DIR", PROJECT_ROOT / "storage"))

    @property
    def etsy_configured(self) -> bool:
        return bool(self.etsy_api_key and self.etsy_shop_id and self.etsy_access_token)


settings = Settings()


@lru_cache(maxsize=None)
def _load_yaml(name: str) -> dict:
    with open(CONFIG_DIR / name, encoding="utf-8") as f:
        return yaml.safe_load(f)


def scoring_config() -> dict:
    return _load_yaml("scoring.yaml")


def compliance_config() -> dict:
    return _load_yaml("compliance.yaml")


def reload_configs() -> None:
    _load_yaml.cache_clear()
