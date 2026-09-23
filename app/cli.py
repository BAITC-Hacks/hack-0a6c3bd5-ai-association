"""Команды: uv run hack seed; uv run hack serve."""

import argparse
import json
import sqlite3
from pathlib import Path

from app.config import Settings, configure_serve_mode
from app.seed import seed


def main() -> None:
    parser = argparse.ArgumentParser(prog="hack", description="Локальный каталог Контур")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("seed", help="Загрузить локальный CSV-снимок в SQLite")
    serve = commands.add_parser("serve", help="Запустить API и готовую сборку интерфейса")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    serve.add_argument("--mode", choices=["demo", "live"], help="Явно включить автономное демо или OpenAI с приоритетом ключа и модели из .env")
    fetch = commands.add_parser("snapshot", help="Явно получить снимок карточек из API ekt.kz")
    fetch.add_argument("--ids", nargs="+", type=int, required=True)
    fetch.add_argument("--output", required=True, help="Новый файл JSON вне Git или в data/")
    normalize = commands.add_parser("import-snapshot", help="Преобразовать проверенный JSON-снимок в новую папку CSV")
    normalize.add_argument("--input", required=True)
    normalize.add_argument("--output-dir", required=True)
    normalize.add_argument("--unit", choices=["шт", "м"], required=True, help="Явная демонстрационная единица для выбранной однородной выборки")
    args = parser.parse_args()
    try:
        if args.command == "serve":
            configure_serve_mode(args.mode)
        settings = Settings.from_env()
        if args.command == "seed":
            print(json.dumps(seed(settings.database_path, settings.data_dir), ensure_ascii=False))
        elif args.command == "import-snapshot":
            from app.adapters.ekt import export_seed
            snapshot = json.loads(Path(args.input).read_text(encoding="utf-8"))
            export_seed(snapshot, Path(args.output_dir), args.unit)
            print("CSV сохранены в новой папке; проверьте их перед заменой основного набора.")
        elif args.command == "snapshot":
            from app.adapters.ekt import save_snapshot
            save_snapshot(args.ids, args.output)
            print("Снимок сохранён. Перед импортом проверьте единицы и происхождение полей.")
        else:
            # Первый запуск готов к демо; повреждённую существующую БД не заменяем.
            if not settings.database_path.exists():
                seed(settings.database_path, settings.data_dir)
            import uvicorn
            from app.main import create_app
            uvicorn.run(create_app(settings), host=args.host, port=args.port)
    except (ValueError, OSError, sqlite3.Error) as exc:
        # Ошибки адаптера очищены от доступов; в CLI не печатаем env.
        parser.exit(1, f"Ошибка: {exc}\n")


if __name__ == "__main__":
    main()
