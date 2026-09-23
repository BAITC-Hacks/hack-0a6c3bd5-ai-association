"""H2: cookie-сессия, консультант и отдельное подтверждение предложения."""

import re

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse

from app.api.guards import COOKIE, ConfirmationRoute, check_origin, get_store, session_token
from app.chat_models import Cart, ChatRequest, ChatResponse, ConfirmRequest, ConfirmResponse, SessionRequest
from app.db import product_from_row, require_warehouse

CONFIRMATIONS = {"да добавь", "да добавляй", "подтверждаю добавление", "подтверждаю удаление", "да удали", "подтверждаю"}


router = APIRouter(prefix="/api", route_class=ConfirmationRoute, dependencies=[Depends(check_origin)])


@router.post("/session")
def create_session(body: SessionRequest, request: Request, response: Response):
    token = get_store(request).create_session(request.cookies.get(COOKIE))
    response.set_cookie(COOKIE, token, httponly=True, samesite="lax", secure=request.url.scheme == "https", path="/")
    return {"ready": True}


@router.get("/cart", response_model=Cart)
def cart(request: Request):
    return get_store(request).cart(session_token(request))


@router.post("/proposals/{proposal_id}/confirm", response_model=ConfirmResponse)
def confirm(proposal_id: str, body: ConfirmRequest, request: Request):
    store, token = get_store(request), session_token(request)

    def work(db, session):
        result = store.confirm_in(db, session, proposal_id)
        return ConfirmResponse.model_validate(result).model_dump(mode="json")

    status, result = store.execute(token, "confirm", str(body.request_id), {"proposal_id": proposal_id, **body.model_dump(mode="json")}, work)
    return JSONResponse(status_code=status, content=result)


@router.post("/chat", response_model=ChatResponse)
def chat(body: ChatRequest, request: Request):
    from app.agent.consultant import consult

    store, token = get_store(request), session_token(request)

    def work(db, session):
        require_warehouse(db, body.warehouse_id)
        store.record_message_in(db, session, "user", body.message)
        current = store.cart_in(db, session)
        phrase = re.sub(r"[.,!?;:]+", " ", body.message.casefold())
        phrase = " ".join(phrase.split())
        if phrase in CONFIRMATIONS:
            active = store.last_proposal_in(db, session)
            quantities = {item["product_id"]: item["quantity"] for item in current["items"]}
            deltas = [item["target_quantity"] - quantities.get(item["product_id"], 0) for item in active["items"]] if active else []
            says_add = phrase in {"да добавь", "да добавляй", "подтверждаю добавление"}
            says_remove = phrase in {"да удали", "подтверждаю удаление"}
            intent_mismatch = (says_add and any(delta < 0 for delta in deltas)) or (says_remove and any(delta > 0 for delta in deltas))
            if active is not None and active["warehouse_id"] == body.warehouse_id and not intent_mismatch:
                confirmed = store.confirm_in(db, session, active["id"])
                text = "Подтверждение принято. Локальная корзина обновлена; заказ в ekt.kz не оформлен."
                result = {"message": text, "products": [], "checks": [], "proposal": None, "cart": confirmed["cart"], "answer_source": "rules", "confirmation_required": False}
            else:
                store.invalidate_proposal_in(db, session)
                result = {"message": "Подтверждение не соответствует показанному предложению для этого склада. Уточните действие, товар и количество, чтобы получить новое предложение.", "products": [], "checks": [], "proposal": None, "cart": current, "answer_source": "rules", "confirmation_required": False}
            store.mark_presented_in(db, session, None)
        else:
            # Новый запрос исключает подтверждение устаревшего контекста словом «да».
            store.invalidate_proposal_in(db, session)
            rows = db.execute("SELECT p.payload,s.quantity FROM products p LEFT JOIN stock s ON s.product_id=p.id AND s.warehouse_id=? ORDER BY p.sku,p.id", (body.warehouse_id,)).fetchall()
            products = [product_from_row(row, body.warehouse_id) for row in rows]
            answer = consult(body.message, products, current, request.app.state.settings.demo_mode)
            items = answer.pop("items", None)
            proposal = store.create_proposal(db, session, body.warehouse_id, items) if items else None
            result = {**answer, "proposal": proposal, "cart": store.cart_in(db, session), "confirmation_required": proposal is not None}
            store.mark_presented_in(db, session, proposal["id"] if proposal else None)
        validated = ChatResponse.model_validate(result).model_dump(mode="json")
        store.record_message_in(db, session, "assistant", validated["message"])
        return validated

    status, result = store.execute(token, "chat", str(body.request_id), body.model_dump(mode="json"), work)
    return JSONResponse(status_code=status, content=result)
