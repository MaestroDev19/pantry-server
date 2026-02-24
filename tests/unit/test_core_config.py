"""Unit tests for app.core.config."""
from __future__ import annotations

import pytest

from app.core.config import (
    AppSettings,
    parse_int_or_none,
    parse_cors_origins,
    str_to_bool,
)


def test_str_to_bool_true_values() -> None:
    assert str_to_bool("true") is True
    assert str_to_bool("1") is True
    assert str_to_bool("yes") is True
    assert str_to_bool("on") is True


def test_str_to_bool_false_values() -> None:
    assert str_to_bool("false") is False
    assert str_to_bool("0") is False
    assert str_to_bool("no") is False
    assert str_to_bool("") is False


def test_parse_int_or_none_valid() -> None:
    assert parse_int_or_none("42") == 42
    assert parse_int_or_none("0") == 0


def test_parse_int_or_none_none_string() -> None:
    assert parse_int_or_none("none") is None
    assert parse_int_or_none("  None  ") is None


def test_parse_int_or_none_invalid() -> None:
    assert parse_int_or_none("not a number") is None


def test_parse_cors_origins_comma_separated() -> None:
    result = parse_cors_origins("a,b,c")
    assert result == ["a", "b", "c"]


def test_parse_cors_origins_list_literal() -> None:
    result = parse_cors_origins("['http://a.com', 'http://b.com']")
    assert result == ["http://a.com", "http://b.com"]


def test_gemini_temperature_within_range(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_TEMPERATURE", "1.2")
    settings = AppSettings()  # type: ignore[call-arg]
    assert 0.0 <= settings.gemini_temperature <= 2.0


def test_gemini_temperature_out_of_range_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_TEMPERATURE", "3.5")
    with pytest.raises(ValueError):
        AppSettings()  # type: ignore[call-arg]
