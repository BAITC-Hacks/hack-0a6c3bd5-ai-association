"""Сквозные проверки H2: HTTP, сессии, предложения, повторные запросы."""

import json
import sqlite3
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.config import ROOT, Settings
from app.main import create_app
from app.seed import seed


@pytest.fixture
def settings(tmp_path):
    result = Settings(tmp_path / "h2.db", ROOT / "data", tmp_path / "web")
    seed(result.database_path, result.data_dir)
    return result


@pytest.fixture
def client(settings):
    with TestClient(create_app(settings), raise_server_exceptions=False) as api:
        assert api.post("/api/session", json={}).status_code == 200
        yield api


def chat(client, message, warehouse="astana", request_id=None):
    return client.post("/api/chat", json={"message": message, "warehouse_id": warehouse, "request_id": request_id or str(uuid4())})


def proposal(client, quantity=2, warehouse="astana"):
    response = chat(client, f"Установи количество {quantity} шт DEMO-160-AVAILABLE", warehouse)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["confirmation_required"] is True, result
    assert result["proposal"]["items"][0]["target_quantity"] == quantity
    return result["proposal"]


def confirm(client, value, request_id=None):
    return client.post(f"/api/proposals/{value['id']}/confirm", json={"request_id": request_id or str(uuid4())})


def test_session_cookie_and_preserved_cart(client):
    token = client.cookies.get("kontur_session")
    response = client.post("/api/session", json={})
    assert response.json() == {"ready": True}
    assert "httponly" in response.headers["set-cookie"].lower()
    assert "samesite=lax" in response.headers["set-cookie"].lower()
    assert client.cookies.get("kontur_session") == token
    p = proposal(client)
    assert client.get("/api/cart").json()["items"] == []
    assert confirm(client, p).status_code == 200
    client.post("/api/session", json={})
    assert client.get("/api/cart").json()["total_kzt"] == 122000


def test_session_required_and_isolation(client, settings):
    p = proposal(client)
    with TestClient(create_app(settings)) as stranger:
        assert stranger.get("/api/cart").status_code == 401
        assert chat(stranger, "привет").status_code == 401
        stranger.post("/api/session", json={})
        response = confirm(stranger, p)
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "PROPOSAL_NOT_FOUND"
        assert stranger.get("/api/cart").json()["items"] == []
    assert confirm(client, p).status_code == 200


@pytest.mark.parametrize("origin", ["https://evil.example", "null", "http://testserver.evil.example", "http://testserver@evil.example"])
def test_origin_rejected(client, origin):
    response = client.post("/api/session", json={}, headers={"origin": origin})
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "ORIGIN_NOT_ALLOWED"


def test_dev_proxy_origin_allowed(client):
    assert client.post("/api/session", json={}, headers={"origin": "http://127.0.0.1:5173"}).status_code == 200
    assert client.post("/api/session", json={}, headers={"sec-fetch-site": "cross-site"}).status_code == 403


def test_idempotent_chat_and_confirm(client):
    key = str(uuid4())
    first = chat(client, "Добавь 2 шт DEMO-160-AVAILABLE", request_id=key)
    again = chat(client, "Добавь 2 шт DEMO-160-AVAILABLE", request_id=key)
    assert first.status_code == 200 and again.json() == first.json()
    assert chat(client, "Добавь 3 шт DEMO-160-AVAILABLE", request_id=key).status_code == 409
    p = first.json()["proposal"]
    confirm_key = str(uuid4())
    success = confirm(client, p, confirm_key)
    assert success.status_code == 200, success.text
    assert confirm(client, p, confirm_key).json() == success.json()
    assert confirm(client, p).json()["cart"] == success.json()["cart"]
    assert client.get("/api/cart").json()["items"][0]["quantity"] == 2
    assert client.get("/api/cart").json()["version"] == 1


def test_changed_price_requires_new_confirmation(client, settings):
    p = proposal(client)
    with sqlite3.connect(settings.database_path) as db:
        value = json.loads(db.execute("SELECT payload FROM products WHERE id=900000160").fetchone()[0])
        value["price_kzt"] = 62000
        db.execute("UPDATE products SET payload=? WHERE id=900000160", (json.dumps(value),))
    failed = confirm(client, p)
    assert failed.status_code == 409
    assert failed.json()["error"]["code"] == "PROPOSAL_CHANGED"
    replacement = failed.json()["error"]["details"]["proposal"]
    assert replacement["items"][0]["unit_price_kzt"] == 62000
    assert client.get("/api/cart").json()["items"] == []
    assert confirm(client, replacement).json()["cart"]["total_kzt"] == 124000


def test_stock_changed_blocks_confirmation(client, settings):
    p = proposal(client)
    with sqlite3.connect(settings.database_path) as db:
        db.execute("UPDATE stock SET quantity=1 WHERE product_id=900000160 AND warehouse_id='astana'")
    result = confirm(client, p)
    assert result.status_code == 409
    assert result.json()["error"]["details"]["proposal"] is None
    assert client.get("/api/cart").json()["items"] == []


def test_text_confirmation_and_stale_context(client):
    proposal(client)
    response = chat(client, "да, добавь")
    assert response.status_code == 200, response.text
    assert response.json()["cart"]["items"][0]["quantity"] == 2
    proposal(client, 3)
    chat(client, "Какие условия доставки?")
    assert chat(client, "да, добавь").json()["confirmation_required"] is False
    assert client.get("/api/cart").json()["items"][0]["quantity"] == 2


def test_text_confirmation_cannot_hide_new_quantity(client):
    proposal(client)
    chat(client, "да, добавь 100")
    assert client.get("/api/cart").json()["items"] == []


def test_cross_warehouse_cart_change_rejected(client):
    assert confirm(client, proposal(client)).status_code == 200
    result = chat(client, "Добавь 2 шт DEMO-160-AVAILABLE", warehouse="almaty")
    assert result.status_code == 409
    assert result.json()["error"]["code"] == "CART_WAREHOUSE_CONFLICT"


def test_conflicts_unknowns_and_quantity_guard(client):
    for message in ["Добавь 2 шт 200300285_", "Добавь 2 шт 000-DEMO-UNKNOWN", "Добавь 100 шт DEMO-160-AVAILABLE"]:
        response = chat(client, message)
        assert response.status_code == 200, response.text
        assert response.json()["proposal"] is None
        assert response.json()["cart"]["items"] == []


def test_delete_is_also_explicit_and_absolute(client):
    assert confirm(client, proposal(client, 2)).status_code == 200
    assert confirm(client, proposal(client, 3)).json()["cart"]["items"][0]["quantity"] == 3
    delete = chat(client, "Удали DEMO-160-AVAILABLE из корзины").json()["proposal"]
    assert delete["items"][0]["target_quantity"] == 0
    assert client.get("/api/cart").json()["items"][0]["quantity"] == 3
    assert confirm(client, delete).json()["cart"]["items"] == []


def test_chat_validation_and_safe_errors(client):
    for body in [{}, {"message": "  ", "warehouse_id": "astana", "request_id": str(uuid4())}, {"message": "ok", "warehouse_id": "astana", "request_id": "not-a-uuid"}]:
        response = client.post("/api/chat", json=body)
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert chat(client, "привет", warehouse="unknown").status_code == 404


def test_confirmation_verb_must_match_proposal(client):
    proposal(client)
    response = chat(client, "подтверждаю удаление")
    assert response.status_code == 200
    assert client.get("/api/cart").json()["items"] == []
    assert confirm(client, proposal(client)).status_code == 200
    chat(client, "Удали DEMO-160-AVAILABLE из корзины")
    chat(client, "да добавь")
    assert client.get("/api/cart").json()["items"][0]["quantity"] == 2


def test_replayed_old_chat_cannot_confirm_new_proposal(client):
    old_key = str(uuid4())
    first = chat(client, "Установи количество 2 шт DEMO-160-AVAILABLE", request_id=old_key)
    newer = proposal(client, 5)
    replay = chat(client, "Установи количество 2 шт DEMO-160-AVAILABLE", request_id=old_key)
    assert replay.json() == first.json()
    chat(client, "да добавь")
    assert client.get("/api/cart").json()["items"] == []


@pytest.mark.parametrize("message", ["Есть DEMO-160-EMPTY?", "Добавь 2 шт DEMO-160-EMPTY"])
def test_zero_stock_analog_keeps_cart_unchanged_without_confirmation(client, message):
    response = chat(client, message)
    assert response.status_code == 200, response.text
    result = response.json()
    assert [p["sku"] for p in result["products"]] == ["DEMO-160-EMPTY", "DEMO-160-AVAILABLE"]
    assert result["proposal"] is None
    assert result["confirmation_required"] is False
    assert result["cart"]["items"] == []
    assert chat(client, "да добавь").json()["cart"]["items"] == []
    assert client.get("/api/cart").json()["items"] == []


def test_auto_analog_uses_only_selected_warehouse(client):
    result = chat(client, "Есть DEMO-160-EMPTY?", warehouse="shymkent").json()
    assert [p["sku"] for p in result["products"]] == ["DEMO-160-EMPTY"]
    assert "не найдено" in result["message"]
    assert result["proposal"] is None
    assert client.get("/api/cart").json()["items"] == []
