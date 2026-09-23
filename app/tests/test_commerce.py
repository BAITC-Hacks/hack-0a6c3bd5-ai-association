"""Проверки изоляции сессий, повторов и атомарного подтверждения."""

import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.commerce import Store, ensure_schema
from app.config import ROOT
from app.errors import ApiError
from app.seed import seed


@pytest.fixture
def commerce(tmp_path):
    path = tmp_path / "catalog.db"
    seed(path, ROOT / "data")
    ensure_schema(path)
    with sqlite3.connect(path) as db:
        for pid in (1001, 1002):
            product = {"id": pid, "sku": f"TEST-{pid}", "name": f"Тестовый товар {pid}", "description": "",
                       "price_kzt": 1000, "unit": "шт", "min_order_quantity": 1, "total_quantity": 30,
                       "properties": [], "image_url": None, "documents": [],
                       "snapshot": {"source": "demo_fixture", "captured_at": "2026-09-23T07:00:00Z", "source_url": None}}
            db.execute("INSERT INTO products VALUES (?,?,?,?)", (pid, product["sku"], product["name"], json.dumps(product)))
            db.executemany("INSERT INTO stock VALUES (?,?,?)", [(pid, "astana", 10), (pid, "almaty", 5)])
    store = Store(path)
    return store, store.create_session(None)


def proposal(store, token, items=None, warehouse="astana"):
    items = items if items is not None else [{"product_id": 1001, "target_quantity": 2}]
    status, result = store.execute(token, "chat", str(uuid4()), {"items": items},
                                  lambda db, sid: store.create_proposal(db, sid, warehouse, items))
    assert status == 200, result
    return result


def confirm(store, token, pid, key=None):
    return store.execute(token, "confirm", key or str(uuid4()), {"proposal_id": pid},
                         lambda db, sid: store.confirm_in(db, sid, pid))


def update_product(store, pid=1001, **changes):
    with sqlite3.connect(store.database_path) as db:
        payload = json.loads(db.execute("SELECT payload FROM products WHERE id=?", (pid,)).fetchone()[0])
        payload.update(changes)
        db.execute("UPDATE products SET payload=? WHERE id=?", (json.dumps(payload), pid))


def test_schema_preserves_catalog_and_session_and_never_creates_missing(commerce, tmp_path):
    store, token = commerce
    ensure_schema(store.database_path)
    assert store.create_session(token) == token
    assert Store(store.database_path).cart(token)["items"] == []
    seed(store.database_path, ROOT / "data")
    assert store.create_session(token) == token
    with pytest.raises(sqlite3.Error):
        ensure_schema(tmp_path / "missing.db")
    assert not (tmp_path / "missing.db").exists()


def test_session_isolation_and_foreign_proposal(commerce):
    store, a = commerce
    b = store.create_session(None)
    assert a != b
    p = proposal(store, a)
    assert store.cart(a)["items"] == []
    status, result = confirm(store, b, p["id"])
    assert status == 404
    assert result["error"]["code"] == "PROPOSAL_NOT_FOUND"
    assert store.cart(b)["items"] == []
    with pytest.raises(ApiError) as error:
        store.cart("unknown")
    assert error.value.status == 401


def test_idempotency_canonical_body_and_conflict(commerce):
    store, token = commerce
    calls = []
    def run(db, sid):
        calls.append(sid)
        store.record_message_in(db, sid, "user", "Тест")
        return 202, {"ok": True}
    first = store.execute(token, "chat", "key", {"a": 1, "b": 2}, run)
    second = store.execute(token, "chat", "key", {"b": 2, "a": 1}, run)
    assert first == second == (202, {"ok": True})
    assert len(calls) == 1
    with pytest.raises(ApiError) as error:
        store.execute(token, "chat", "key", {"a": 3}, run)
    assert error.value.code == "IDEMPOTENCY_CONFLICT"
    with sqlite3.connect(store.database_path) as db:
        assert db.execute("SELECT count(*) FROM messages").fetchone()[0] == 1


def test_confirm_is_absolute_preserves_lines_and_duplicate_never_reapplies(commerce):
    store, token = commerce
    p = proposal(store, token)
    status, result = confirm(store, token, p["id"], "first")
    assert status == 200
    assert result["cart"]["version"] == 1
    assert result["cart"]["total_kzt"] == 2000
    assert confirm(store, token, p["id"], "first") == (status, result)
    p2 = proposal(store, token, [{"product_id": 1002, "target_quantity": 3}])
    assert p2["result_total_kzt"] == 5000
    confirm(store, token, p2["id"])
    status, current = confirm(store, token, p["id"])
    assert status == 200
    assert current["cart"]["version"] == 2
    assert current["cart"]["total_kzt"] == 5000
    p3 = proposal(store, token)
    assert confirm(store, token, p3["id"])[1]["cart"]["version"] == 2


def test_parallel_same_request_applies_once(commerce):
    store, token = commerce
    p = proposal(store, token)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: confirm(store, token, p["id"], "same"), range(2)))
    assert results[0] == results[1]
    assert store.cart(token)["version"] == 1
    assert store.cart(token)["items"][0]["quantity"] == 2


def test_changed_price_persists_replacement_and_error_replay(commerce):
    store, token = commerce
    p = proposal(store, token)
    update_product(store, price_kzt=1200)
    first = confirm(store, token, p["id"], "changed")
    assert first[0] == 409
    assert first[1]["error"]["code"] == "PROPOSAL_CHANGED"
    replacement = first[1]["error"]["details"]["proposal"]
    assert replacement["result_total_kzt"] == 2400
    assert confirm(store, token, p["id"], "changed") == first
    assert store.cart(token)["items"] == []
    assert confirm(store, token, replacement["id"])[1]["cart"]["total_kzt"] == 2400


@pytest.mark.parametrize("changed", ["minimum", "stock", "unknown", "conflict"])
def test_changed_constraints_block_atomically(commerce, changed):
    store, token = commerce
    p = proposal(store, token, [{"product_id": 1002, "target_quantity": 2}, {"product_id": 1001, "target_quantity": 2}])
    if changed == "minimum":
        update_product(store, min_order_quantity=3)
    elif changed == "stock":
        with sqlite3.connect(store.database_path) as db:
            db.execute("UPDATE stock SET quantity=1 WHERE product_id=1001 AND warehouse_id='astana'")
    elif changed == "unknown":
        update_product(store, price_kzt=None)
    else:
        update_product(store, name="Автомат 160 А", description="Номинальный ток 160 А", properties=[
            {"name": "Номинальный ток", "value": "250 А", "source_field": "properties.Номинальный ток"}])
    status, error = confirm(store, token, p["id"])
    assert status == 409
    assert error["error"]["code"] == "PROPOSAL_CHANGED"
    assert error["error"]["details"]["proposal"] is None
    assert store.cart(token)["version"] == 0
    assert store.cart(token)["items"] == []


def test_minimum_change_still_requires_reconfirmation(commerce):
    store, token = commerce
    p = proposal(store, token)
    update_product(store, min_order_quantity=2)
    status, result = confirm(store, token, p["id"])
    assert status == 409
    assert result["error"]["details"]["proposal"] is not None


def test_delete_unknown_product_clears_warehouse_and_allows_switch(commerce):
    store, token = commerce
    confirm(store, token, proposal(store, token)["id"])
    update_product(store, price_kzt=None, min_order_quantity=None)
    delete = proposal(store, token, [{"product_id": 1001, "target_quantity": 0}])
    status, response = confirm(store, token, delete["id"])
    assert status == 200
    assert response["cart"]["warehouse_id"] is None
    assert response["cart"]["version"] == 2
    assert proposal(store, token, [{"product_id": 1002, "target_quantity": 1}], "almaty")["warehouse_id"] == "almaty"


def test_wrong_warehouse_expired_superseded_and_changed_cart(commerce):
    store, token = commerce
    old = proposal(store, token)
    current = proposal(store, token)
    assert confirm(store, token, old["id"])[1]["error"]["code"] == "PROPOSAL_SUPERSEDED"
    with sqlite3.connect(store.database_path) as db:
        current["expires_at"] = (datetime.now(UTC) - timedelta(seconds=1)).isoformat()
        db.execute("UPDATE proposals SET payload=? WHERE id=?", (json.dumps(current), current["id"]))
    assert confirm(store, token, current["id"])[1]["error"]["code"] == "PROPOSAL_EXPIRED"
    current = proposal(store, token)
    with sqlite3.connect(store.database_path) as db:
        db.execute("UPDATE sessions SET cart_version=1 WHERE token=?", (token,))
    assert confirm(store, token, current["id"])[1]["error"]["code"] == "CART_CHANGED"
    confirm(store, token, proposal(store, token)["id"])
    status, error = store.execute(token, "chat", str(uuid4()), {}, lambda db, sid:
        store.create_proposal(db, sid, "almaty", [{"product_id": 1002, "target_quantity": 1}]))
    assert status == 409
    assert error["error"]["code"] == "CART_WAREHOUSE_CONFLICT"


def test_text_confirmation_requires_last_presented_proposal(commerce):
    store, token = commerce
    p = proposal(store, token)
    def inspect(db, sid):
        assert store.last_proposal_in(db, sid) is None
        store.mark_presented_in(db, sid, p["id"])
        assert store.last_proposal_in(db, sid)["id"] == p["id"]
        store.invalidate_proposal_in(db, sid)
        assert store.last_proposal_in(db, sid) is None
        return {"ok": True}
    assert store.execute(token, "chat", str(uuid4()), {}, inspect)[0] == 200


def test_unexpected_callback_failure_rolls_back_all_writes(commerce):
    store, token = commerce
    p = proposal(store, token)
    def interrupted(db, sid):
        store.confirm_in(db, sid, p["id"])
        raise RuntimeError("Прервано до сохранения результата")
    with pytest.raises(RuntimeError):
        store.execute(token, "confirm", "interrupted", {"proposal_id": p["id"]}, interrupted)
    assert store.cart(token)["items"] == []
    assert confirm(store, token, p["id"], "interrupted")[1]["cart"]["version"] == 1

@pytest.mark.parametrize("initial_proposal", [True, False])
def test_replayed_old_chat_cannot_authorize_newer_proposal(commerce, initial_proposal):
    store, token = commerce
    def old_reply(db, sid):
        p = store.create_proposal(db, sid, "astana", [{"product_id": 1001, "target_quantity": 2}]) if initial_proposal else None
        store.mark_presented_in(db, sid, p["id"] if p else None)
        return {"proposal": p}
    first = store.execute(token, "chat", "old", {"message": "Старое сообщение"}, old_reply)
    # Повтор действительно последнего показанного предложения сохраняет его право подтверждения.
    assert store.execute(token, "chat", "old", {"message": "Старое сообщение"}, old_reply) == first
    with sqlite3.connect(store.database_path) as db:
        pointer = db.execute("SELECT presented_proposal_id FROM sessions WHERE token=?", (token,)).fetchone()[0]
        assert pointer == (first[1]["proposal"]["id"] if initial_proposal else None)
    newer = proposal(store, token, [{"product_id": 1001, "target_quantity": 5}])
    def show_newer(db, sid):
        store.mark_presented_in(db, sid, newer["id"])
        return {"proposal": newer}
    store.execute(token, "chat", "newer", {}, show_newer)
    assert store.execute(token, "chat", "old", {"message": "Старое сообщение"}, old_reply) == first
    with sqlite3.connect(store.database_path) as db:
        pointer = db.execute("SELECT presented_proposal_id FROM sessions WHERE token=?", (token,)).fetchone()[0]
        assert pointer is None
        assert db.execute("SELECT status FROM proposals WHERE id=?", (newer["id"],)).fetchone()[0] == "pending"
    assert store.cart(token)["items"] == []

def test_replayed_changed_confirmation_cannot_authorize_other_replacement(commerce):
    store, token = commerce
    initial = proposal(store, token)
    update_product(store, price_kzt=1200)
    changed = confirm(store, token, initial["id"], "price-change")
    assert changed[0] == 409
    assert changed[1]["error"]["details"]["proposal"] is not None
    newer = proposal(store, token, [{"product_id": 1001, "target_quantity": 5}])
    def show_newer(db, sid):
        store.mark_presented_in(db, sid, newer["id"])
        return {"proposal": newer}
    store.execute(token, "chat", "newer", {}, show_newer)
    assert confirm(store, token, initial["id"], "price-change") == changed
    with sqlite3.connect(store.database_path) as db:
        assert db.execute("SELECT presented_proposal_id FROM sessions WHERE token=?", (token,)).fetchone()[0] is None
        assert db.execute("SELECT status FROM proposals WHERE id=?", (newer["id"],)).fetchone()[0] == "pending"
    assert store.cart(token)["items"] == []