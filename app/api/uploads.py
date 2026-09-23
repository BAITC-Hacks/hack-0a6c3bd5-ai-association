"""H3: ограниченная загрузка и предложение по проверенным человеком строкам."""

import hashlib
import json
import secrets
import sqlite3
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile
from starlette.formparsers import MultiPartException, MultiPartParser

from app.api.chat import check_origin, get_store, session_token
from app.chat_models import ChatResponse
from app.commerce import canonical
from app.db import product_from_row, require_warehouse
from app.errors import ApiError
from app.upload_models import Extraction, UploadProposalRequest, UploadResponse

MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_MULTIPART_BYTES = MAX_FILE_BYTES + 64 * 1024
class UploadRoute(APIRoute):
    """Неудачный новый запрос файла снимает разрешение на краткое «да»."""

    def get_route_handler(self):
        handler = super().get_route_handler()

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
            except (ApiError, RequestValidationError):
                await clear_confirmation()
                raise
            if response.status_code >= 400:
                await clear_confirmation()
            return response

        return guarded


router = APIRouter(prefix="/api", route_class=UploadRoute, dependencies=[Depends(check_origin)])


def invalid_form():
    return ApiError(422, "VALIDATION_ERROR", "Передайте один файл, UUID request_id и warehouse_id.")


async def upload_form(request: Request) -> tuple[str, bytes, str, str]:
    if request.headers.get("content-type", "").split(";", 1)[0].strip().lower() != "multipart/form-data":
        raise ApiError(415, "UNSUPPORTED_FILE_TYPE", "Передайте файл через multipart/form-data.")
    declared = request.headers.get("content-length")
    if declared is not None:
        if not declared.isdigit():
            raise invalid_form()
        if int(declared) > MAX_MULTIPART_BYTES:
            raise ApiError(413, "FILE_TOO_LARGE", "Размер файла не должен превышать 10 MiB.")
    # Ограничиваем реальный поток до разбора multipart, включая запрос без Content-Length.
    chunks, size = [], 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > MAX_MULTIPART_BYTES:
            raise ApiError(413, "FILE_TOO_LARGE", "Размер файла не должен превышать 10 MiB.")
        chunks.append(chunk)

    async def stream():
        for chunk in chunks:
            yield chunk

    try:
        form = await MultiPartParser(request.headers, stream(), max_files=1, max_fields=2, max_part_size=4096).parse()
    except (MultiPartException, ValueError):
        raise invalid_form() from None
    try:
        if len(form.multi_items()) != 3 or set(form) != {"file", "request_id", "warehouse_id"}:
            raise invalid_form()
        file, key, warehouse = form["file"], form["request_id"], form["warehouse_id"]
        if not isinstance(file, UploadFile) or not isinstance(key, str) or not isinstance(warehouse, str) or not warehouse.strip():
            raise invalid_form()
        if not file.filename or len(file.filename) > 255:
            raise invalid_form()
        try:
            key = str(UUID(key))
        except ValueError:
            raise invalid_form() from None
        content = await file.read(MAX_FILE_BYTES + 1)
        if len(content) > MAX_FILE_BYTES:
            raise ApiError(413, "FILE_TOO_LARGE", "Размер файла не должен превышать 10 MiB.")
        return file.filename, content, key, warehouse
    finally:
        await form.close()


@router.post("/uploads", response_model=UploadResponse)
async def upload(request: Request):
    store, token = get_store(request), session_token(request)
    # Не принимаем тело документа от клиента без действующей сессии.
    await run_in_threadpool(store.cart, token)
    filename, content, key, warehouse = await upload_form(request)
    digest = hashlib.sha256(content).hexdigest()

    def work(db, session):
        from app.documents import parse_document

        require_warehouse(db, warehouse)
        store.invalidate_proposal_in(db, session)
        try:
            extracted = Extraction.model_validate(parse_document(filename, content, request.app.state.settings.demo_mode))
        except ValidationError:
            raise ApiError(422, "DOCUMENT_PARSE_FAILED", "Не удалось надёжно извлечь строки. Проверьте документ или вставьте текст.") from None
        result = UploadResponse(upload_id="u_" + secrets.token_urlsafe(18), **extracted.model_dump()).model_dump(mode="json")
        # Исходник хранится только в локальной БД, не публикуется как статический файл.
        db.execute("INSERT INTO uploads(id,session_token,content_hash,content,payload) VALUES (?,?,?,?,?)",
                   (result["upload_id"], session, digest, content, canonical(result)))
        return result

    status, result = await run_in_threadpool(store.execute, token, "upload", key,
                                           {"filename": filename, "sha256": digest, "warehouse_id": warehouse}, work)
    return JSONResponse(status_code=status, content=result)


@router.post("/uploads/{upload_id}/proposal", response_model=ChatResponse)
def upload_proposal(upload_id: str, body: UploadProposalRequest, request: Request):
    from app.agent.uploads import match_upload_lines

    store, token = get_store(request), session_token(request)

    def work(db, session):
        saved = db.execute("SELECT payload FROM uploads WHERE id=? AND session_token=?", (upload_id, session)).fetchone()
        if saved is None:
            raise ApiError(404, "UPLOAD_NOT_FOUND", "Загруженный документ не найден.")
        require_warehouse(db, body.warehouse_id)
        original_ids = {line["line_id"] for line in json.loads(saved["payload"])["lines"]}
        if any(line.line_id not in original_ids for line in body.lines):
            raise ApiError(422, "VALIDATION_ERROR", "В исправленном списке есть строка, которой не было в документе.")
        store.invalidate_proposal_in(db, session)
        current = store.cart_in(db, session)
        rows = db.execute("SELECT p.payload,s.quantity FROM products p LEFT JOIN stock s ON s.product_id=p.id AND s.warehouse_id=? ORDER BY p.sku,p.id", (body.warehouse_id,)).fetchall()
        products = [product_from_row(row, body.warehouse_id) for row in rows]
        answer = match_upload_lines([line.model_dump() for line in body.lines], products, current)
        items = answer.pop("items", None)
        proposal = store.create_proposal(db, session, body.warehouse_id, items) if items else None
        store.mark_presented_in(db, session, proposal["id"] if proposal else None)
        result = ChatResponse.model_validate({**answer, "proposal": proposal, "confirmation_required": proposal is not None, "cart": current}).model_dump(mode="json")
        store.record_message_in(db, session, "assistant", result["message"])
        return result

    status, result = store.execute(token, "upload_proposal", str(body.request_id), {"upload_id": upload_id, **body.model_dump(mode="json")}, work)
    return JSONResponse(status_code=status, content=result)
