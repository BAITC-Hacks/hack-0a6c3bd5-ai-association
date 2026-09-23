"""Локальные пути и настройки; секреты не входят в ответы API."""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Settings:
    database_path: Path
    data_dir: Path
    web_dir: Path
    demo_mode: bool = True

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
        )
