"""Проверки границ консультанта: противоречия, количество, аналоги и сбой LLM."""

import copy
import json
from types import SimpleNamespace

import pytest

from app.agent.consultant import consult
from app.agent.rules import analog_matches, product_checks, purchase_blockers
from app.config import ROOT
from app.seed import read_csv


@pytest.fixture
def catalog():
    stock = {(int(row["product_id"]), row["warehouse_id"]): None if row["quantity"] == "" else int(row["quantity"]) for row in read_csv(ROOT / "data/stock.csv")}
    products = []
    for source in read_csv(ROOT / "data/products.csv"):
        product = dict(source)
        for field in ("id", "price_kzt", "total_quantity", "min_order_quantity"):
            product[field] = int(product[field]) if product[field] else None
        for field in ("properties", "snapshot", "documents"):
            product[field] = json.loads(product[field])
        product.update(warehouse_id="astana", available_quantity=stock.get((product["id"], "astana")))
        products.append(product)
    return products


@pytest.fixture
def safe_product(catalog):
    product = copy.deepcopy(next(p for p in catalog if p["id"] == 515280))
    product.update(id=1001, sku="000001", available_quantity=8)
    return product


@pytest.mark.parametrize("pid,values", [(515291, {"160", "250"}), (515279, {"40", "125"})])
def test_source_conflicts_block_purchase(catalog, pid, values):
    product = next(p for p in catalog if p["id"] == pid)
    check = next(c for c in product_checks(product) if c["field"] == "current_a")
    assert check["status"] == "conflict"
    assert {s["value"] for s in check["sources"]} == values
    assert purchase_blockers(product, 1)
    assert purchase_blockers(product, 0) == []


def test_unknown_is_not_zero_or_default(catalog):
    product = next(p for p in catalog if p["id"] == 900000001)
    assert len(purchase_blockers(product, 1)) == 3
    assert all(c["status"] == "unknown" for c in product_checks(product))


def test_local_stock_not_replaced_by_total(safe_product):
    safe_product.update(available_quantity=0, total_quantity=100)
    assert purchase_blockers(safe_product, 1)


def test_sku_digits_are_never_quantity(safe_product):
    result = consult("Добавь 000001", [safe_product], {"items": []}, True)
    assert result["items"] is None
    result = consult("Добавь 2 шт 000001", [safe_product], {"items": []}, True)
    assert result["items"] == [{"product_id": 1001, "target_quantity": 2}]
    assert result["products"][0]["sku"] == "000001"


@pytest.mark.parametrize("quantity", ["1.5", "1,5", "-1", "2.0"])
def test_fractional_and_negative_quantities_not_rounded(safe_product, quantity):
    assert consult(f"Добавь {quantity} шт 000001", [safe_product], {"items": []}, True)["items"] is None


def test_current_is_not_quantity(safe_product):
    assert consult("Добавь 000001 на 50 А", [safe_product], {"items": []}, True)["items"] is None
    assert consult("Добавь 50 А 000001", [safe_product], {"items": []}, True)["items"] is None


def test_add_target_and_remove_are_explicit(safe_product):
    cart = {"items": [{"product_id": 1001, "quantity": 3}]}
    assert consult("Добавь 2 шт 000001", [safe_product], cart, True)["items"][0]["target_quantity"] == 5
    assert consult("Установи 2 шт 000001", [safe_product], cart, True)["items"][0]["target_quantity"] == 2
    assert consult("Удали 000001", [safe_product], cart, True)["items"][0]["target_quantity"] == 0
    assert consult("Не добавляй 2 шт 000001", [safe_product], cart, True)["items"] is None


def test_unknown_or_multiple_products_need_clarification(safe_product):
    another = {**safe_product, "id": 1002, "sku": "000002"}
    assert consult("Добавь 2 шт 000001 и 000002", [safe_product, another], {"items": []}, True)["items"] is None
    assert consult("Добавь 2 шт неизвестный", [safe_product], {"items": []}, True)["items"] is None


def test_analog_must_match_critical_specs_and_have_stock(safe_product):
    candidate = copy.deepcopy(safe_product)
    assert analog_matches(candidate, safe_product, 50)
    assert not analog_matches(candidate, safe_product, 160)
    candidate["properties"] = [p for p in candidate["properties"] if p["name"] != "NOMINALNOE_NAPRYAZHENIE"]
    candidate["description"] = ""
    assert not analog_matches(candidate, safe_product, 50)


def test_demo_fixture_uses_current_facts(catalog):
    product = next(p for p in catalog if p["id"] == 515291)
    product["available_quantity"] = 7
    result = consult("Покажи 200300285_", [product], {"items": []}, True)
    assert result["answer_source"] == "fixture"
    assert "7 шт" in result["message"]
    assert result["items"] is None


def test_live_missing_configuration_is_honest_fallback(monkeypatch):
    from app.llm import render_answer
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    text, source = render_answer("вопрос", "проверенные факты", "product", False)
    assert source == "rules"
    assert "локальн" in text


def test_live_exception_cannot_break_answer(monkeypatch, tmp_path):
    import openai
    import app.llm as llm
    monkeypatch.setenv("OPENAI_API_KEY", "test-only-key")
    monkeypatch.setenv("OPENAI_MODEL", "test-model")
    monkeypatch.setattr(llm, "FIXTURES_DIR", tmp_path)
    def fail(**kwargs):
        assert kwargs["timeout"] == 3
        assert kwargs["max_retries"] == 1
        raise RuntimeError("secret-error-not-for-user")
    monkeypatch.setattr(openai, "OpenAI", fail)
    text, source = llm.render_answer("вопрос", "проверенные факты", "product", False)
    assert source == "rules"
    assert "secret-error" not in text
    assert "проверенные факты" in text


def test_live_structured_output_cache_excludes_prompt(monkeypatch, tmp_path):
    import openai
    import app.llm as llm
    monkeypatch.setenv("OPENAI_API_KEY", "test-only-key")
    monkeypatch.setenv("OPENAI_MODEL", "test-model")
    monkeypatch.setattr(llm, "FIXTURES_DIR", tmp_path)
    class FakeClient:
        def __init__(self, **kwargs):
            self.responses = self
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return None
        def parse(self, **kwargs):
            assert kwargs["temperature"] == 0
            assert kwargs["text_format"] is llm.ConsultantWording
            return SimpleNamespace(output_parsed=llm.ConsultantWording(introduction=llm.INTRODUCTIONS[0]))
    monkeypatch.setattr(openai, "OpenAI", FakeClient)
    assert llm.render_answer("private-query", "проверенные факты", "product", False)[1] == "openai"
    assert llm.render_answer("private-query", "проверенные факты", "product", False)[1] == "fixture"
    cache = next((tmp_path / "cache").glob("*.json")).read_text()
    assert "private-query" not in cache
    assert "test-only-key" not in cache


@pytest.mark.parametrize("query", ["Добавь 2-3 шт 000001", "Добавь 2/3 шт 000001", "Добавь 2 м 000001", "Добавь 2 шт 000001 на 160 А и 50 А", "Добавь 2 шт 000001 на 50.5 А", "Добавь 2 шт 000001 на 1 полюс"])
def test_ambiguous_or_incompatible_purchase_needs_clarification(safe_product, query):
    assert consult(query, [safe_product], {"items": []}, True)["items"] is None


def test_live_meaning_cannot_create_purchase(monkeypatch, safe_product):
    from app.llm import QueryMeaning
    import app.agent.consultant as consultant
    monkeypatch.setattr(consultant, "interpret_query", lambda *args: QueryMeaning(intent="catalog", product_sku="000001", current_a=None))
    answer = consultant.consult("Посоветуй подходящую позицию", [safe_product], {"items": []}, False)
    assert answer["answer_source"] == "openai"
    assert answer["products"] == [safe_product]
    assert answer["items"] is None


def test_live_meaning_failure_and_forged_sku(monkeypatch, tmp_path, safe_product):
    import openai
    import app.llm as llm
    monkeypatch.setenv("OPENAI_API_KEY", "test-only-key")
    monkeypatch.setenv("OPENAI_MODEL", "test-model")
    monkeypatch.setattr(llm, "FIXTURES_DIR", tmp_path)
    class FakeClient:
        def __init__(self, **kwargs):
            self.responses = self
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return None
        def parse(self, **kwargs):
            assert kwargs["text_format"] is llm.QueryMeaning
            return SimpleNamespace(output_parsed=llm.QueryMeaning(intent="catalog", product_sku="not-in-catalog", current_a=None))
    monkeypatch.setattr(openai, "OpenAI", FakeClient)
    assert llm.interpret_query("неточный запрос", [safe_product], False) is None
    assert llm.interpret_query("неточный запрос", [safe_product], True) is None


def test_demo_analog_does_not_hide_explicit_pole_requirement(catalog):
    found = consult("Подбери 2 штуки на 160 А", catalog, {"items": []}, True)
    assert any(p["sku"] == "DEMO-160-AVAILABLE" for p in found["products"])
    assert found["answer_source"] == "fixture"
    not_found = consult("Подбери 2 штуки на 160 А 1 полюс", catalog, {"items": []}, True)
    assert not not_found["products"]
