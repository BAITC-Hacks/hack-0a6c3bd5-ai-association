"""Повторяемый импорт проверенного CSV-снимка без сетевых запросов."""

import csv
import json
import sqlite3
from pathlib import Path

from app.db import SCHEMA
from app.models import Product, Warehouse


def read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def optional_int(value: str):
    return None if value == "" else int(value)


def seed(database_path: Path, data_dir: Path) -> dict[str, int]:
    warehouses = [Warehouse.model_validate(row) for row in read_csv(data_dir / "warehouses.csv")]
    if not warehouses:
        raise ValueError("Снимок не содержит складов.")
    warehouse_ids = {item.id for item in warehouses}
    if len(warehouse_ids) != len(warehouses):
        raise ValueError("Повтор ID склада в снимке.")
    products = []
    for row in read_csv(data_dir / "products.csv"):
        for key in ("id", "price_kzt", "min_order_quantity", "total_quantity"):
            row[key] = optional_int(row[key])
        for key in ("properties", "documents", "snapshot"):
            row[key] = json.loads(row[key])
        row["image_url"] = row["image_url"] or None
        products.append(Product.model_validate({**row, "warehouse_id": warehouses[0].id, "available_quantity": None}))
    product_ids = {p.id for p in products}
    if not products or len(product_ids) != len(products):
        raise ValueError("Снимок пуст или содержит повтор ID товара.")
    stock = []
    seen = set()
    for row in read_csv(data_dir / "stock.csv"):
        pid, wid, quantity = int(row["product_id"]), row["warehouse_id"], optional_int(row["quantity"])
        if pid not in product_ids or wid not in warehouse_ids or (quantity is not None and quantity < 0) or (pid, wid) in seen:
            raise ValueError("Неверная ссылка, количество или дубликат в остатках.")
        seen.add((pid, wid))
        stock.append((pid, wid, quantity))
    # Отсутствующий остаток остаётся неизвестным, а не нулевым.
    stock.extend((pid, wid, None) for pid in product_ids for wid in warehouse_ids if (pid, wid) not in seen)
    database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database_path)
    try:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.executescript(SCHEMA)
        with connection:
            connection.executemany(
                "INSERT INTO warehouses VALUES (?,?,?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name, city=excluded.city, position=excluded.position",
                [(w.id, w.name, w.city, i) for i, w in enumerate(warehouses)],
            )
            for product in products:
                payload = product.model_dump(mode="json", exclude={"warehouse_id", "available_quantity"})
                connection.execute(
                    "INSERT INTO products VALUES (?,?,?,?) ON CONFLICT(id) DO UPDATE SET sku=excluded.sku, name=excluded.name, payload=excluded.payload",
                    (product.id, product.sku, product.name, json.dumps(payload, ensure_ascii=False)),
                )
            connection.executemany(
                "INSERT INTO stock VALUES (?,?,?) ON CONFLICT(product_id,warehouse_id) DO UPDATE SET quantity=excluded.quantity", stock,
            )
            connection.executemany("INSERT INTO catalog_meta VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", [("version", "v1"), ("default_warehouse_id", warehouses[0].id)])
    finally:
        connection.close()
    return {"products": len(products), "warehouses": len(warehouses), "stock_rows": len(stock)}
