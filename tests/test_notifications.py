"""
tests/test_notifications.py
-------------------------------
notifications.py — Telegram सूचना (credentials नसतानाही crash होऊ नये) + Heartbeat monitoring.
"""
import datetime
import os

import notifications as notif


class TestTelegramGracefulFallback:
    def test_no_credentials_returns_false_without_crashing(self, tmp_path, monkeypatch):
        monkeypatch.setattr(notif, "CONFIG_PATH", str(tmp_path / "cfg.json"))
        monkeypatch.setattr(notif, "LOG_PATH", str(tmp_path / "log.txt"))
        monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
        monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)

        result = notif.send_telegram_message("टेस्ट संदेश")
        assert result is False
        assert os.path.exists(str(tmp_path / "log.txt"))  # local log मध्ये तरी नोंद व्हायलाच हवी


class TestHeartbeat:
    def test_fresh_heartbeat_is_not_stale(self, tmp_path, monkeypatch):
        monkeypatch.setattr(notif, "HEARTBEAT_DIR", str(tmp_path))
        notif.write_heartbeat("test_script")
        assert notif.check_heartbeat_stale("test_script", max_age_minutes=30) is False

    def test_never_run_script_is_stale(self, tmp_path, monkeypatch):
        monkeypatch.setattr(notif, "HEARTBEAT_DIR", str(tmp_path))
        assert notif.check_heartbeat_stale("never_ran", max_age_minutes=30) is True

    def test_old_heartbeat_is_stale(self, tmp_path, monkeypatch):
        monkeypatch.setattr(notif, "HEARTBEAT_DIR", str(tmp_path))
        old_time = (datetime.datetime.now() - datetime.timedelta(hours=2)).isoformat()
        with open(tmp_path / "old_script.txt", "w") as f:
            f.write(old_time)
        assert notif.check_heartbeat_stale("old_script", max_age_minutes=30) is True
