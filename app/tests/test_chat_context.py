"""H4: контекст товара помогает справке, но не заменяет выбор для корзины."""

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
    value = Settings(tmp_path / "context.db", ROOT / "data", tmp_path / "web")
    seed(value.database_path, value.data_dir)
    return value


@pytest.fixture
def client(settings):
    with TestClient(create_app(settings), raise_server_exceptions=False) as api:
        assert api.post("/api/session", json={}).status_code == 200
        yield api


def chat(client, message, warehouse="astana", key=None):
    response = client.post("/api/chat", json={
        "message": message, "warehouse_id": warehouse,
        "request_id": key or str(uuid4()),
    })
    assert response.status_code == 200, response.text
    return response.json()


def only_product(result, sku="DEMO-160-AVAILABLE", warehouse="astana"):
    assert [item["sku"] for item in result["products"]] == [sku], result
    product = result["products"][0]
    assert product["warehouse_id"] == warehouse, result
    return product


def upload(client, key=None):
    response = client.post("/api/uploads", files={
        "file": ("sample.xlsx", (ROOT / "fixtures/uploads/sample.xlsx").read_bytes()),
    }, data={"request_id": key or str(uuid4()), "warehouse_id": "astana"})
    assert response.status_code == 200, response.text
    return response.json()


def review(client, saved, lines=None, key=None):
    response = client.post(f"/api/uploads/{saved['upload_id']}/proposal", json={
        "request_id": key or str(uuid4()), "warehouse_id": "astana",
        "lines": saved["lines"] if lines is None else lines,
    })
    assert response.status_code == 200, response.text
    return response.json()


def test_information_followups_keep_selected_product_and_cart_unchanged(client):
    chat(client, "Проверь DEMO-160-AVAILABLE")
    before = client.get("/api/cart").json()
    for message in ["А сколько его есть?", "Какая минимальная партия?", "А цена?", "А сертификат есть?"]:
        result = chat(client, message)
        product = only_product(result)
        assert product["available_quantity"] == 12
        assert product["price_kzt"] == 61000
        assert product["min_order_quantity"] == 1
        assert result["proposal"] is None
        assert result["confirmation_required"] is False
    assert client.get("/api/cart").json() == before


def test_named_warehouse_is_remembered_for_information_only(client):
    pending = chat(client, "Добавь 2 шт DEMO-160-AVAILABLE")["proposal"]
    confirmed = client.post(f"/api/proposals/{pending['id']}/confirm", json={"request_id": str(uuid4())})
    assert confirmed.status_code == 200, confirmed.text
    before = client.get("/api/cart").json()
    chat(client, "Проверь DEMO-160-AVAILABLE")
    result = chat(client, "А сколько его в Алматы?")
    assert only_product(result, warehouse="almaty")["available_quantity"] == 6
    assert result["proposal"] is None
    assert only_product(chat(client, "Какая минимальная партия?"), warehouse="almaty")["min_order_quantity"] == 1
    assert client.get("/api/cart").json() == before
    assert before["warehouse_id"] == "astana"


def test_ui_warehouse_change_overrides_remembered_information_warehouse(client):
    chat(client, "Проверь DEMO-160-AVAILABLE")
    only_product(chat(client, "А сколько его в Алматы?"), warehouse="almaty")
    result = chat(client, "А сколько его есть?", warehouse="shymkent")
    assert only_product(result, warehouse="shymkent")["available_quantity"] == 0
    assert only_product(chat(client, "А цена?", warehouse="shymkent"), warehouse="shymkent")["price_kzt"] == 61000
    assert only_product(chat(client, "А сколько его есть?", warehouse="astana"))["available_quantity"] == 12
    assert client.get("/api/cart").json()["items"] == []


def test_explicit_new_product_replaces_previous_selection(client):
    chat(client, "Проверь DEMO-160-AVAILABLE")
    only_product(chat(client, "А цена 200300285_?"), sku="200300285_")
    product = only_product(chat(client, "Какая минимальная партия?"), sku="200300285_")
    assert product["price_kzt"] == 64920


@pytest.mark.parametrize("message", [
    "А цена NO-SUCH-123?", "А цена DEMO-160-AVAILABLE-X?", "А цена артикула 999999999?",
])
def test_explicit_unknown_product_never_falls_back_to_old_selection(client, message):
    chat(client, "Проверь DEMO-160-AVAILABLE")
    unknown = chat(client, message)
    assert unknown["products"] == [], unknown
    assert unknown["proposal"] is None
    assert chat(client, "Какая минимальная партия?")["products"] == []


@pytest.mark.parametrize("message", [
    "Сравни DEMO-160-AVAILABLE и 200300285_", "Есть DEMO-160-EMPTY?",
])
def test_multiple_products_or_analog_choice_clear_ambiguous_context(client, message):
    chat(client, "Проверь DEMO-160-AVAILABLE")
    assert len(chat(client, message)["products"]) > 1
    followup = chat(client, "А сколько его есть?")
    assert followup["products"] == [], followup
    assert followup["proposal"] is None


@pytest.mark.parametrize("message", [
    "Добавь его 2 шт", "Удали его", "Установи 2 шт", "Да, добавь 2 шт",
])
def test_pronouns_never_supply_product_for_cart_changes(client, message):
    chat(client, "Проверь DEMO-160-AVAILABLE")
    result = chat(client, message)
    assert result["proposal"] is None, result
    assert result["confirmation_required"] is False
    assert client.get("/api/cart").json()["items"] == []


def test_information_followup_does_not_authorize_old_short_confirmation(client):
    assert chat(client, "Добавь 2 шт DEMO-160-AVAILABLE")["proposal"] is not None
    info = chat(client, "Какая минимальная партия?")
    only_product(info)
    assert info["proposal"] is None
    confirmed = chat(client, "да добавь")
    assert confirmed["cart"]["items"] == []
    assert client.get("/api/cart").json()["version"] == 0


def test_replaying_old_chat_does_not_restore_old_selected_product(client):
    key = str(uuid4())
    first = chat(client, "Проверь DEMO-160-AVAILABLE", key=key)
    chat(client, "Проверь 200300285_")
    assert chat(client, "Проверь DEMO-160-AVAILABLE", key=key) == first
    only_product(chat(client, "Какая минимальная партия?"), sku="200300285_")


def test_selected_product_is_isolated_between_cookie_sessions(client, settings):
    key = str(uuid4())
    chat(client, "Проверь DEMO-160-AVAILABLE", key=key)
    with TestClient(create_app(settings)) as other:
        assert other.post("/api/session", json={}).status_code == 200
        assert chat(other, "Какая минимальная партия?")["products"] == []
        # Одинаковый UUID в другой сессии не возвращает чужой ответ.
        only_product(chat(other, "Проверь 200300285_", key=key), sku="200300285_")
        only_product(chat(other, "А цена?"), sku="200300285_")
    only_product(chat(client, "А цена?"))


def test_existing_session_keeps_context_after_application_restart(client, settings):
    chat(client, "Проверь DEMO-160-AVAILABLE")
    chat(client, "А сколько его в Алматы?")
    token = client.cookies.get("kontur_session")
    with TestClient(create_app(settings)) as restarted:
        restarted.cookies.set("kontur_session", token)
        assert restarted.post("/api/session", json={}).status_code == 200
        result = chat(restarted, "Какая минимальная партия?")
        only_product(result, warehouse="almaty")


def test_successful_upload_clears_old_chat_selection(client):
    chat(client, "Проверь DEMO-160-AVAILABLE")
    upload(client)
    followup = chat(client, "Какая минимальная партия?")
    assert followup["products"] == [], followup
    assert followup["proposal"] is None
    assert client.get("/api/cart").json()["items"] == []


def test_review_of_single_file_product_establishes_information_context(client):
    chat(client, "Проверь 200300285_")
    saved = upload(client)
    only_product(review(client, saved, lines=saved["lines"][:1]))
    result = chat(client, "Какая минимальная партия?")
    only_product(result)
    assert result["proposal"] is None
    assert client.get("/api/cart").json()["items"] == []


def test_review_of_multiple_file_products_keeps_context_ambiguous(client):
    saved = upload(client)
    chat(client, "Проверь DEMO-160-AVAILABLE")
    assert len(review(client, saved)["products"]) > 1
    result = chat(client, "А сколько его есть?")
    assert result["products"] == [], result
    assert result["proposal"] is None


@pytest.mark.parametrize("operation", ["upload", "review"])
def test_replaying_old_file_operation_does_not_replace_new_chat_context(client, operation):
    key = str(uuid4())
    saved = upload(client, key=key)
    if operation == "review":
        initial = review(client, saved, lines=saved["lines"][:1], key=key)
    chat(client, "Проверь 200300285_")
    if operation == "upload":
        assert upload(client, key=key) == saved
    else:
        assert review(client, saved, lines=saved["lines"][:1], key=key) == initial
    only_product(chat(client, "Какая минимальная партия?"), sku="200300285_")



def test_followup_reads_current_price_and_stock_from_sqlite(client, settings):
    chat(client, "Проверь DEMO-160-AVAILABLE")
    with sqlite3.connect(settings.database_path) as db:
        row = db.execute("SELECT payload FROM products WHERE id=900000160").fetchone()
        product = json.loads(row[0])
        product["price_kzt"] = 62000
        db.execute("UPDATE products SET payload=? WHERE id=900000160", (json.dumps(product),))
        db.execute("UPDATE stock SET quantity=9 WHERE product_id=900000160 AND warehouse_id='astana'")
    product = only_product(chat(client, "А цена?"))
    assert product["price_kzt"] == 62000
    assert product["available_quantity"] == 9
    assert client.get("/api/cart").json()["items"] == []


@pytest.mark.parametrize("message", [
    "Сколько его в Алматы и Астане?",
    "Сколько его не в Алматы?",
    "Сколько его в Караганде?",
    "Есть в наличии DEMO-160-AVAILABLE в Караганде?",
])
def test_ambiguous_negative_or_unknown_warehouse_does_not_guess(client, message):
    chat(client, "Проверь DEMO-160-AVAILABLE")
    result = chat(client, message)
    assert result["products"] == [], result
    assert result["proposal"] is None
    assert result["confirmation_required"] is False
    assert client.get("/api/cart").json()["items"] == []


def test_disappeared_selected_product_clears_context_without_server_error(client, settings):
    chat(client, "Проверь DEMO-160-AVAILABLE")
    with sqlite3.connect(settings.database_path) as db:
        db.execute("DELETE FROM stock WHERE product_id=900000160")
        db.execute("DELETE FROM products WHERE id=900000160")
    result = chat(client, "А цена?")
    assert result["products"] == [], result
    assert result["proposal"] is None
    assert chat(client, "Какая минимальная партия?")["products"] == []


def test_question_about_another_product_does_not_reuse_previous_selection(client):
    chat(client, "Проверь DEMO-160-AVAILABLE")
    result = chat(client, "А цена другого автомата?")
    assert result["products"] == [], result
    assert result["proposal"] is None
    assert chat(client, "Какая минимальная партия?")["products"] == []


@pytest.mark.parametrize("message", [
    "Покажи цену артикула DEMO-160-AVAILABLE",
    "Проверь ID 900000160",
])
def test_explicit_inflected_sku_marker_or_id_selects_the_named_product(client, message):
    chat(client, "Проверь 200300285_")
    only_product(chat(client, message))
    only_product(chat(client, "Какая минимальная партия?"))


def test_city_at_start_of_followup_uses_the_named_information_warehouse(client):
    chat(client, "Проверь DEMO-160-AVAILABLE")
    result = chat(client, "В Алматы его сколько?")
    assert only_product(result, warehouse="almaty")["available_quantity"] == 6
    assert result["proposal"] is None
    assert client.get("/api/cart").json()["items"] == []
