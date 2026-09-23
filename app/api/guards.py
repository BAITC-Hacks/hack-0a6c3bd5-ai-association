"""Общие проверки сессии, Origin и контекста явного подтверждения."""

import json
import sqlite3
from urllib.parse import urlsplit

from fastapi import Request
from fastapi.routing import APIRoute
from starlette.concurrency import run_in_threadpool

from app.commerce import Store, ensure_schema
from app.errors import ApiError

COOKIE = "kontur_session"


def origin_tuple(value: str):
    try:
        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password or parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
            return None
        return parsed.scheme, parsed.hostname.lower(), parsed.port or (443 if parsed.scheme == "https" else 80)
    except ValueError:
        return None


def check_origin(request: Request) -> None:
    if request.method not in {"POST", "PUT", "PATCH", "DELETE"}:
        return
    supplied = request.headers.get("origin")
    # curl/локальные клиенты могут не отправлять Origin; браузерный cross-site запрещён.
    if supplied is None:
        if request.headers.get("sec-fetch-site") == "cross-site":
            raise ApiError(403, "ORIGIN_NOT_ALLOWED", "Источник запроса не разрешён.")
        return
    allowed = {origin_tuple(str(request.base_url))}
    allowed.update(origin_tuple(value) for value in request.app.state.settings.allowed_origins)
    supplied_tuple = origin_tuple(supplied)
    if supplied_tuple is None or supplied_tuple not in allowed:
        raise ApiError(403, "ORIGIN_NOT_ALLOWED", "Источник запроса не разрешён.")



def get_store(request: Request) -> Store:
    if not getattr(request.app.state, "commerce_ready", False):
        ensure_schema(request.app.state.settings.database_path)
        request.app.state.commerce_ready = True
    return Store(request.app.state.settings.database_path)


def session_token(request: Request) -> str:
    token = request.cookies.get(COOKIE)
    if not token:
        raise ApiError(401, "SESSION_REQUIRED", "Сначала создайте сессию.")
    return token



class ConfirmationRoute(APIRoute):
    """Ошибка нового действия снимает разрешение на короткое «да»."""

    def get_route_handler(self):
        handler = super().get_route_handler()
        if "POST" not in self.methods:
            return handler

        async def guarded(request: Request):
            async def clear_confirmation():
                try:
                    # Чужой Origin не вправе менять даже контекст подтверждения.
                    check_origin(request)
                    await run_in_threadpool(get_store(request).clear_presented, session_token(request))
                except (ApiError, sqlite3.Error):
                    pass  # Сохраняем исходную ошибку при отсутствии сессии/БД.

            try:
                response = await handler(request)
            except Exception as exc:
                replacement = isinstance(exc, ApiError) and exc.code == "PROPOSAL_CHANGED" and exc.details.get("proposal")
                if not replacement:
                    await clear_confirmation()
                raise
            if response.status_code >= 400:
                try:
                    error = json.loads(response.body).get("error", {})
                    replacement = error.get("code") == "PROPOSAL_CHANGED" and error.get("details", {}).get("proposal")
                except (ValueError, AttributeError, TypeError):
                    replacement = None
                # Показанное новое предложение после изменения цены требует нового «да».
                if not replacement:
                    await clear_confirmation()
            return response

        return guarded
