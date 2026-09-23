"""Короткие соединения SQLite, чтение API без создания пустой БД."""

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from app.errors import ApiError

SCHEMA = """
CREATE TABLE IF NOT EXISTS catalog_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS warehouses (
    id TEXT PRIMARY KEY, name TEXT NOT NULL, city TEXT NOT NULL,
    position INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY CHECK(id > 0), sku TEXT NOT NULL,
    name TEXT NOT NULL, payload TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS stock (
    product_id INTEGER NOT NULL REFERENCES products(id),
    warehouse_id TEXT NOT NULL REFERENCES warehouses(id),
    quantity INTEGER CHECK(quantity IS NULL OR quantity >= 0),
    PRIMARY KEY (product_id, warehouse_id)
);
"""


@contextmanager
def connect_read(path: Path):
    connection = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, timeout=3)
    connection.row_factory = sqlite3.Row
    connection.create_function("CASEFOLD", 1, str.casefold, deterministic=True)
    try:
        meta = connection.execute("SELECT value FROM catalog_meta WHERE key='version'").fetchone()
        if meta is None or meta[0] != "v1":
            raise sqlite3.DatabaseError("Каталог не инициализирован")
        yield connection
    finally:
        connection.close()


def require_warehouse(connection: sqlite3.Connection, warehouse_id: str) -> None:
    if not connection.execute("SELECT 1 FROM warehouses WHERE id=?", (warehouse_id,)).fetchone():
        raise ApiError(404, "WAREHOUSE_NOT_FOUND", "Склад не найден. Выберите склад из списка.", {"warehouse_id": warehouse_id})


def product_from_row(row: sqlite3.Row, warehouse_id: str) -> dict:
    product = json.loads(row["payload"])
    product.update(warehouse_id=warehouse_id, available_quantity=row["quantity"])
    return product
