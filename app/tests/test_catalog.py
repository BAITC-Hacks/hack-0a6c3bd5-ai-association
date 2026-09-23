"""Проверки контракта H1 и наиболее опасных ошибок данных."""

import sqlite3

import pytest
from fastapi.testclient import TestClient

from app.adapters.ekt import whole_number
from app.config import ROOT, Settings
from app.main import create_app
from app.seed import seed


@pytest.fixture
def settings(tmp_path):
    result = Settings(tmp_path / "catalog.db", ROOT / "data", tmp_path / "web")
    seed(result.database_path, result.data_dir)
    return result


@pytest.fixture
def client(settings):
    with TestClient(create_app(settings), raise_server_exceptions=False) as api:
        yield api


def test_health_and_warehouses(client):
    assert client.get("/api/health").json() == {"status": "ok", "api_version": "v1", "demo_mode": True, "database": "ok"}
    result = client.get("/api/warehouses").json()
    assert result["default_warehouse_id"] == "astana"
    assert result["items"][0] == {"id": "astana", "name": "Нур-Султан", "city": "Астана"}


def test_list_detail_and_warehouse_stock(client):
    items = client.get("/api/products", params={"warehouse_id": "astana", "q": "200300285_"}).json()["items"]
    assert len(items) == 1
    product = client.get(f"/api/products/{items[0]['id']}", params={"warehouse_id": "astana"}).json()
    assert product == items[0]
    assert product["available_quantity"] == 8
    assert product["total_quantity"] == 23
    assert client.get(f"/api/products/{product['id']}", params={"warehouse_id": "almaty"}).json()["available_quantity"] == 5
    assert "160" in product["name"]
    assert any(p["value"] == "250 А" for p in product["properties"])


def test_search_cyrillic_empty_and_literal_wildcards(client):
    for query in ("коробка", "КОРОБКА"):
        assert client.get("/api/products", params={"warehouse_id": "astana", "q": query}).json()["total"] > 0
    for query in ("нет-такого-артикула", "%", "' OR 1=1 --"):
        assert client.get("/api/products", params={"warehouse_id": "astana", "q": query}).json()["items"] == []
    all_items = client.get("/api/products", params={"warehouse_id": "astana"}).json()
    page = client.get("/api/products", params={"warehouse_id": "astana", "limit": 2, "offset": 1}).json()
    assert page["total"] == all_items["total"]
    assert page["items"] == all_items["items"][1:3]


def test_unknown_and_zero_are_different(settings, client):
    with sqlite3.connect(settings.database_path) as db:
        db.execute("UPDATE stock SET quantity=NULL WHERE product_id=45357 AND warehouse_id='astana'")
    a = client.get("/api/products/45357", params={"warehouse_id": "astana"}).json()
    b = client.get("/api/products/45357", params={"warehouse_id": "almaty"}).json()
    assert a["available_quantity"] is None
    assert b["available_quantity"] == 0
    assert a["min_order_quantity"] is None


@pytest.mark.parametrize("path,params,status,code", [
    ("/api/products", {}, 422, "VALIDATION_ERROR"),
    ("/api/products", {"warehouse_id": "bad"}, 404, "WAREHOUSE_NOT_FOUND"),
    ("/api/products/99999999", {"warehouse_id": "astana"}, 404, "PRODUCT_NOT_FOUND"),
    ("/api/products/0", {"warehouse_id": "astana"}, 422, "VALIDATION_ERROR"),
    ("/api/products/515291.0", {"warehouse_id": "astana"}, 422, "VALIDATION_ERROR"),
    ("/api/products", {"warehouse_id": "astana", "limit": "2.0"}, 422, "VALIDATION_ERROR"),
    ("/api/products/abc", {"warehouse_id": "astana"}, 422, "VALIDATION_ERROR"),
    ("/api/products", {"warehouse_id": "astana", "limit": 101}, 422, "VALIDATION_ERROR"),
    ("/api/products", {"warehouse_id": "astana", "limit": "1.5"}, 422, "VALIDATION_ERROR"),
    ("/api/products", {"warehouse_id": "astana", "offset": -1}, 422, "VALIDATION_ERROR"),
    ("/api/products", {"warehouse_id": "astana", "q": "a" * 201}, 422, "VALIDATION_ERROR"),
    ("/api/unknown", {}, 404, "NOT_FOUND"),
])
def test_errors(client, path, params, status, code):
    response = client.get(path, params=params)
    assert response.status_code == status
    error = response.json()["error"]
    assert error["code"] == code
    assert isinstance(error["details"], dict)
    if status == 422:
        assert error["details"]["fields"]


def test_no_database_does_not_create_file(tmp_path):
    missing = tmp_path / "absent.db"
    with TestClient(create_app(Settings(missing, ROOT / "data", tmp_path)), raise_server_exceptions=False) as client:
        for path in ("/api/health", "/api/warehouses", "/api/products?warehouse_id=astana"):
            response = client.get(path)
            assert response.status_code == 503
            assert response.json()["error"]["code"] == "DATABASE_UNAVAILABLE"
    assert not missing.exists()


def test_repeat_seed_preserves_snapshot_and_other_tables(settings, client):
    before = client.get("/api/products?warehouse_id=astana").json()
    with sqlite3.connect(settings.database_path) as db:
        db.execute("CREATE TABLE future_cart (value TEXT)")
        db.execute("INSERT INTO future_cart VALUES ('preserved')")
    seed(settings.database_path, settings.data_dir)
    assert client.get("/api/products?warehouse_id=astana").json() == before
    with sqlite3.connect(settings.database_path) as db:
        assert db.execute("SELECT value FROM future_cart").fetchone()[0] == "preserved"


def test_serve_spa_without_swallowing_api_or_missing_assets(settings):
    settings.web_dir.mkdir()
    (settings.web_dir / "index.html").write_text("<html>Проверка UI</html>", encoding="utf-8")
    with TestClient(create_app(settings)) as client:
        assert client.get("/").status_code == 200
        assert client.get("/cart").text == client.get("/").text
        assert client.get("/api/missing").status_code == 404
        assert client.get("/assets/missing.js").status_code == 404


def test_no_network_required(settings, monkeypatch):
    import socket
    def denied(*args, **kwargs):
        raise AssertionError("Сетевое соединение в demo")
    monkeypatch.setattr(socket, "create_connection", denied)
    monkeypatch.delenv("EKT_API_USERNAME", raising=False)
    monkeypatch.delenv("EKT_API_PASSWORD", raising=False)
    seed(settings.database_path, settings.data_dir)
    with TestClient(create_app(settings)) as client:
        assert client.get("/api/products?warehouse_id=astana").status_code == 200


@pytest.mark.parametrize("value,expected", [(0, 0), ("1", 1), ("1.0", 1), ("1.1", None), ("-1", None), (None, None), ("NaN", None), (True, None)])
def test_no_silent_rounding(value, expected):
    assert whole_number(value) == expected
