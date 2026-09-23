"""Локальные пути и настройки; секреты не входят в ответы API."""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import dotenv_values, load_dotenv

ROOT = Path(__file__).resolve().parent.parent


def configure_serve_mode(mode: str | None) -> None:
    """Явный режим CLI действует только в запускаемом процессе."""
    if mode is None:
        return
    if mode == "demo":
        os.environ["DEMO_MODE"] = "1"
        return
    if mode != "live":
        raise ValueError("Режим запуска должен быть demo или live.")

    # Для явного live локальные доступы важнее устаревшего окружения терминала.
    values = dotenv_values(ROOT / ".env", encoding="utf-8-sig", interpolate=False)
    access = {
        name: (values.get(name, os.getenv(name, "")) or "").strip()
        for name in ("OPENAI_API_KEY", "OPENAI_MODEL")
    }
    if not all(access.values()):
        raise ValueError("Для live укажите OPENAI_API_KEY и OPENAI_MODEL в локальном .env или окружении запуска.")
    os.environ.update(access)
    os.environ["OPENAI_BASE_URL"] = "https://api.openai.com/v1"
    os.environ["DEMO_MODE"] = "0"


@dataclass(frozen=True)
class Settings:
    database_path: Path
    data_dir: Path
    web_dir: Path
    demo_mode: bool = True
    allowed_origins: tuple[str, ...] = ("http://127.0.0.1:5173", "http://localhost:5173")

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv(ROOT / ".env", override=False)
        mode = os.getenv("DEMO_MODE", "1")
        if mode not in {"0", "1"}:
            raise ValueError("DEMO_MODE должен быть 0 или 1.")
        return cls(
            database_path=Path(os.getenv("DATABASE_PATH", str(ROOT / "data/app.db"))),
            data_dir=ROOT / "data",
            web_dir=ROOT / "web/dist",
            demo_mode=mode == "1",
            allowed_origins=tuple(value.strip() for value in os.getenv("ALLOWED_ORIGINS", "http://127.0.0.1:5173,http://localhost:5173").split(",") if value.strip()),
        )
