"""H3 HTTP: загрузка, исправление строк и подтверждение без скрытых изменений."""

import io
import json
import sqlite3
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook

from app.api.uploads import MAX_FILE_BYTES, MAX_MULTIPART_BYTES
from app.config import ROOT, Settings
from app.main import create_app
from app.seed import seed


@pytest.fixture
def settings(tmp_path):
    settings = Settings(tmp_path / "h3.db", ROOT / "data", tmp_path / "web")
    seed(settings.database_path, settings.data_dir)
    return settings


@pytest.fixture
def client(settings):
    with TestClient(create_app(settings), raise_server_exceptions=False) as api:
        assert api.post("/api/session", json={}).status_code == 200
        yield api


def xlsx(rows=None):
    book = Workbook()
    sheet = book.active
    sheet.append(["Артикул", "Количество", "Ед. изм."])
    for row in rows or [["DEMO-160-AVAILABLE", 2, "шт"]]:
        sheet.append(row)
    output = io.BytesIO()
    book.save(output)
    book.close()
    return output.getvalue()


def upload(client, content=None, name="spec.xlsx", key=None, warehouse="astana", **kwargs):
    return client.post("/api/uploads", files={"file": (name, xlsx() if content is None else content)},
                       data={"request_id": key or str(uuid4()), "warehouse_id": warehouse}, **kwargs)


def proposal(client, saved, lines=None, key=None, warehouse="astana"):
    return client.post(f"/api/uploads/{saved['upload_id']}/proposal", json={
        "request_id": key or str(uuid4()), "warehouse_id": warehouse,
        "lines": saved["lines"] if lines is None else lines,
    })


def confirm(client, result, key=None):
    return client.post(f"/api/proposals/{result['proposal']['id']}/confirm", json={"request_id": key or str(uuid4())})


def test_upload_review_confirm_and_absolute_totals(client):
    saved = upload(client)
    assert saved.status_code == 200, saved.text
    saved = saved.json()
    assert saved["lines"] == [{"line_id": "1", "query": "DEMO-160-AVAILABLE", "quantity": 2, "unit": "шт"}]
    assert client.get("/api/cart").json()["items"] == []
    review_key = str(uuid4())
    result = proposal(client, saved, key=review_key)
    assert result.status_code == 200, result.text
    assert result.json()["cart"]["items"] == []
    assert proposal(client, saved, key=review_key).json() == result.json()
    key = str(uuid4())
    done = confirm(client, result.json(), key)
    assert done.json()["cart"]["total_kzt"] == 122000
    assert confirm(client, result.json(), key).json() == done.json()
    # Новое предложение той же спецификации задаёт итог, не прибавляет ещё две штуки.
    again = proposal(client, saved).json()
    assert again["proposal"]["items"][0]["target_quantity"] == 2
    assert confirm(client, again).json()["cart"]["items"][0]["quantity"] == 2


def test_file_ownership_and_restart(client, settings):
    content = xlsx()
    saved = upload(client, content).json()
    with sqlite3.connect(settings.database_path) as db:
        assert db.execute("SELECT content FROM uploads WHERE id=?", (saved["upload_id"],)).fetchone()[0] == content
    seed(settings.database_path, settings.data_dir)
    with TestClient(create_app(settings)) as other:
        assert upload(other, content).status_code == 401
        other.post("/api/session", json={})
        assert proposal(other, saved).status_code == 404
        other.cookies.set("kontur_session", client.cookies.get("kontur_session"))
        assert proposal(other, saved).status_code == 200
    assert proposal(client, {**saved, "upload_id": "u_missing"}).status_code == 404


def test_upload_retries_do_not_parse_again(client, monkeypatch):
    import app.documents as documents
    original = documents.parse_document
    calls = []

    def tracked(*args):
        calls.append(1)
        return original(*args)

    monkeypatch.setattr(documents, "parse_document", tracked)
    key, content = str(uuid4()), xlsx()
    first = upload(client, content, key=key)
    assert first.status_code == 200, first.text
    assert upload(client, content, key=key).json() == first.json()
    assert len(calls) == 1
    changed = upload(client, xlsx([["DEMO-160-AVAILABLE", 3, "шт"]]), key=key)
    assert changed.status_code == 409
    assert changed.json()["error"]["code"] == "IDEMPOTENCY_CONFLICT"
    assert upload(client, content, key=key, warehouse="almaty").status_code == 409


def test_validation_and_cross_origin(client):
    assert upload(client, headers={"Origin": "https://evil.example"}).status_code == 403
    assert upload(client, headers={"Origin": "http://127.0.0.1:5173"}).status_code == 200
    assert upload(client, key="invalid-uuid").status_code == 422
    assert upload(client, warehouse="missing").status_code == 404
    assert client.post("/api/uploads", json={}).status_code == 415
    bad = client.post("/api/uploads", content=b"invalid", headers={"Content-Type": "multipart/form-data; boundary=x"})
    assert bad.status_code == 422
    assert bad.json()["error"]["code"] == "VALIDATION_ERROR"


def test_actual_file_and_stream_size_limits(client):
    response = upload(client, b"x" * (MAX_FILE_BYTES + 1), name="large.pdf")
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "FILE_TOO_LARGE"
    response = client.post("/api/uploads", content=iter([b"x" * (MAX_MULTIPART_BYTES + 1)]),
                           headers={"Content-Type": "multipart/form-data; boundary=x"})
    assert response.status_code == 413


def test_duplicate_and_extra_multipart_fields(client):
    fields = [("file", ("a.xlsx", xlsx())), ("file", ("b.xlsx", xlsx()))]
    response = client.post("/api/uploads", files=fields, data={"request_id": str(uuid4()), "warehouse_id": "astana"})
    assert response.status_code == 422
    response = client.post("/api/uploads", files={"file": ("a.xlsx", xlsx())},
                           data={"request_id": str(uuid4()), "warehouse_id": "astana", "extra": "x"})
    assert response.status_code == 422


@pytest.mark.parametrize("name,content", [("document.exe", b"MZ"), ("fake.xlsx", b"not-zip"), ("fake.pdf", b"not-pdf")])
def test_unsupported_and_disguised_files(client, name, content):
    result = upload(client, content, name=name)
    assert result.status_code == 415
    assert result.json()["error"]["code"] == "UNSUPPORTED_FILE_TYPE"


def test_fractional_or_unknown_extraction_requires_review(client):
    saved = upload(client, xlsx([["DEMO-160-AVAILABLE", "2.5", "коробка"]])).json()
    assert saved["lines"][0]["quantity"] is None
    assert saved["lines"][0]["unit"] is None
    assert saved["warnings"]
    assert proposal(client, saved).status_code == 422
    fixed = [{**saved["lines"][0], "quantity": 2, "unit": "шт"}]
    assert proposal(client, saved, lines=fixed).json()["confirmation_required"] is True


@pytest.mark.parametrize("quantity", [0, -1, 1.5, True, "2", None])
def test_reviewed_quantity_must_be_positive_integer(client, quantity):
    saved = upload(client).json()
    lines = [{**saved["lines"][0], "quantity": quantity}]
    assert proposal(client, saved, lines=lines).status_code == 422


def test_review_line_ids_and_queries(client):
    saved = upload(client).json()
    assert proposal(client, saved, lines=[]).status_code == 422
    assert proposal(client, saved, lines=saved["lines"] * 2).status_code == 422
    assert proposal(client, saved, lines=[{**saved["lines"][0], "line_id": "unknown"}]).status_code == 422
    assert proposal(client, saved, lines=[{**saved["lines"][0], "query": " "}]).status_code == 422


def test_conflict_blocks_entire_file_and_review_can_remove_row(client):
    saved = upload(client, xlsx([["DEMO-160-AVAILABLE", 2, "шт"], ["200300285_", 1, "шт"]])).json()
    result = proposal(client, saved)
    assert result.status_code == 200, result.text
    assert result.json()["proposal"] is None
    assert any(check["status"] == "conflict" for check in result.json()["checks"])
    assert result.json()["cart"]["items"] == []
    assert proposal(client, saved, lines=saved["lines"][:1]).json()["proposal"] is not None


def test_changed_price_after_file_proposal_requires_confirmation_again(client, settings):
    saved = upload(client).json()
    result = proposal(client, saved).json()
    with sqlite3.connect(settings.database_path) as db:
        row = db.execute("SELECT payload FROM products WHERE id=900000160").fetchone()
        product = json.loads(row[0])
        product["price_kzt"] = 62000
        db.execute("UPDATE products SET payload=? WHERE id=900000160", (json.dumps(product),))
    response = confirm(client, result)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "PROPOSAL_CHANGED"
    assert client.get("/api/cart").json()["items"] == []


def test_upload_and_replayed_old_proposal_clear_text_confirmation(client):
    saved = upload(client).json()
    key = str(uuid4())
    old = proposal(client, saved, key=key)
    newer_lines = [{**saved["lines"][0], "quantity": 5}]
    assert proposal(client, saved, lines=newer_lines).json()["proposal"] is not None
    assert proposal(client, saved, key=key).json() == old.json()
    chat_body = {"message": "да, добавь", "warehouse_id": "astana", "request_id": str(uuid4())}
    assert client.post("/api/chat", json=chat_body).json()["cart"]["items"] == []
    assert proposal(client, saved).json()["proposal"] is not None
    assert upload(client).status_code == 200
    chat_body["request_id"] = str(uuid4())
    assert client.post("/api/chat", json=chat_body).json()["cart"]["items"] == []


@pytest.mark.parametrize("failure", ["content_type", "warehouse", "review_validation", "line_id", "idempotency"])
def test_rejected_upload_attempt_invalidates_previous_text_confirmation(client, failure):
    content, key = xlsx(), str(uuid4())
    saved = upload(client, content, key=key).json()
    assert proposal(client, saved).json()["proposal"] is not None
    if failure == "content_type":
        rejected = client.post("/api/uploads", json={})
    elif failure == "warehouse":
        rejected = upload(client, warehouse="missing")
    elif failure == "review_validation":
        rejected = proposal(client, saved, lines=[])
    elif failure == "line_id":
        rejected = proposal(client, saved, lines=[{**saved["lines"][0], "line_id": "missing"}])
    else:
        rejected = upload(client, content, key=key, warehouse="almaty")
    assert rejected.status_code >= 400
    response = client.post("/api/chat", json={"message": "да, добавь", "warehouse_id": "astana", "request_id": str(uuid4())})
    assert response.json()["cart"]["items"] == []


def test_cross_origin_error_cannot_invalidate_own_confirmation(client):
    saved = upload(client).json()
    assert proposal(client, saved).json()["proposal"] is not None
    assert upload(client, headers={"Origin": "https://evil.example"}).status_code == 403
    response = client.post("/api/chat", json={"message": "да, добавь", "warehouse_id": "astana", "request_id": str(uuid4())})
    assert response.json()["cart"]["total_kzt"] == 122000


@pytest.mark.parametrize("source", ["chat", "upload"])
def test_new_upload_in_another_tab_supersedes_pending_proposal(client, settings, source):
    if source == "chat":
        old = client.post("/api/chat", json={"message": "Добавь 2 шт DEMO-160-AVAILABLE",
            "warehouse_id": "astana", "request_id": str(uuid4())}).json()
    else:
        old = proposal(client, upload(client).json()).json()
    assert old["proposal"] is not None
    # Два клиента с одной cookie воспроизводят две вкладки браузера.
    with TestClient(create_app(settings)) as second_tab:
        second_tab.cookies.set("kontur_session", client.cookies.get("kontur_session"))
        assert upload(second_tab).status_code == 200
    response = confirm(client, old)
    assert response.status_code == 409, response.text
    assert response.json()["error"]["code"] == "PROPOSAL_SUPERSEDED"
    assert client.get("/api/cart").json()["items"] == []
    assert client.get("/api/cart").json()["version"] == 0
    assert confirm(client, old).status_code == 409
    fresh = proposal(client, upload(client).json()).json()
    assert confirm(client, fresh).json()["cart"]["total_kzt"] == 122000


def test_successful_review_without_proposal_supersedes_old_selection(client):
    saved = upload(client).json()
    review_key = str(uuid4())
    old = proposal(client, saved, key=review_key).json()
    blocked = proposal(client, saved, lines=[{**saved["lines"][0], "query": "200300285_"}])
    assert blocked.status_code == 200
    assert blocked.json()["proposal"] is None
    # Повтор сохранённого ответа не возвращает старому предложению действительность.
    assert proposal(client, saved, key=review_key).json() == old
    response = confirm(client, old)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "PROPOSAL_SUPERSEDED"
    assert client.get("/api/cart").json()["items"] == []


def test_replayed_upload_does_not_supersede_newer_proposal(client):
    content, upload_key = xlsx(), str(uuid4())
    saved = upload(client, content, key=upload_key).json()
    current = proposal(client, saved).json()
    assert upload(client, content, key=upload_key).json() == saved
    # Сетевой повтор той же загрузки не является новым документом.
    assert confirm(client, current).json()["cart"]["total_kzt"] == 122000


def test_rejected_upload_preserves_explicit_proposal_confirmation(client):
    old = proposal(client, upload(client).json()).json()
    assert upload(client, b"not-pdf", name="broken.pdf").status_code == 415
    # Ошибка очищает только краткое «да», но не отменяет явно выбранный ID.
    assert confirm(client, old).json()["cart"]["total_kzt"] == 122000


def test_upload_supersedes_only_its_own_session(client, settings):
    old = proposal(client, upload(client).json()).json()
    with TestClient(create_app(settings)) as other_session:
        other_session.post("/api/session", json={})
        assert upload(other_session).status_code == 200
    assert confirm(client, old).json()["cart"]["total_kzt"] == 122000


def test_new_upload_keeps_confirmed_proposal_retry_idempotent(client):
    old = proposal(client, upload(client).json()).json()
    assert confirm(client, old).json()["cart"]["total_kzt"] == 122000
    assert upload(client).status_code == 200
    repeated = confirm(client, old)
    assert repeated.status_code == 200
    assert repeated.json()["cart"]["items"][0]["quantity"] == 2
    assert repeated.json()["cart"]["version"] == 1



def test_rejected_review_preserves_explicit_proposal_confirmation(client):
    saved = upload(client).json()
    assert confirm(client, proposal(client, saved).json()).status_code == 200
    old = proposal(client, saved, lines=[{**saved["lines"][0], "quantity": 3}]).json()
    rejected = proposal(client, saved, warehouse="almaty")
    assert rejected.status_code == 409
    assert rejected.json()["error"]["code"] == "CART_WAREHOUSE_CONFLICT"
    confirmed = confirm(client, old)
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["cart"]["items"][0]["quantity"] == 3
