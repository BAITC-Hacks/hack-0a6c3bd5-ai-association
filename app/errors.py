"""Единый формат ошибок, включая ошибки FastAPI и SQLite."""

import logging
import sqlite3

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

logger = logging.getLogger(__name__)


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str, details: dict | None = None):
        self.status, self.code, self.message = status, code, message
        self.details = details or {}


def error_response(status: int, code: str, message: str, details: dict | None = None):
    return JSONResponse(status_code=status, content={
        "error": {"code": code, "message": message, "details": details or {}}
    })


def register_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def api_error(_request: Request, exc: ApiError):
        return error_response(exc.status, exc.code, exc.message, exc.details)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_request: Request, exc: RequestValidationError):
        messages = {
            "missing": "Обязательное поле.",
            "int_parsing": "Укажите целое число.",
            "int_from_float": "Укажите целое число.",
            "greater_than": "Значение должно быть больше нуля.",
            "greater_than_equal": "Значение меньше допустимого.",
            "less_than_equal": "Значение больше допустимого.",
            "string_too_long": "Строка превышает допустимую длину.",
        }
        fields = [{
            "field": ".".join(str(part) for part in error["loc"][1:]),
            "message": messages.get(error["type"], "Некорректное значение поля."),
        } for error in exc.errors()]
        return error_response(422, "VALIDATION_ERROR", "Проверьте параметры запроса.", {"fields": fields})

    @app.exception_handler(sqlite3.Error)
    async def database_error(_request: Request, _exc: sqlite3.Error):
        logger.exception("Ошибка доступа к SQLite")
        return error_response(503, "DATABASE_UNAVAILABLE", "База данных недоступна. Выполните hack seed или повторите запрос позже.")

    @app.exception_handler(HTTPException)
    async def http_error(_request: Request, exc: HTTPException):
        code = "NOT_FOUND" if exc.status_code == 404 else "METHOD_NOT_ALLOWED" if exc.status_code == 405 else "HTTP_ERROR"
        return error_response(exc.status_code, code, "Ресурс не найден." if exc.status_code == 404 else "Запрос не поддерживается.")

    @app.exception_handler(Exception)
    async def unexpected_error(_request: Request, _exc: Exception):
        logger.exception("Непредвиденная ошибка сервера")
        return error_response(500, "INTERNAL_ERROR", "Не удалось обработать запрос. Повторите попытку позже.")
