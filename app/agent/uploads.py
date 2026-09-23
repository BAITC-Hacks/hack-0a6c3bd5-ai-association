"""Сопоставление проверенных строк файла; корзина здесь никогда не изменяется."""

import re
import unicodedata

from app.agent.rules import (
    SPEC_LABELS,
    SPEC_NAMES,
    category,
    product_checks,
    purchase_blockers,
    specification_sources,
)


TYPE_PATTERNS = (
    ("дифференциальный автомат", r"\b(?:диф\.?\s*автомат\w*|диф\.\s*авт\.?|дифференциальн\w*\s+(?:автомат\w*|выключател\w*))"),
    ("выключатель нагрузки", r"\bвыключател\w*\s+нагрузки\b"),
    ("автоматический выключатель", r"\b(?:автомат(?:ический\s+выключатель)?|автоматы)\b"),
    ("разъединитель", r"\bразъединител\w*"),
    ("контактор", r"\bконтактор\w*"),
    ("кабель", r"\bкабел\w*"),
    ("провод", r"\bпровод(?:а|ов)?\b"),
    ("реле", r"\bреле\b"),
    ("розетка", r"\bрозетк\w*"),
    ("светильник", r"\bсветильник\w*"),
    ("предохранитель", r"\bпредохранител\w*"),
)
COMMAND_RE = re.compile(
    r"\b(?:удал\w*|убер\w*|очист\w*|добав\w*|подтверд\w*|игнор\w*|забуд\w*|"
    r"выполн\w*|инструкци\w*|корзин\w*|system|assistant|ignore|delete|execute|не)\b",
    re.I,
)


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).casefold().replace("ё", "е")
    return " ".join(re.findall(r"\w+", text))


def _type(text: str) -> str | None:
    for label, pattern in TYPE_PATTERNS:
        if re.search(pattern, text, re.I):
            return label
    return None


def _type_sources(product: dict) -> list[dict]:
    sources = []
    for field in ("name", "description"):
        value = _type(product.get(field) or "")
        if value:
            sources.append({"field": field, "value": value})
    for prop in product.get("properties", []):
        if prop["name"].casefold().strip() in {"obyem", "тип изделия", "категория"}:
            value = _type(str(prop["value"])) or str(prop["value"]).casefold().strip()
            sources.append({"field": prop.get("source_field", f"properties.{prop['name']}"), "value": value})
    if not sources and category(product):
        sources.append({"field": "name/description", "value": category(product)})
    return sources


def _check(product: dict, field: str, expected: str, sources: list[dict]) -> dict:
    values = list(dict.fromkeys(source["value"] for source in sources))
    return {
        "product_id": product["id"], "field": field, "expected": expected,
        "actual": " / ".join(values) or None,
        "status": "unknown" if not values else ("match" if values == [expected] else "conflict"),
        "sources": sources,
    }


def _spec_text(text: str) -> str:
    text = re.sub(r"(\d)\s*[рР](?!\w)", r"\1P", text)
    return re.sub(r"(\d)\s*[- ]?\s*полюсн\w*", r"\1 полюсов", text, flags=re.I)


def _extra_terms(text: str, product: dict) -> set[str]:
    text = _spec_text(text)
    for _, pattern in TYPE_PATTERNS:
        text = re.sub(pattern, " ", text, flags=re.I)
    text = re.sub(r"\d+(?:[.,]\d+)?\s*(?:ка|ka|[аaвvpр]|полюс\w*)(?!\w)", " ", text, flags=re.I)
    words = set(_normalize(text).split()) - {
        "на", "с", "для", "и", "ток", "номинальный", "номинальное", "напряжение", "количество", "полюсов",
        "отключающая", "способность", "артикул", "sku", "шт", "м",
    }
    facts = " ".join([product.get("name", ""), product.get("description", ""), *(str(p["value"]) for p in product.get("properties", []))])
    return words - set(_normalize(facts).split())


def _requirements(text: str) -> tuple[dict[str, str], str | None]:
    # Диапазон и отрицание нельзя молча свести к одному найденному числу.
    if re.search(r"\d\s*[-–—/+]\s*\d|[<>≤≥±]\s*\d|(?<!\w)-\s*\d|\d\s*[pр]\s*\+\s*n", text, re.I):
        return {}, "Укажите одно точное значение каждой характеристики без диапазонов."
    requirements = {}
    # Поддерживаем распространённую запись полюсов кириллицей и через дефис.
    text = _spec_text(text)
    for field in SPEC_NAMES:
        sources = specification_sources({"name": text}, field)
        values = {source["value"] for source in sources}
        if len(values) > 1:
            return {}, f"Характеристика «{SPEC_LABELS[field]}» указана неоднозначно."
        if values:
            requirements[field] = next(iter(values))
    return requirements, None


def _candidate_names(candidates: list[dict]) -> str:
    shown = "; ".join(f"{p['sku']} — {p['name']}" for p in candidates[:6])
    return shown + (f"; ещё {len(candidates) - 6}" if len(candidates) > 6 else "")


def _find(query: str, products: list[dict]) -> tuple[list[dict], dict[str, str], str | None, str | None]:
    exact = []
    text = query
    for product in products:
        pattern = rf"(?<![\w-]){re.escape(product['sku'])}(?![\w-])"
        if re.search(pattern, query, re.I):
            exact.append(product)
            text = re.sub(pattern, " ", text, flags=re.I)
    requirements, error = _requirements(text)
    required_type = _type(text)
    type_text = text
    types = set()
    for label, pattern in TYPE_PATTERNS:
        if re.search(pattern, type_text, re.I):
            types.add(label)
            type_text = re.sub(pattern, " ", type_text, flags=re.I)
    if len(types) > 1:
        error = "В строке указаны разные типы изделий; оставьте один товар."
    if error or exact:
        return exact, requirements, required_type, error
    exact_names = [p for p in products if _normalize(p["name"]) == _normalize(query)]
    if exact_names:
        return exact_names, requirements, required_type, None
    if re.search(r"\b(?:sku|артикул)\b", text, re.I):
        return [], requirements, required_type, "Артикул не найден; проверьте его полностью, включая ведущие нули."
    if not required_type:
        return [], requirements, None, "Уточните тип изделия и характеристики либо укажите точный артикул."
    residual = _spec_text(text)
    for _, pattern in TYPE_PATTERNS:
        residual = re.sub(pattern, " ", residual, flags=re.I)
    residual = re.sub(r"\d+(?:[.,]\d+)?\s*(?:ка|ka|[аaвvpр]|полюс\w*)(?!\w)", " ", residual, flags=re.I)
    words = set(_normalize(residual).split()) - {
        "на", "с", "для", "и", "ток", "номинальный", "номинальное", "напряжение", "количество", "полюсов", "шт", "м",
    }
    if not requirements and not words:
        return [], requirements, required_type, "Одного типа изделия недостаточно; уточните характеристики или артикул."
    candidates = []
    for product in products:
        if required_type not in {source["value"] for source in _type_sources(product)}:
            continue
        if not words.issubset(set(_normalize(product["name"]).split())):
            continue
        # Конфликтный источник остаётся кандидатом для явной проверки, а не скрывается.
        if any(expected not in {s["value"] for s in specification_sources(product, field)} for field, expected in requirements.items()):
            continue
        candidates.append(product)
    return sorted(candidates, key=lambda p: (p["sku"], p["id"])), requirements, required_type, None


def match_upload_lines(lines: list[dict], products: list[dict], cart: dict) -> dict:
    """Количество в файле — итог по артикулу, а не добавка к текущей корзине."""
    found: dict[int, dict] = {}
    checks: list[dict] = []
    messages = []
    totals: dict[int, int] = {}
    references: dict[int, list[str]] = {}
    blocked = False

    def add_checks(values: list[dict]) -> None:
        for value in values:
            if value not in checks:
                checks.append(value)

    if not lines:
        return {"message": "Добавьте хотя бы одну проверенную строку спецификации.", "products": [], "checks": [], "items": None, "answer_source": "rules"}
    for line in lines:
        prefix = f"Строка {line['line_id']}: "
        if COMMAND_RE.search(line["query"]):
            blocked = True
            messages.append(prefix + "в поле товара нужны название или артикул и характеристики, без команд. Исправьте строку.")
            continue
        candidates, requirements, required_type, error = _find(line["query"], products)
        for product in candidates:
            found[product["id"]] = product
        if error or len(candidates) != 1:
            blocked = True
            add_checks([check for product in candidates for check in product_checks(product)])
            reason = error or ("подходящий товар не найден; уточните артикул и характеристики." if not candidates else "найдено несколько товаров; укажите один точный артикул: " + _candidate_names(candidates) + ".")
            messages.append(prefix + reason)
            continue
        product = candidates[0]
        query_text = re.sub(rf"(?<![\w-]){re.escape(product['sku'])}(?![\w-])", " ", line["query"], flags=re.I)
        extra_terms = _extra_terms(query_text, product)
        if extra_terms:
            blocked = True
            messages.append(prefix + "не удалось подтвердить дополнительные требования: " + ", ".join(sorted(extra_terms)) + ". Уточните строку.")
        line_checks = [check for check in product_checks(product) if check["field"] not in requirements]
        for field, expected in requirements.items():
            line_checks.append(_check(product, field, expected, specification_sources(product, field)))
        type_sources = _type_sources(product)
        if required_type or type_sources:
            expected_type = required_type or type_sources[0]["value"]
            line_checks.append(_check(product, "product_type", expected_type, type_sources))
        line_checks.append(_check(product, "unit", line["unit"], [{"field": "unit", "value": product["unit"]}]))
        add_checks(line_checks)
        mismatches = [check for check in line_checks if check["status"] != "match"]
        if mismatches:
            blocked = True
            labels = {**SPEC_LABELS, "unit": "единица измерения", "product_type": "тип изделия", "price_kzt": "цена", "min_order_quantity": "минимальная партия", "available_quantity": "остаток склада"}
            detail = "; ".join(f"{labels.get(c['field'], c['field'])}: ожидается {c['expected'] or 'подтверждённое значение'}, в каталоге {c['actual'] or 'нет данных'}" for c in mismatches)
            messages.append(prefix + f"{product['sku']} — есть противоречие или неизвестные данные ({detail}).")
        else:
            messages.append(prefix + f"{product['sku']} — {line['quantity']} {line['unit']}.")
        totals[product["id"]] = totals.get(product["id"], 0) + line["quantity"]
        references.setdefault(product["id"], []).append(str(line["line_id"]))

    for product_id, quantity in totals.items():
        product = found[product_id]
        reasons = purchase_blockers(product, quantity)
        if reasons:
            blocked = True
            messages.append(f"Строки {', '.join(references[product_id])}, {product['sku']}, всего {quantity} {product['unit']}: " + " ".join(reasons))
        for field, expected, invalid in (
            ("available_quantity", f"не менее {quantity}", lambda actual: actual < quantity),
            ("min_order_quantity", f"не более {quantity}", lambda actual: actual > quantity),
        ):
            actual = product.get(field)
            if actual is not None:
                add_checks([{"product_id": product_id, "field": field, "expected": expected, "actual": str(actual), "status": "conflict" if invalid(actual) else "match", "sources": [{"field": field, "value": str(actual)}]}])
        if len(references[product_id]) > 1:
            messages.append(f"Повторные строки {', '.join(references[product_id])} объединены: {product['sku']} — итоговое количество {quantity} {product['unit']}.")
    items = None if blocked else [{"product_id": pid, "target_quantity": quantity} for pid, quantity in totals.items()]
    if blocked:
        messages.append("Предложение для всего файла не создано. Исправьте отмеченные строки и повторите сопоставление. Корзина не изменена.")
    else:
        messages.append("Итоговое желаемое количество в корзине: " + "; ".join(f"{found[pid]['sku']} — {quantity} {found[pid]['unit']}" for pid, quantity in totals.items()) + ".")
        messages.append("Количество заменит текущее количество этих артикулов; остальные строки сохранятся. Проверены указанные требования и данные каталога; полная совместимость по неуказанным параметрам не подтверждена. Корзина изменится только после отдельного подтверждения.")
    return {"message": "\n".join(messages), "products": list(found.values()), "checks": checks, "items": items, "answer_source": "rules"}
