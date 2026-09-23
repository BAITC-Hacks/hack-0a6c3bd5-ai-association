"""OCR не угадывает демофайлы и никогда не подтверждает покупку."""

import hashlib
import json
from types import SimpleNamespace

import pytest

from app import llm
from app.config import ROOT
from app.errors import ApiError


SAMPLE = ROOT / "fixtures" / "uploads" / "sample.jpg"
UNKNOWN_IMAGE = b"validated-jpeg-from-parser"


def stub_provider(monkeypatch, tmp_path, payload=None, error=None):
    calls = []
    monkeypatch.setattr(llm, "FIXTURES_DIR", tmp_path)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-never-persist")
    monkeypatch.setenv("OPENAI_MODEL", "test-vision-model")

    class FakeOpenAI:
        def __init__(self, **kwargs):
            self.options = kwargs
            self.responses = self

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def parse(self, **kwargs):
            calls.append({"options": self.options, "request": kwargs})
            if error is not None:
                raise error
            return SimpleNamespace(output_parsed=payload)

    monkeypatch.setattr("openai.OpenAI", FakeOpenAI)
    return calls


def valid_extraction(**overrides):
    return {
        "lines": [{"query": "00123_", "quantity": 2, "unit": "шт"}],
        "too_many_lines": False,
        **overrides,
    }


def assert_error(call, code):
    with pytest.raises(ApiError) as caught:
        call()
    assert caught.value.status == 422
    assert caught.value.code == code
    return caught.value


def test_demo_sample_matches_recorded_hash_and_never_calls_provider(monkeypatch):
    def forbidden(**_kwargs):
        raise AssertionError("В деморежиме не должно быть сетевого вызова")

    monkeypatch.setattr("openai.OpenAI", forbidden)
    monkeypatch.setenv("OPENAI_API_KEY", "ignored")
    monkeypatch.setenv("OPENAI_MODEL", "ignored")
    fixture = json.loads((SAMPLE.parent / "jpeg.json").read_text(encoding="utf-8"))
    content = SAMPLE.read_bytes()
    assert fixture["sha256"] == hashlib.sha256(content).hexdigest()
    result = llm.extract_image_lines(content, demo_mode=True)
    assert result["lines"] == [
        {"line_id": "1", "query": "DEMO-160-AVAILABLE", "quantity": 2, "unit": "шт"},
        {"line_id": "2", "query": "200300285_", "quantity": 1, "unit": "шт"},
    ]
    assert "записанный результат" in result["warnings"][0]
    assert "Проверьте" in result["warnings"][1]


def test_known_sample_is_safe_fallback_without_live_credentials(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    assert len(llm.extract_image_lines(SAMPLE.read_bytes(), demo_mode=False)["lines"]) == 2


def test_unknown_demo_jpeg_is_not_guessed(monkeypatch, tmp_path):
    calls = stub_provider(monkeypatch, tmp_path, payload=valid_extraction())
    assert_error(lambda: llm.extract_image_lines(UNKNOWN_IMAGE, True), "OCR_UNAVAILABLE")
    assert calls == []


@pytest.mark.parametrize("missing", ["OPENAI_API_KEY", "OPENAI_MODEL"])
def test_live_missing_configuration_does_not_call_provider(monkeypatch, tmp_path, missing):
    calls = stub_provider(monkeypatch, tmp_path, payload=valid_extraction())
    monkeypatch.delenv(missing)
    assert_error(lambda: llm.extract_image_lines(UNKNOWN_IMAGE, False), "OCR_UNAVAILABLE")
    assert calls == []


def test_live_uses_structured_image_and_caches_only_extracted_lines(monkeypatch, tmp_path):
    calls = stub_provider(monkeypatch, tmp_path, payload=valid_extraction())
    result = llm.extract_image_lines(UNKNOWN_IMAGE, False)
    assert result["lines"][0] == {"line_id": "1", "query": "00123_", "quantity": 2, "unit": "шт"}
    assert calls[0]["options"] == {"api_key": "test-key-never-persist", "timeout": 5.0, "max_retries": 1}
    request = calls[0]["request"]
    assert request["text_format"] is llm.ImageExtraction
    assert request["temperature"] == 0
    assert request["store"] is False
    assert request["model"] == "test-vision-model"
    image = request["input"][1]["content"][1]
    assert image["type"] == "input_image"
    assert image["image_url"].startswith("data:image/jpeg;base64,")
    assert image["detail"] == "high"
    cached = list((tmp_path / "cache").glob("ocr-*.json"))
    assert len(cached) == 1
    assert len(cached[0].stem.removeprefix("ocr-")) == 64
    assert json.loads(cached[0].read_text(encoding="utf-8")) == valid_extraction()
    assert llm.extract_image_lines(UNKNOWN_IMAGE, False) == result
    assert len(calls) == 1


def test_uncertain_values_stay_null_and_require_review(monkeypatch, tmp_path):
    calls = stub_provider(monkeypatch, tmp_path, payload=valid_extraction(lines=[
        {"query": "Автомат 160 А", "quantity": None, "unit": None},
    ]))
    result = llm.extract_image_lines(UNKNOWN_IMAGE, False)
    assert result["lines"][0]["quantity"] is None
    assert result["lines"][0]["unit"] is None
    assert "Строка 1" in result["warnings"][1]
    assert len(calls) == 1


def test_provider_failure_does_not_expose_message(monkeypatch, tmp_path):
    stub_provider(monkeypatch, tmp_path, error=RuntimeError("secret provider request and API key"))
    error = assert_error(lambda: llm.extract_image_lines(UNKNOWN_IMAGE, False), "OCR_UNAVAILABLE")
    assert "secret" not in error.message
    assert error.details == {}
    assert not (tmp_path / "cache").exists()


def test_empty_result_is_honest_parse_failure(monkeypatch, tmp_path):
    stub_provider(monkeypatch, tmp_path, payload=valid_extraction(lines=[]))
    assert_error(lambda: llm.extract_image_lines(UNKNOWN_IMAGE, False), "DOCUMENT_PARSE_FAILED")
    assert not (tmp_path / "cache").exists()


@pytest.mark.parametrize("payload", [
    valid_extraction(too_many_lines=True),
    valid_extraction(lines=[{"query": "Автомат", "quantity": 1, "unit": "шт"}] * 51),
])
def test_over_limit_is_not_silently_truncated(monkeypatch, tmp_path, payload):
    stub_provider(monkeypatch, tmp_path, payload=payload)
    assert_error(lambda: llm.extract_image_lines(UNKNOWN_IMAGE, False), "DOCUMENT_LIMIT_EXCEEDED")
    assert not (tmp_path / "cache").exists()


@pytest.mark.parametrize("quantity", [0, -1, 1.5, True, "2"])
def test_invalid_provider_quantity_is_not_coerced(monkeypatch, tmp_path, quantity):
    stub_provider(monkeypatch, tmp_path, payload=valid_extraction(lines=[
        {"query": "Автомат", "quantity": quantity, "unit": "шт"},
    ]))
    assert_error(lambda: llm.extract_image_lines(UNKNOWN_IMAGE, False), "OCR_UNAVAILABLE")


def test_corrupt_cache_is_ignored(monkeypatch, tmp_path):
    calls = stub_provider(monkeypatch, tmp_path, payload=valid_extraction())
    llm.extract_image_lines(UNKNOWN_IMAGE, False)
    cache = next((tmp_path / "cache").glob("ocr-*.json"))
    cache.write_text("not json", encoding="utf-8")
    assert llm.extract_image_lines(UNKNOWN_IMAGE, False)["lines"][0]["quantity"] == 2
    assert len(calls) == 2


def test_cache_write_failure_does_not_break_extraction(monkeypatch, tmp_path):
    stub_provider(monkeypatch, tmp_path, payload=valid_extraction())
    (tmp_path / "cache").write_text("not a directory", encoding="utf-8")
    assert llm.extract_image_lines(UNKNOWN_IMAGE, False)["lines"][0]["quantity"] == 2


def test_invalid_recorded_fixture_is_not_trusted(monkeypatch, tmp_path):
    calls = stub_provider(monkeypatch, tmp_path, payload=valid_extraction())
    (tmp_path / "uploads").mkdir()
    fixture = {
        "version": 1,
        "sha256": hashlib.sha256(UNKNOWN_IMAGE).hexdigest(),
        "extraction": valid_extraction(lines=[{"query": "Автомат", "quantity": -1, "unit": "шт"}]),
    }
    (tmp_path / "uploads" / "jpeg.json").write_text(json.dumps(fixture), encoding="utf-8")
    assert_error(lambda: llm.extract_image_lines(UNKNOWN_IMAGE, True), "OCR_UNAVAILABLE")
    assert calls == []
