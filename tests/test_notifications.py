"""
tests/test_notifications.py
--------------------------------
Telegram credentials चा शोध-क्रम: environment -> data/notification_config.json (दोन्ही keys असतील तरच) -> प्रोजेक्टची .env.
"""
import json

import pytest

import notifications as n


@pytest.fixture(autouse=True)
def _clean(monkeypatch, tmp_path):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    monkeypatch.setattr(n, "CONFIG_PATH", str(tmp_path / "missing_config.json"))
    monkeypatch.setattr(n, "ENV_FILE_PATH", str(tmp_path / "missing.env"))
    monkeypatch.setattr(n, "LOG_PATH", str(tmp_path / "log.txt"))


def test_nothing_configured_returns_none():
    assert n._load_telegram_credentials() == (None, None)


def test_environment_wins(monkeypatch, tmp_path):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "envtok")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "111")
    (tmp_path / "x.env").write_text("TELEGRAM_BOT_TOKEN=filetok\nTELEGRAM_CHAT_ID=222\n")
    monkeypatch.setattr(n, "ENV_FILE_PATH", str(tmp_path / "x.env"))
    assert n._load_telegram_credentials() == ("envtok", "111")


def test_config_json_used_when_it_has_both_keys(monkeypatch, tmp_path):
    cfg = tmp_path / "cfg.json"
    cfg.write_text(json.dumps({"telegram_bot_token": "cfgtok", "telegram_chat_id": "333"}))
    monkeypatch.setattr(n, "CONFIG_PATH", str(cfg))
    (tmp_path / "x.env").write_text("TELEGRAM_BOT_TOKEN=filetok\nTELEGRAM_CHAT_ID=222\n")
    monkeypatch.setattr(n, "ENV_FILE_PATH", str(tmp_path / "x.env"))
    assert n._load_telegram_credentials() == ("cfgtok", "333")


def test_config_json_without_telegram_keys_falls_back_to_env_file(monkeypatch, tmp_path):
    """VPS ची खरी स्थिती -- config.json आहे पण त्यात telegram keys नाहीत (आधी KeyError/None) -> .env वापरली जाते."""
    cfg = tmp_path / "cfg.json"
    cfg.write_text(json.dumps({"something_else": 1}))
    monkeypatch.setattr(n, "CONFIG_PATH", str(cfg))
    (tmp_path / "x.env").write_text("# comment\nSUPABASE_DB_URL=postgres://x\nexport TELEGRAM_BOT_TOKEN=\"filetok\"\nTELEGRAM_CHAT_ID='222'\n")
    monkeypatch.setattr(n, "ENV_FILE_PATH", str(tmp_path / "x.env"))
    assert n._load_telegram_credentials() == ("filetok", "222")


def test_corrupt_config_json_falls_back_to_env_file(monkeypatch, tmp_path):
    cfg = tmp_path / "cfg.json"
    cfg.write_text("{not json")
    monkeypatch.setattr(n, "CONFIG_PATH", str(cfg))
    (tmp_path / "x.env").write_text("TELEGRAM_BOT_TOKEN=a\nTELEGRAM_CHAT_ID=b\n")
    monkeypatch.setattr(n, "ENV_FILE_PATH", str(tmp_path / "x.env"))
    assert n._load_telegram_credentials() == ("a", "b")


def test_env_file_with_only_one_key_returns_partial_so_send_is_skipped(monkeypatch, tmp_path):
    (tmp_path / "x.env").write_text("TELEGRAM_BOT_TOKEN=a\n")
    monkeypatch.setattr(n, "ENV_FILE_PATH", str(tmp_path / "x.env"))
    token, chat = n._load_telegram_credentials()
    assert token == "a" and chat is None


def test_send_uses_env_file_credentials(monkeypatch, tmp_path):
    (tmp_path / "x.env").write_text("TELEGRAM_BOT_TOKEN=tok123\nTELEGRAM_CHAT_ID=999\n")
    monkeypatch.setattr(n, "ENV_FILE_PATH", str(tmp_path / "x.env"))
    calls = {}

    class Resp:
        status_code = 200

    def fake_post(url, json=None, timeout=None):
        calls["url"], calls["json"] = url, json
        return Resp()

    monkeypatch.setattr(n.requests, "post", fake_post)
    assert n.send_telegram_message("hello") is True
    assert calls["url"].endswith("/bottok123/sendMessage") and calls["json"]["chat_id"] == "999"


def test_send_without_credentials_does_not_post(monkeypatch):
    monkeypatch.setattr(n.requests, "post", lambda *a, **k: pytest.fail("should not post"))
    assert n.send_telegram_message("hello") is False
