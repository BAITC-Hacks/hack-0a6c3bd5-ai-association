"""Разбор коротких запросов и объяснение проверок без мутаций корзины."""

import json
import re

from app.agent.rules import CURRENT_RE, SPEC_LABELS, analog_matches, consistent_spec, product_checks, purchase_blockers, specification_sources
from app.config import ROOT
from app.llm import interpret_query, render_answer


def _money(value: int | None) -> str:
    return "неизвестна" if value is None else f"{value:,}".replace(",", " ") + " ₸"


def _summary(product: dict) -> str:
    local, total = product.get("available_quantity"), product.get("total_quantity")
    quantity = "нет данных" if local is None else str(local)
    overall = "нет данных" if total is None else str(total)
    minimum = product.get("min_order_quantity")
    text = f"{product['sku']} — {product['name']}. Цена: {_money(product.get('price_kzt'))}. На выбранном складе: {quantity} {product['unit']}; всего: {overall}. Минимальная партия: {minimum if minimum is not None else 'неизвестна'}."
    if product.get("snapshot", {}).get("source") == "demo_fixture":
        text += " Данные помечены как демонстрационные."
    text += " Наличие и цена относятся к снимку каталога."
    for check in product_checks(product):
        if check["status"] == "conflict":
            text += " Противоречие: " + "; ".join(f"{s['field']}: {s['value']}" for s in check["sources"]) + "."
    specs = []
    units = {"current_a": "А", "poles": "", "voltage_v": "В", "breaking_capacity_ka": "кА"}
    for field, label in SPEC_LABELS.items():
        value = consistent_spec(product, field)
        if value is not None:
            specs.append(f"{label}: {value} {units[field]}".rstrip())
    if specs:
        text += " Характеристики: " + "; ".join(specs) + "."
    certificates = [d for d in product.get("documents", []) if d.get("kind") == "certificate"]
    sheets = [d for d in product.get("documents", []) if d.get("kind") == "datasheet"]
    text += " Сертификаты: " + ("; ".join(f"{d['title']}: {d['url']}" for d in certificates) if certificates else "не предоставлены в сохранённых данных") + "."
    if sheets:
        text += " Техническая документация: " + "; ".join(f"{d['title']}: {d['url']}" for d in sheets) + "."
    return text


def _explicit_products(message: str, products: list[dict]) -> list[dict]:
    found = []
    for product in products:
        sku = re.escape(product["sku"])
        if re.search(rf"(?<![\w-]){sku}(?![\w-])", message, re.I) or re.search(rf"\b(?:id|ид|товар(?:а)?)\s*[:№#]?\s*{product['id']}\b", message, re.I):
            found.append(product)
    return found


def _quantity(message: str) -> tuple[int | None, bool]:
    """Числа артикула заранее замаскированы, ток не трактуется как количество."""
    if re.search(r"\d+\s*[/–—-]\s*\d+", message):
        return None, True
    expressions = [
        r"(?<![\w.,])(-?\d+(?:[.,]\d+)?)\s*(?:шт(?:ук[аи]?)?\.?|штук[аи]?|метр(?:а|ов)?|м)(?!\w)",
        r"(?:количеств[оеа]|кол-во)\s*[:=]?\s*(-?\d+(?:[.,]\d+)?)\b",
        r"(?:добав\w*|купи\w*|нужно|нужны|закаж\w*|полож\w*|остав\w*|установ\w*|удал\w*|убер\w*)\s+(-?\d+(?:[.,]\d+)?)(?![\w.,])(?!\s*[аa](?!\w))",
    ]
    values = [m[1] for pattern in expressions for m in re.finditer(pattern, message, re.I)]
    if any(not re.fullmatch(r"\d+", v) for v in values):
        return None, True
    numbers = {int(value) for value in values}
    return (next(iter(numbers)), False) if len(numbers) == 1 else (None, len(numbers) > 1)


def consult(message: str, products: list[dict], cart: dict, demo_mode: bool) -> dict:
    text = " ".join(message.casefold().split())
    selected = _explicit_products(message, products)
    without_sku = text
    for product in selected:
        without_sku = re.sub(re.escape(product["sku"]), " ", without_sku, flags=re.I)
        without_sku = re.sub(rf"\b(?:id|ид|товар(?:а)?)\s*[:№#]?\s*{product['id']}\b", " ", without_sku, flags=re.I)
    currents = {match[1] for match in CURRENT_RE.finditer(without_sku)}
    current = int(next(iter(currents))) if len(currents) == 1 and next(iter(currents)).isdigit() else None
    quantity, invalid_quantity = _quantity(without_sku)
    is_remove = bool(re.search(r"\b(?:удал\w*|убер\w*|очист\w*)", text))
    is_change = bool(re.search(r"\b(?:добав\w*|купи\w*|купить|закаж\w*|полож\w*|остав\w*|установ\w*|измени\w*)", text))
    is_analog = bool(re.search(r"\b(?:аналог\w*|замен\w*|подбер\w*|подоб\w*)", text))

    live_meaning = None
    tried_interpretation = False
    terms_request = bool(re.search(r"\b(?:оплат\w*|достав\w*|услови\w*)", text))
    if not selected and not (is_change or is_remove or is_analog or current or terms_request or "корзин" in text):
        tried_interpretation = not demo_mode
        live_meaning = interpret_query(message, products, demo_mode)
        if live_meaning and live_meaning.intent != "unknown":
            if live_meaning.product_sku:
                selected = [p for p in products if p["sku"] == live_meaning.product_sku]
            terms_request = live_meaning.intent == "terms"
            is_analog = live_meaning.intent == "analog"
            current = live_meaning.current_a if is_analog else current

    auto_analog = bool(len(selected) == 1 and type(selected[0].get("available_quantity")) is int and selected[0]["available_quantity"] == 0 and not is_remove)

    def reply(facts: str, found: list[dict] | None = None, items: list[dict] | None = None, kind: str = "product") -> dict:
        found = selected if found is None else found
        if live_meaning and live_meaning.intent != "unknown":
            answer, source = "Запрос интерпретирован моделью; сведения ниже проверены по каталогу.\n\n" + facts, live_meaning._answer_source
        elif tried_interpretation:
            answer, source = facts + "\n\nИспользованы локальные правила.", "rules"
        else:
            answer, source = render_answer(message, facts, kind, demo_mode)
        return {"message": answer, "products": found, "checks": [check for product in found for check in product_checks(product, current)], "items": items, "answer_source": source}

    # Отрицание и многосоставная команда требуют уточнения до любого предложения.
    if (is_remove or is_change) and re.search(r"\b(?:не|нельзя|отмен\w*)\b", text):
        return reply("Изменений не предлагаю. Уточните одной командой, что нужно сделать с корзиной.", kind="clarify")
    if currents and current is None:
        return reply("Укажите один целый номинальный ток в амперах; противоречивое или дробное требование нуждается в уточнении.", kind="clarify")
    if len(selected) > 1:
        return reply("Найдено несколько артикулов. Укажите один артикул и целое количество для одного предложения.", kind="clarify")
    if invalid_quantity and (is_change or is_remove or is_analog or auto_analog):
        return reply("Укажите одно целое неотрицательное количество. Дробное количество не округляется.", kind="clarify")
    if terms_request and not (is_change or is_remove):
        try:
            terms = json.loads((ROOT / "data/purchase_terms.json").read_text(encoding="utf-8"))
            return reply("\n".join(terms[field] for field in ("title", "payment", "delivery", "cart")), [], kind="terms")
        except (OSError, ValueError, KeyError):
            return reply("Подтверждённых условий оплаты и доставки нет. Уточните их у продавца. Локальная корзина не является заказом.", [], kind="terms")
    if "корзин" in text and not (selected or is_change or is_remove):
        count = sum(item["quantity"] for item in cart.get("items", []))
        return reply(f"В локальной корзине {count} единиц, сумма {_money(cart.get('total_kzt', 0))}. Корзина не резервирует товар. Открыть: /cart.", [], kind="cart")
    if is_remove and not selected:
        if re.search(r"(?:очист\w*\s+корзин|(?:удал\w*|убер\w*)\s+(?:всё|все))", text):
            items = [{"product_id": item["product_id"], "target_quantity": 0} for item in cart.get("items", [])]
            return reply("Подготовлено удаление всех строк. Требуется отдельное подтверждение." if items else "Корзина уже пуста.", [], items or None, "proposal")
        return reply("Укажите точный артикул строки, которую нужно удалить.", [], kind="clarify")
    if not is_remove and (is_analog or auto_analog or (current is not None and not selected)):
        reference = selected[0] if selected else None
        prefix = _summary(reference) + "\n\nНа выбранном складе товара нет. " if auto_analog else ""
        if quantity == 0:
            return reply(prefix + "Укажите положительное целое количество для подбора аналога.", kind="clarify")
        if auto_analog:
            verified = consistent_spec(reference, "current_a")
            if verified is None or (current is not None and verified != str(current)):
                return reply(prefix + "Проверенный аналог нельзя выбрать: номинальный ток исходного товара не подтверждён или не совпадает с требованием. Уточните характеристики.", kind="analog")
        if current is None and reference:
            verified = consistent_spec(reference, "current_a")
            current = int(verified) if verified and verified.isdigit() else None
        if current is None:
            return reply(prefix + "Уточните требуемый номинальный ток в амперах. При противоречии источников нельзя выбрать его за вас.", kind="clarify")
        matches = [p for p in products if (not reference or p["id"] != reference["id"]) and analog_matches(p, reference, current)]
        if reference:
            matches = [p for p in matches if p.get("warehouse_id") == reference.get("warehouse_id") and p.get("unit") == reference.get("unit")]
        requested_units = []
        if re.search(r"\d+\s*(?:м|метр(?:а|ов)?)(?!\w)", without_sku):
            requested_units.append("м")
        if re.search(r"\d+\s*(?:шт(?:ук[аи]?)?\.?|штук[аи]?)(?!\w)", without_sku):
            requested_units.append("шт")
        matches = [p for p in matches if all(p["unit"] == unit for unit in requested_units)]
        for field in ("poles", "voltage_v", "breaking_capacity_ka"):
            requested = specification_sources({"name": without_sku}, field)
            if requested:
                required_values = {source["value"] for source in requested}
                matches = [p for p in matches if {consistent_spec(p, field)} == required_values]
        if quantity is not None:
            matches = [p for p in matches if not purchase_blockers(p, quantity)]
        if not matches:
            return reply(prefix + f"Проверенного доступного аналога на {current} А с достаточными данными не найдено. Уточните характеристики или выберите другой склад.", kind="analog")
        matches.sort(key=lambda p: (p["price_kzt"], p["sku"]))
        explanation = f"Доступные аналоги. Проверены ток {current} А, тип изделия и отсутствие блокирующих противоречий."
        if reference:
            explanation += " Также совпадают число полюсов, номинальное напряжение и отключающая способность."
        else:
            explanation += " Это подбор по току; для полной совместимости уточните полюса, напряжение и отключающую способность."
        found = matches[:3]
        facts = prefix + explanation + "\n\n" + "\n\n".join(_summary(p) for p in found)
        # Подбор сам по себе показывает выбор; покупка требует однозначного артикула.
        facts += "\n\nДля предложения покупки укажите точный артикул и целое количество."
        return reply(facts, ([reference] if auto_analog else []) + found, kind="analog")
    if not selected:
        # Текстовый поиск только информирует, никогда не угадывает артикул для покупки.
        words = [w for w in re.findall(r"[а-яёa-z]{4,}", text) if w not in {"покажи", "найди", "товар", "товары", "нужен", "нужна", "есть", "цена", "наличие", "сколько"}]
        matches = [p for p in products if words and all(w in p["name"].casefold() for w in words)]
        if matches and not (is_change or is_remove):
            return reply("Найдены позиции; выберите точный артикул:\n\n" + "\n\n".join(_summary(p) for p in matches[:5]), matches[:5])
        return reply("Укажите точный артикул из каталога. Можно спросить о наличии, цене и условиях, подобрать автомат на 160 А или написать «Добавь 2 шт DEMO-160-AVAILABLE».", [], kind="clarify")
    product = selected[0]
    if is_remove or is_change:
        in_cart = next((item["quantity"] for item in cart.get("items", []) if item["product_id"] == product["id"]), 0)
        if is_remove:
            if not in_cart:
                return reply("Этой позиции нет в корзине; удалять нечего.")
            if quantity is not None and quantity > in_cart:
                return reply(f"В корзине только {in_cart} единиц. Уточните количество для удаления.", kind="clarify")
            target = 0 if quantity is None else in_cart - quantity
        else:
            if quantity is None or quantity == 0:
                return reply("Укажите положительное целое количество и единицу (шт или м). Для полного удаления напишите «Удали» и артикул.", kind="clarify")
            absolute = bool(re.search(r"\b(?:остав\w*|установ\w*|измени\w*)", text))
            target = quantity if absolute else in_cart + quantity
        blockers = purchase_blockers(product, target)
        if target:
            requested_metres = bool(re.search(r"\d+\s*(?:м|метр(?:а|ов)?)(?!\w)", without_sku))
            requested_pieces = bool(re.search(r"\d+\s*(?:шт(?:ук[аи]?)?\.?|штук[аи]?)(?!\w)", without_sku))
            if (requested_metres and product["unit"] != "м") or (requested_pieces and product["unit"] != "шт"):
                blockers.append("Указанная единица количества не соответствует единице товара.")
            for field in ("poles", "voltage_v", "breaking_capacity_ka"):
                requested = specification_sources({"name": without_sku}, field)
                if requested and {consistent_spec(product, field)} != {source["value"] for source in requested}:
                    blockers.append(f"Характеристика {SPEC_LABELS[field]} не соответствует указанному требованию или не подтверждена.")
        if current is not None and target and consistent_spec(product, "current_a") != str(current):
            blockers.append(f"Требуемый ток {current} А не подтверждён источниками этого товара.")
        if blockers:
            return reply(_summary(product) + "\n\nПредложение заблокировано: " + " ".join(blockers) + " Уточните данные или запросите проверенный аналог.")
        operation = "удаление" if target == 0 else f"итоговое количество {target} {product['unit']}"
        return reply(f"Для {product['sku']} подготовлено {operation}. Корзина изменится только после отдельного подтверждения.", items=[{"product_id": product["id"], "target_quantity": target}], kind="proposal")
    facts = _summary(product)
    if quantity is not None:
        blockers = purchase_blockers(product, quantity)
        facts += "\n\n" + (" ".join(blockers) if blockers else f"Для {quantity} {product['unit']} известного локального остатка достаточно.")
    return reply(facts)
