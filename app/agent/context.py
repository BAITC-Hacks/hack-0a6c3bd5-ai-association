"""Контекст одного товара только для однозначных справочных уточнений."""

import re
from dataclasses import dataclass

from app.agent.consultant import _explicit_products


MUTATION = re.compile(r"\b(?:добав\w*|купи\w*|закаж\w*|полож\w*|остав\w*|установ\w*|измени\w*|удал\w*|убер\w*|очист\w*|подтвержд\w*)", re.I)
WAREHOUSE_NAMES = {
    "astana": r"\b(?:астан(?:а|е|у|ы)|нур[ -]?султан(?:е|а)?|astana)\b",
    "almaty": r"\b(?:алматы|алмата|алмате|almaty)\b",
    "shymkent": r"\b(?:шымкент(?:е|а)?|шимкент(?:е|а)?|shymkent)\b",
}
INFO_WORD = re.compile(r"(?:сколько|како\w*|кака\w*|каки\w*|есть|стоит|цен\w*|стоимост\w*|налич\w*|остат\w*|доступн\w*|миним\w*|парт\w*|заказ\w*|количеств\w*|сертификат\w*|документ\w*|характерист\w*|параметр\w*|номинальн\w*|ток\w*|полюс\w*|напряжен\w*|отключающ\w*|способност\w*)")
FILLER = re.compile(r"(?:а|и|ну|еще|ещё|пожалуйста|подскажи(?:те)?|скажи(?:те)?|уточни(?:те)?|покажи(?:те)?|проверь(?:те)?|расскажи(?:те)?|он|она|оно|его|ее|её|него|неё|нем|нём|нему|эт\w*|так\w*|товар\w*|о|об|у|на|в|для|по|ли|же|всего|сейчас|там|здесь|тут|склад\w*)")


@dataclass(frozen=True)
class ContextQuery:
    message: str
    warehouse_id: str
    used_context: bool = False
    clarification: str | None = None


def resolve_context(message: str, products: list[dict], warehouses: list[dict], context: dict | None, selected_warehouse_id: str) -> ContextQuery:
    selected = _explicit_products(message, products)
    text = message.casefold()
    for product in selected:
        text = re.sub(re.escape(product["sku"]), " ", text, flags=re.I)
    places = []
    for warehouse in warehouses:
        pattern = WAREHOUSE_NAMES.get(warehouse["id"], rf"\b{re.escape(warehouse['city'].casefold())}\b")
        if re.search(pattern, text):
            places.append(warehouse["id"])
            text = re.sub(pattern, " @ ", text)

    def clarify(reason: str) -> ContextQuery:
        return ContextQuery(message, selected_warehouse_id, clarification=reason)

    if len(places) > 1 or (places and re.search(r"\b(?:не|кроме|исключая)\b", message.casefold())):
        return clarify("Укажите один склад для этого вопроса: " + ", ".join(w["city"] for w in warehouses) + ".")
    known_skus = {p["sku"].casefold() for p in products}
    markers = re.findall(r"\b(?:артикул(?:а|у|ом|е)?|sku|код(?:а|у|ом|е)?)\b\s*[:№#]?\s*([\w-]+)", message.casefold())
    ids = re.findall(r"\b(?:id|ид|товар(?:а)?)\s*[:№#]?\s*(\d+)\b", message.casefold())
    codes = re.findall(r"\b[a-z0-9]+(?:[-_][a-z0-9]+)+_*\b", text)
    if any(code not in known_skus for code in markers + codes) or any(int(value) not in {p["id"] for p in products} for value in ids):
        return clarify("Указанный артикул или ID не найден в каталоге. Уточните точное обозначение товара.")
    locations = re.finditer(r"\b(?:в|во|на\s+складе)\s+(?:городе\s+)?([а-яёa-z][\w-]*)", text)
    if any(place[1] not in {"наличии", "корзине", "каталоге", "снимке", "данных", "товаре", "карточке", "описании"} for place in locations):
        return clarify("Выберите склад из каталога: " + ", ".join(w["city"] for w in warehouses) + ".")
    if MUTATION.search(message):
        if places and places[0] != selected_warehouse_id:
            city = next(w["city"] for w in warehouses if w["id"] == places[0])
            return clarify(f"Для изменения корзины выберите склад «{city}» в интерфейсе и повторите запрос с точным артикулом и количеством.")
        return ContextQuery(message, selected_warehouse_id)

    words = re.findall(r"[\w]+", text)
    followup = not selected and bool(places or any(INFO_WORD.fullmatch(word) for word in words)) and all(INFO_WORD.fullmatch(word) or FILLER.fullmatch(word) for word in words)
    product = next((p for p in products if context and p["id"] == context["product_id"]), None)
    if followup and context and product is None:
        return clarify("Предыдущий товар больше недоступен в каталоге. Укажите актуальный артикул.")
    use_context = followup and product is not None
    warehouse_id = selected_warehouse_id
    if use_context and context["selection_warehouse_id"] == selected_warehouse_id and context["warehouse_id"] in {w["id"] for w in warehouses}:
        warehouse_id = context["warehouse_id"]
    if places:
        warehouse_id = places[0]
    resolved = message + f"\nАртикул: {product['sku']}" if use_context else message
    return ContextQuery(resolved, warehouse_id, use_context)
