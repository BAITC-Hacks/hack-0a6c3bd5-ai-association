"""H4: ошибочный запрос не подтверждает старое предложение коротким ответом."""

import json
import sqlite3
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.config import ROOT, Settings
from app.main import create_app
from app.seed import seed


@pytest.fixture
def api(tmp_path):
    settings = Settings(tmp_path / "h4.db", ROOT / "data", tmp_path / "web")
    seed(settings.database_path, settings.data_dir)
    with TestClient(create_app(settings), raise_server_exceptions=False) as client:
        assert client.post("/api/session", json={}).status_code == 200
        yield client, settings


def body(message, **changes):
    return {"message": message, "warehouse_id": "astana", "request_id": str(uuid4()), **changes}


def pending(client):
    payload = body("Установи количество 2 шт DEMO-160-AVAILABLE")
    response = client.post("/api/chat", json=payload)
    assert response.status_code == 200, response.text
    assert response.json()["confirmation_required"]
    return payload, response.json()["proposal"]


@pytest.mark.parametrize("failure", ["validation", "malformed", "warehouse", "idempotency", "confirm_id"])
def test_failed_request_clears_short_confirmation(api, failure):
    client, _ = api
    old_body, proposal = pending(client)
    if failure == "validation":
        response = client.post("/api/chat", json=body(" "))
    elif failure == "malformed":
        response = client.post("/api/chat", content="{", headers={"Content-Type": "application/json"})
    elif failure == "warehouse":
        response = client.post("/api/chat", json=body("Добавь 5 шт DEMO-160-AVAILABLE", warehouse_id="missing"))
    elif failure == "idempotency":
        response = client.post("/api/chat", json={**old_body, "message": "Добавь 5 шт DEMO-160-AVAILABLE"})
    else:
        response = client.post("/api/proposals/missing/confirm", json={"request_id": str(uuid4())})
    assert response.status_code >= 400
    confirmation = client.post("/api/chat", json=body("да добавь"))
    assert confirmation.status_code == 200, confirmation.text
    assert confirmation.json()["cart"]["items"] == []
    assert client.get("/api/cart").json()["version"] == 0
    # Явная кнопка привязана к ID: старое предложение по-прежнему можно выбрать.
    explicit = client.post(f"/api/proposals/{proposal['id']}/confirm", json={"request_id": str(uuid4())})
    assert explicit.status_code == 200, explicit.text


def test_unexpected_chat_failure_clears_short_confirmation(api, monkeypatch):
    client, _ = api
    pending(client)
    with monkeypatch.context() as patch:
        def unavailable(*args, **kwargs):
            raise RuntimeError("Ошибка обработки")
        patch.setattr("app.agent.consultant.consult", unavailable)
        response = client.post("/api/chat", json=body("Новый запрос"))
    assert response.status_code == 500
    assert client.post("/api/chat", json=body("да добавь")).json()["cart"]["items"] == []


def test_rejected_origin_does_not_clear_confirmation(api):
    client, _ = api
    pending(client)
    response = client.post("/api/chat", json=body("Новый запрос"), headers={"Origin": "https://foreign.example"})
    assert response.status_code == 403
    assert client.post("/api/chat", json=body("да добавь")).json()["cart"]["total_kzt"] == 122000


@pytest.mark.parametrize("text_confirmation", [False, True])
def test_new_price_proposal_can_be_confirmed_after_409(api, text_confirmation):
    client, settings = api
    _, proposal = pending(client)
    with sqlite3.connect(settings.database_path) as db:
        product = json.loads(db.execute("SELECT payload FROM products WHERE id=900000160").fetchone()[0])
        product["price_kzt"] = 62000
        db.execute("UPDATE products SET payload=? WHERE id=900000160", (json.dumps(product),))
    if text_confirmation:
        response = client.post("/api/chat", json=body("да добавь"))
    else:
        response = client.post(f"/api/proposals/{proposal['id']}/confirm", json={"request_id": str(uuid4())})
    assert response.status_code == 409
    assert response.json()["error"]["details"]["proposal"] is not None
    assert client.get("/api/cart").json()["items"] == []
    confirmed = client.post("/api/chat", json=body("да добавь"))
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["cart"]["total_kzt"] == 124000
