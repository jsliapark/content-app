"""Settings / env parsing."""

import json
import os

import pytest

from content_app.config import Settings, get_settings, parse_brandvoice_args


@pytest.fixture(autouse=True)
def clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_brandvoice_args_comma_separated(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "a")
    monkeypatch.setenv("OPENAI_API_KEY", "b")
    monkeypatch.setenv("BRANDVOICE_ARGS", " brandvoice-mcp , --verbose ")
    get_settings.cache_clear()
    assert parse_brandvoice_args(get_settings().brandvoice_args) == [
        "brandvoice-mcp",
        "--verbose",
    ]


def test_brandvoice_args_json_array(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "a")
    monkeypatch.setenv("OPENAI_API_KEY", "b")
    monkeypatch.setenv("BRANDVOICE_ARGS", json.dumps(["brandvoice-mcp==0.1.1"]))
    get_settings.cache_clear()
    assert parse_brandvoice_args(get_settings().brandvoice_args) == ["brandvoice-mcp==0.1.1"]


def test_optional_ints_and_strings_from_env(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "a")
    monkeypatch.setenv("OPENAI_API_KEY", "b")
    monkeypatch.setenv("MAX_RETRIES", "5")
    monkeypatch.setenv("ALIGNMENT_THRESHOLD", "82")
    monkeypatch.setenv("DEFAULT_MODEL", "claude-3-haiku-20240307")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///custom.db")
    monkeypatch.setenv("LOG_LEVEL", "debug")
    monkeypatch.setenv("BRANDVOICE_COMMAND", "npx")
    get_settings.cache_clear()
    s = get_settings()
    assert s.max_retries == 5
    assert s.alignment_threshold == 82
    assert s.default_model == "claude-3-haiku-20240307"
    assert s.database_url == "sqlite:///custom.db"
    assert s.log_level == "debug"
    assert s.brandvoice_command == "npx"


def test_brandvoice_args_json_must_be_array(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "a")
    monkeypatch.setenv("OPENAI_API_KEY", "b")
    monkeypatch.setenv("BRANDVOICE_ARGS", '{"x":1}')
    with pytest.raises(ValueError, match="array, not an object"):
        Settings()
