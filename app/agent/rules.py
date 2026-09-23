"""Проверки покупок используют исходные данные, решение модели не учитывается."""

import re


CURRENT_RE = re.compile(r"(?<![\w.,])([0-9]+(?:[.,][0-9]+)?)\s*[аa](?!\w)", re.I)
SPEC_NAMES = {
    "current_a": {"nominalnyy_tok", "номинальный ток"},
    "poles": {"kolichestvo_polyusov", "количество полюсов"},
    "voltage_v": {"nominalnoe_napryazhenie", "номинальное напряжение"},
    "breaking_capacity_ka": {"nominalnaya_otklyuchayushchaya_sposobnost", "номинальная отключающая способность", "отключающая способность"},
}
SPEC_LABELS = {"current_a": "Номинальный ток", "poles": "Количество полюсов", "voltage_v": "Номинальное напряжение", "breaking_capacity_ka": "Отключающая способность"}
TEXT_PATTERNS = {
    "current_a": CURRENT_RE,
    "poles": re.compile(r"(?:количество полюсов\s*[:—-]?\s*([0-9]+)|(?<!\w)([0-9]+)\s*(?:p|ф|полюс(?:а|ов)?)(?!\w))", re.I),
    "voltage_v": re.compile(r"(?<![\w.,])([0-9]+(?:[.,][0-9]+)?)\s*(?:в|v)(?!\w)", re.I),
    "breaking_capacity_ka": re.compile(r"(?<![\w.,])([0-9]+(?:[.,][0-9]+)?)\s*(?:ка|ka)(?!\w)", re.I),
}


def _number(value: str) -> str | None:
    result = re.fullmatch(r"\s*([0-9]+(?:[.,][0-9]+)?)\s*(?:[аaвv]|ка|ka)?\s*", value, re.I)
    if result is None:
        return None
    return result[1].replace(",", ".").rstrip("0").rstrip(".") if "." in result[1].replace(",", ".") else result[1]


def specification_sources(product: dict, field: str) -> list[dict]:
    sources = []
    for key in ("name", "description"):
        for match in TEXT_PATTERNS[field].finditer(product.get(key) or ""):
            value = next(group for group in match.groups() if group is not None)
            normalized = _number(value)
            entry = {"field": key, "value": normalized}
            if entry not in sources:
                sources.append(entry)
    for prop in product.get("properties", []):
        if prop["name"].casefold().strip() in SPEC_NAMES[field]:
            normalized = _number(str(prop["value"]))
            # Нечитаемое свойство сохраняется в источниках и запрещает вывод match.
            sources.append({"field": prop.get("source_field", f"properties.{prop['name']}"), "value": normalized or str(prop["value"])})
    return sources


def consistent_spec(product: dict, field: str) -> str | None:
    values = {item["value"] for item in specification_sources(product, field)}
    if len(values) != 1:
        return None
    value = next(iter(values))
    return value if _number(value) is not None else None


def category(product: dict) -> str | None:
    for prop in product.get("properties", []):
        if prop["name"].casefold() in {"obyem", "тип изделия", "категория"}:
            return str(prop["value"]).casefold().strip()
    text = (product.get("name", "") + " " + product.get("description", "")).casefold()
    if "диф" in text:
        return "дифференциальный автомат"
    if "автоматический выключатель" in text or re.search(r"\bавтомат\b", text):
        return "автоматический выключатель"
    return None


def product_checks(product: dict, expected_current: int | None = None) -> list[dict]:
    checks = []
    for field in SPEC_NAMES:
        sources = specification_sources(product, field)
        if not sources and not (field == "current_a" and expected_current is not None):
            continue
        values = list(dict.fromkeys(item["value"] for item in sources))
        expected = str(expected_current) if field == "current_a" and expected_current is not None else (values[0] if values else None)
        valid = all(_number(value) is not None for value in values)
        status = "unknown" if not values or not valid else ("conflict" if len(values) > 1 or expected != values[0] else "match")
        checks.append({"product_id": product["id"], "field": field, "expected": expected, "actual": " / ".join(values) or None, "status": status, "sources": sources})
    for field in ("price_kzt", "min_order_quantity", "available_quantity"):
        value = product.get(field)
        checks.append({"product_id": product["id"], "field": field, "expected": None, "actual": None if value is None else str(value), "status": "unknown" if value is None else "match", "sources": [{"field": field, "value": str(value)}] if value is not None else []})
    return checks


def purchase_blockers(product: dict, quantity: int) -> list[str]:
    if type(quantity) is not int or quantity < 0:
        return ["Укажите целое неотрицательное количество."]
    if quantity == 0:
        return []
    reasons = []
    for field, label, minimum in (("price_kzt", "цена", 0), ("min_order_quantity", "минимальная партия", 1), ("available_quantity", "остаток выбранного склада", 0)):
        value = product.get(field)
        if type(value) is not int or value < minimum:
            reasons.append(f"Неизвестна или неподдерживаема {label}.")
    if type(product.get("min_order_quantity")) is int and quantity < product["min_order_quantity"]:
        reasons.append(f"Минимальная партия — {product['min_order_quantity']} {product.get('unit', 'шт')}.")
    if type(product.get("available_quantity")) is int and quantity > product["available_quantity"]:
        reasons.append(f"На выбранном складе только {product['available_quantity']} {product.get('unit', 'шт')}; общего остатка недостаточно для подтверждения наличия здесь.")
    if product.get("unit") not in {"шт", "м"}:
        reasons.append("Единица товара не поддерживается в демонстрационной корзине.")
    for check in product_checks(product):
        if check["field"] in SPEC_NAMES and check["status"] in {"conflict", "unknown"}:
            reasons.append(f"{SPEC_LABELS[check['field']]}: данные источников противоречат друг другу или не распознаны ({check['actual']}).")
    return reasons


def analog_matches(candidate: dict, reference: dict | None, current: int | None) -> bool:
    if current is None or consistent_spec(candidate, "current_a") != str(current):
        return False
    required_category = category(reference) if reference else "автоматический выключатель"
    if not required_category or category(candidate) != required_category:
        return False
    # При известном образце сравниваются все критичные параметры, пропуск не равен совпадению.
    if reference:
        for field in ("poles", "voltage_v", "breaking_capacity_ka"):
            expected = consistent_spec(reference, field)
            if expected is None or consistent_spec(candidate, field) != expected:
                return False
    return not purchase_blockers(candidate, candidate.get("min_order_quantity") or 1)
