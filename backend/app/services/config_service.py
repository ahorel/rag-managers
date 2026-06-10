import json
from pathlib import Path
from app.models import AppConfig

_FILE = Path(__file__).parent.parent.parent / "data" / "app_config.json"


def get_app_config() -> AppConfig:
    if _FILE.exists():
        with open(_FILE, encoding="utf-8") as f:
            return AppConfig(**json.load(f))
    return AppConfig()


def save_app_config(config: AppConfig) -> None:
    _FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(_FILE, "w", encoding="utf-8") as f:
        json.dump(config.model_dump(), f, ensure_ascii=False, indent=2)
