"""API работает самостоятельно; сборка UI подключается при наличии."""

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.catalog import router
from app.config import Settings
from app.errors import ApiError, register_handlers


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    # Swagger/ReDoc по умолчанию требуют CDN; контракт доступен как JSON.
    application = FastAPI(title="Контур", version="0.1.0", docs_url=None, redoc_url=None)
    application.state.settings = settings
    register_handlers(application)
    application.include_router(router)

    assets = settings.data_dir / "assets"
    if assets.is_dir():
        application.mount("/assets/catalog", StaticFiles(directory=assets), name="catalog-assets")
    web_assets = settings.web_dir / "assets"
    if web_assets.is_dir():
        application.mount("/assets", StaticFiles(directory=web_assets), name="web-assets")

    @application.get("/", include_in_schema=False)
    @application.get("/cart", include_in_schema=False)
    def frontend():
        index = settings.web_dir / "index.html"
        if index.is_file():
            return FileResponse(index)
        raise ApiError(404, "FRONTEND_NOT_BUILT", "Сборка интерфейса ещё не подготовлена. API доступен по /api.")

    @application.get("/{path:path}", include_in_schema=False)
    def static_file(path: str):
        candidate = (settings.web_dir / path).resolve()
        root = settings.web_dir.resolve()
        if not path.startswith(("api/", "assets/")) and candidate.is_relative_to(root) and candidate.is_file():
            return FileResponse(candidate)
        raise ApiError(404, "NOT_FOUND", "Ресурс не найден.")

    return application


app = create_app()
