"""Анонимные сессии и атомарное подтверждение локальной корзины."""

import json
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.agent.rules import purchase_blockers
from app.db import product_from_row, require_warehouse
from app.errors import ApiError


SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    token TEXT PRIMARY KEY, cart_id TEXT NOT NULL UNIQUE,
    cart_version INTEGER NOT NULL DEFAULT 0,
    warehouse_id TEXT, presented_proposal_id TEXT
);
CREATE TABLE IF NOT EXISTS cart_items (
    session_token TEXT NOT NULL REFERENCES sessions(token),
    product_id INTEGER NOT NULL, payload TEXT NOT NULL,
    PRIMARY KEY (session_token, product_id)
);
CREATE TABLE IF NOT EXISTS proposals (
    id TEXT PRIMARY KEY, session_token TEXT NOT NULL REFERENCES sessions(token),
    status TEXT NOT NULL, payload TEXT NOT NULL, expectations TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS proposals_session ON proposals(session_token, status);
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_token TEXT NOT NULL REFERENCES sessions(token),
    role TEXT NOT NULL, content TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);
CREATE TABLE IF NOT EXISTS uploads (
    id TEXT PRIMARY KEY,
    session_token TEXT NOT NULL REFERENCES sessions(token),
    content_hash TEXT NOT NULL, content BLOB NOT NULL, payload TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS uploads_session ON uploads(session_token);
CREATE TABLE IF NOT EXISTS request_results (
    session_token TEXT NOT NULL REFERENCES sessions(token),
    operation TEXT NOT NULL, request_id TEXT NOT NULL,
    body TEXT NOT NULL, status INTEGER NOT NULL, response TEXT NOT NULL,
    PRIMARY KEY (session_token, operation, request_id)
);
"""


def canonical(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


@contextmanager
def connect_write(path: Path):
    # mode=rw запрещает незаметно создать пустую БД вместо каталога.
    db = sqlite3.connect(path.resolve().as_uri() + "?mode=rw", uri=True, timeout=15)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    try:
        meta = db.execute("SELECT value FROM catalog_meta WHERE key='version'").fetchone()
        if meta is None or meta[0] != "v1":
            raise sqlite3.DatabaseError("Каталог не инициализирован")
        yield db
    finally:
        db.close()


def ensure_schema(database_path: Path) -> None:
    with connect_write(database_path) as db:
        db.executescript(SCHEMA)


class Store:
    def __init__(self, database_path: Path):
        self.database_path = database_path

    @staticmethod
    def _session(db, token):
        session = db.execute("SELECT * FROM sessions WHERE token=?", (token,)).fetchone()
        if session is None:
            raise ApiError(401, "SESSION_REQUIRED", "Сначала откройте анонимную сессию.")
        return session

    def create_session(self, existing_token: str | None) -> str:
        with connect_write(self.database_path) as db, db:
            db.execute("BEGIN IMMEDIATE")
            if existing_token and db.execute("SELECT 1 FROM sessions WHERE token=?", (existing_token,)).fetchone():
                return existing_token
            token = secrets.token_urlsafe(32)
            db.execute("INSERT INTO sessions(token,cart_id) VALUES (?,?)", (token, "c_" + secrets.token_urlsafe(18)))
            return token

    def clear_presented(self, token: str) -> None:
        with connect_write(self.database_path) as db, db:
            db.execute("BEGIN IMMEDIATE")
            self.invalidate_proposal_in(db, token)

    def cart(self, token: str) -> dict:
        with connect_write(self.database_path) as db:
            # Оба чтения видят один снимок даже при параллельном подтверждении.
            db.execute("BEGIN")
            return self.cart_in(db, token)

    def cart_in(self, db, token: str) -> dict:
        session = self._session(db, token)
        items = [json.loads(row[0]) for row in db.execute(
            "SELECT payload FROM cart_items WHERE session_token=? ORDER BY product_id", (token,)
        )]
        return {"id": session["cart_id"], "version": session["cart_version"],
                "warehouse_id": session["warehouse_id"], "items": items,
                "total_kzt": sum(item["line_total_kzt"] for item in items),
                "cart_url": "/cart", "scope": "local_demo"}

    def record_message_in(self, db, token: str, role: str, content: str) -> None:
        self._session(db, token)
        if role not in {"user", "assistant"}:
            raise ValueError("Неизвестная роль сообщения.")
        db.execute("INSERT INTO messages(session_token,role,content) VALUES (?,?,?)", (token, role, content))

    def execute(self, token: str, operation: str, request_id: str, body: dict, callback) -> tuple[int, dict]:
        with connect_write(self.database_path) as db, db:
            db.execute("BEGIN IMMEDIATE")
            self._session(db, token)
            encoded = canonical(body)
            previous = db.execute(
                "SELECT body,status,response FROM request_results WHERE session_token=? AND operation=? AND request_id=?",
                (token, operation, request_id),
            ).fetchone()
            if previous:
                if previous["body"] != encoded:
                    raise ApiError(409, "IDEMPOTENCY_CONFLICT", "Этот request_id уже использован с другим содержимым.")
                response = json.loads(previous["response"])
                error_details = response.get("error", {}).get("details", {})
                if operation in {"chat", "upload", "upload_proposal"} or "proposal" in error_details:
                    shown = response.get("proposal") if "proposal" in response else error_details.get("proposal")
                    shown_id = shown["id"] if shown else None
                    current_id = self._session(db, token)["presented_proposal_id"]
                    if shown_id != current_id:
                        # Старый ответ не разрешает подтвердить другое, более новое предложение.
                        self.invalidate_proposal_in(db, token)
                return previous["status"], response
            try:
                result = callback(db, token)
                status, response = result if isinstance(result, tuple) else (200, result)
            except ApiError as exc:
                # Новое предложение после изменения цены сохраняется вместе с 409.
                status = exc.status
                response = {"error": {"code": exc.code, "message": exc.message, "details": exc.details}}
            db.execute("INSERT INTO request_results VALUES (?,?,?,?,?,?)",
                       (token, operation, request_id, encoded, status, canonical(response)))
            return status, response

    @staticmethod
    def product_in(db, product_id: int, warehouse_id: str) -> dict:
        require_warehouse(db, warehouse_id)
        row = db.execute(
            "SELECT p.payload,s.quantity FROM products p LEFT JOIN stock s ON s.product_id=p.id AND s.warehouse_id=? WHERE p.id=?",
            (warehouse_id, product_id),
        ).fetchone()
        if row is None:
            raise ApiError(404, "PRODUCT_NOT_FOUND", "Товар не найден.", {"product_id": product_id})
        return product_from_row(row, warehouse_id)

    @staticmethod
    def _proposal(row) -> dict:
        value = json.loads(row["payload"])
        value["status"] = row["status"]
        return value

    def mark_presented_in(self, db, token: str, proposal_id: str | None) -> None:
        self._session(db, token)
        if proposal_id is not None:
            row = db.execute("SELECT 1 FROM proposals WHERE id=? AND session_token=? AND status='pending'", (proposal_id, token)).fetchone()
            if row is None:
                raise ApiError(404, "PROPOSAL_NOT_FOUND", "Предложение не найдено.")
        db.execute("UPDATE sessions SET presented_proposal_id=? WHERE token=?", (proposal_id, token))

    def invalidate_proposal_in(self, db, token: str) -> None:
        self.mark_presented_in(db, token, None)

    def last_proposal_in(self, db, token: str) -> dict | None:
        session = self._session(db, token)
        row = db.execute("SELECT * FROM proposals WHERE id=? AND session_token=? AND status='pending'",
                         (session["presented_proposal_id"], token)).fetchone()
        if row is None:
            return None
        proposal = self._proposal(row)
        if datetime.fromisoformat(proposal["expires_at"]) <= datetime.now(UTC):
            db.execute("UPDATE proposals SET status='expired' WHERE id=?", (proposal["id"],))
            self.invalidate_proposal_in(db, token)
            return None
        return proposal

    def create_proposal(self, db, token: str, warehouse_id: str, items: list[dict]) -> dict:
        cart = self.cart_in(db, token)
        require_warehouse(db, warehouse_id)
        if cart["items"] and cart["warehouse_id"] != warehouse_id:
            raise ApiError(409, "CART_WAREHOUSE_CONFLICT", "Сначала подтвердите удаление товаров текущего склада.")
        if not items or len({item["product_id"] for item in items}) != len(items):
            raise ApiError(422, "VALIDATION_ERROR", "Предложение должно содержать неповторяющиеся позиции.")
        resulting = {item["product_id"]: item.copy() for item in cart["items"]}
        proposal_items, expectations = [], {}
        for item in items:
            product_id, quantity = item["product_id"], item["target_quantity"]
            if type(quantity) is not int or quantity < 0:
                raise ApiError(422, "VALIDATION_ERROR", "Укажите целое неотрицательное количество.")
            if quantity == 0:
                old = resulting.pop(product_id, None)
                # Удаление возможно даже если товар исчез из каталога.
                price = old["unit_price_kzt"] if old else 0
            else:
                product = self.product_in(db, product_id, warehouse_id)
                blockers = purchase_blockers(product, quantity)
                if blockers:
                    raise ApiError(409, "PROPOSAL_CHANGED", " ".join(blockers), {"proposal": None})
                price = product["price_kzt"]
                expectations[str(product_id)] = {"price_kzt": price, "min_order_quantity": product["min_order_quantity"]}
                resulting[product_id] = self._cart_line(product, quantity)
            proposal_items.append({"product_id": product_id, "target_quantity": quantity, "unit_price_kzt": price})
        proposal = {"id": "p_" + secrets.token_urlsafe(18), "status": "pending", "warehouse_id": warehouse_id,
                    "cart_version": cart["version"], "items": proposal_items,
                    "result_total_kzt": sum(item["line_total_kzt"] for item in resulting.values()),
                    "expires_at": (datetime.now(UTC) + timedelta(minutes=15)).isoformat().replace("+00:00", "Z")}
        db.execute("UPDATE proposals SET status='superseded' WHERE session_token=? AND status='pending'", (token,))
        db.execute("INSERT INTO proposals VALUES (?,?,?,?,?)",
                   (proposal["id"], token, "pending", canonical(proposal), canonical(expectations)))
        self.invalidate_proposal_in(db, token)
        return proposal

    @staticmethod
    def _cart_line(product: dict, quantity: int) -> dict:
        return {"product_id": product["id"], "sku": product["sku"], "name": product["name"], "unit": product["unit"],
                "quantity": quantity, "unit_price_kzt": product["price_kzt"], "line_total_kzt": product["price_kzt"] * quantity}

    def confirm_in(self, db, token: str, proposal_id: str) -> dict:
        cart = self.cart_in(db, token)
        row = db.execute("SELECT * FROM proposals WHERE id=? AND session_token=?", (proposal_id, token)).fetchone()
        if row is None:
            raise ApiError(404, "PROPOSAL_NOT_FOUND", "Предложение не найдено.")
        proposal = self._proposal(row)
        if proposal["status"] == "confirmed":
            return {"proposal_id": proposal_id, "status": "confirmed", "cart": cart}
        if proposal["status"] == "superseded":
            raise ApiError(409, "PROPOSAL_SUPERSEDED", "Предложение заменено новым. Подтвердите актуальное предложение.")
        if proposal["status"] == "expired" or datetime.fromisoformat(proposal["expires_at"]) <= datetime.now(UTC):
            db.execute("UPDATE proposals SET status='expired' WHERE id=?", (proposal_id,))
            self.invalidate_proposal_in(db, token)
            raise ApiError(409, "PROPOSAL_EXPIRED", "Срок предложения истёк. Запросите новое предложение.")
        if proposal["cart_version"] != cart["version"]:
            raise ApiError(409, "CART_CHANGED", "Корзина изменилась. Запросите новое предложение.")
        if cart["items"] and cart["warehouse_id"] != proposal["warehouse_id"]:
            raise ApiError(409, "CART_WAREHOUSE_CONFLICT", "Предложение относится к другому складу.")
        expectations = json.loads(row["expectations"])
        resulting = {item["product_id"]: item.copy() for item in cart["items"]}
        changes, blocked = [], False
        for item in proposal["items"]:
            product_id, quantity = item["product_id"], item["target_quantity"]
            if quantity == 0:
                resulting.pop(product_id, None)
                continue
            try:
                product = self.product_in(db, product_id, proposal["warehouse_id"])
            except ApiError:
                changes.append(f"Товар {product_id} или склад больше недоступен.")
                blocked = True
                continue
            old = expectations[str(product_id)]
            if product["price_kzt"] != old["price_kzt"]:
                changes.append(f"Цена {product['sku']}: {old['price_kzt']} → {product['price_kzt']} ₸.")
            if product["min_order_quantity"] != old["min_order_quantity"]:
                changes.append(f"Минимальный заказ {product['sku']}: {old['min_order_quantity']} → {product['min_order_quantity']}.")
            blockers = purchase_blockers(product, quantity)
            if blockers:
                changes.extend(blockers)
                blocked = True
            else:
                resulting[product_id] = self._cart_line(product, quantity)
        if changes:
            db.execute("UPDATE proposals SET status='superseded' WHERE id=?", (proposal_id,))
            self.invalidate_proposal_in(db, token)
            replacement = None if blocked else self.create_proposal(db, token, proposal["warehouse_id"], proposal["items"])
            if replacement:
                self.mark_presented_in(db, token, replacement["id"])
            raise ApiError(409, "PROPOSAL_CHANGED", " ".join(changes) + " Требуется новое подтверждение.", {"proposal": replacement})
        new_items = sorted(resulting.values(), key=lambda item: item["product_id"])
        if new_items != cart["items"]:
            db.execute("DELETE FROM cart_items WHERE session_token=?", (token,))
            db.executemany("INSERT INTO cart_items VALUES (?,?,?)",
                           [(token, item["product_id"], canonical(item)) for item in new_items])
            db.execute("UPDATE sessions SET cart_version=cart_version+1,warehouse_id=? WHERE token=?",
                       (proposal["warehouse_id"] if new_items else None, token))
        db.execute("UPDATE proposals SET status='confirmed' WHERE id=?", (proposal_id,))
        self.invalidate_proposal_in(db, token)
        return {"proposal_id": proposal_id, "status": "confirmed", "cart": self.cart_in(db, token)}
