"""Только GET к API организаторов. Обычный seed/serve не обращается к сети."""

import base64
import csv
import json
import os
import urllib.error
import urllib.request
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # BasicAuth нельзя пересылать другому адресу при перенаправлении.
        raise urllib.error.URLError("Перенаправление API запрещено")


class EktReadAdapter:
    def __init__(self):
        username, password = os.getenv("EKT_API_USERNAME"), os.getenv("EKT_API_PASSWORD")
        if not username or not password:
            raise ValueError("Для чтения ekt.kz задайте EKT_API_USERNAME и EKT_API_PASSWORD в локальной .env.")
        self._authorization = "Basic " + base64.b64encode(f"{username}:{password}".encode()).decode()
        self._opener = urllib.request.build_opener(NoRedirect)

    def _get(self, suffix: str) -> dict:
        request = urllib.request.Request("https://ekt.kz/api/products" + suffix, headers={"Authorization": self._authorization, "Accept": "application/json"})
        try:
            with self._opener.open(request, timeout=15) as response:
                payload = response.read(5 * 1024 * 1024 + 1)
                if len(payload) > 5 * 1024 * 1024:
                    raise ValueError("Ответ ekt.kz превышает допустимый размер.")
                result = json.loads(payload)
                if not isinstance(result, dict):
                    raise ValueError("Неожиданный формат ответа ekt.kz.")
                return result
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise ValueError("Не удалось прочитать ekt.kz. Проверьте сеть и локальные доступы.") from None

    def list_products(self, page: int = 1) -> dict:
        if page < 1:
            raise ValueError("Номер страницы должен быть положительным.")
        return self._get(f"?page={page}")

    def get_product(self, product_id: int) -> dict:
        if product_id < 1:
            raise ValueError("ID товара должен быть положительным.")
        result = self._get(f"/detail?id={product_id}")
        if result.get("id") != product_id:
            raise ValueError("API вернул другую карточку товара.")
        return result


def save_snapshot(ids: list[int], output: str) -> None:
    path = Path(output)
    if path.exists():
        raise ValueError("Файл снимка уже существует. Укажите новое имя.")
    if not 1 <= len(ids) <= 50:
        raise ValueError("За один импорт поддерживается от 1 до 50 карточек.")
    adapter = EktReadAdapter()
    snapshot = []
    for product_id in dict.fromkeys(ids):
        raw = adapter.get_product(product_id)
        snapshot.append({"captured_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"), "source_url": f"https://ekt.kz/api/products/detail?id={product_id}", "data": raw})
    with path.open("x", encoding="utf-8") as file:
        json.dump(snapshot, file, ensure_ascii=False, indent=2)


def whole_number(value, minimum: int = 0) -> int | None:
    """Дробные, отрицательные и неизвестные числа не округляются."""
    if value is None or value == "" or isinstance(value, bool):
        return None
    try:
        number = Decimal(str(value).replace(",", "."))
        if not number.is_finite() or number != number.to_integral_value() or number < minimum:
            return None
        return int(number)
    except InvalidOperation:
        return None


def export_seed(snapshot: list[dict], output_dir: Path, unit: str) -> None:
    """CSV для проверенной выборки. Единицу, отсутствующую в API, задают явно.

    Такой набор маркируется demo_fixture: цены/остатки/характеристики взяты из
    сохранённого API, а единица учёта — локальное условие демонстрации.
    """
    if unit not in {"шт", "м"}:
        raise ValueError("Поддерживаются только шт и м.")
    selection = [(24, "astana", "Астана"), (13, "almaty", "Алматы"), (3, "shymkent", "Шымкент")]
    warehouse_names = {}
    for entry in snapshot:
        for store in entry["data"].get("stores", []):
            warehouse_names[store["id"]] = store["name"]
    products, stock = [], []
    for entry in snapshot:
        raw = entry["data"]
        properties = [{"name": key, "value": value if isinstance(value, str) else json.dumps(value, ensure_ascii=False), "source_field": f"properties.{key}"} for key, value in raw.get("properties", {}).items()]
        properties.append({"name": "Единица учёта демо", "value": unit, "source_field": "demo.unit_override"})
        products.append({
            "id": raw["id"], "sku": raw["article"], "name": raw["name"], "description": raw.get("description") or "",
            "price_kzt": whole_number(raw.get("price")), "unit": unit,
            "min_order_quantity": whole_number(raw.get("properties", {}).get("KRATNOST_MIN"), 1),
            "total_quantity": whole_number(raw.get("quantity")), "properties": json.dumps(properties, ensure_ascii=False),
            "image_url": "", "documents": "[]",
            "snapshot": json.dumps({"source": "demo_fixture", "captured_at": entry["captured_at"], "source_url": entry["source_url"]}, ensure_ascii=False),
        })
        stores = {store["id"]: store.get("quantity") for store in raw.get("stores", [])}
        for source_id, warehouse_id, _ in selection:
            if source_id in warehouse_names:
                stock.append({"product_id": raw["id"], "warehouse_id": warehouse_id, "quantity": whole_number(stores.get(source_id))})
    warehouses = [{"id": internal, "name": warehouse_names[source_id], "city": city} for source_id, internal, city in selection if source_id in warehouse_names]
    if not products or not warehouses:
        raise ValueError("Снимок не содержит поддерживаемых товаров/складов.")
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = [output_dir / f"{name}.csv" for name in ("products", "warehouses", "stock")]
    if any(path.exists() for path in paths):
        raise ValueError("CSV уже существуют. Экспортируйте в новую папку для сравнения.")
    for path, rows in zip(paths, (products, warehouses, stock), strict=True):
        with path.open("x", encoding="utf-8", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
