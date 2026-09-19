"""
tests/test_crypto_utils.py
--------------------------------
🎓 वापरकर्त्याने मागितलेली सुधारणा (Production-Grade — Plaintext Broker Credentials, महत्त्वाच्या
🟠 यादीतला मुद्दा) — TOKEN_ENCRYPTION_KEY सेट नसेल तर आधीसारखंच (plaintext, backward-compatible)
वर्तन, सेट असेल तर पारदर्शक encrypt/decrypt.
"""
from cryptography.fernet import Fernet

import crypto_utils

SAMPLE_KEY = Fernet.generate_key().decode()


class TestNoKeyConfigured:
    def test_encrypt_returns_plaintext_unchanged(self, monkeypatch):
        monkeypatch.delenv("TOKEN_ENCRYPTION_KEY", raising=False)
        monkeypatch.setattr(crypto_utils, "CONFIG_PATH", "/nonexistent/path.json")
        assert crypto_utils.encrypt_token("my_secret_token") == "my_secret_token"

    def test_decrypt_of_plain_string_returns_unchanged(self, monkeypatch):
        monkeypatch.delenv("TOKEN_ENCRYPTION_KEY", raising=False)
        monkeypatch.setattr(crypto_utils, "CONFIG_PATH", "/nonexistent/path.json")
        assert crypto_utils.decrypt_token("legacy_plaintext_token") == "legacy_plaintext_token"

    def test_none_passes_through(self, monkeypatch):
        monkeypatch.delenv("TOKEN_ENCRYPTION_KEY", raising=False)
        assert crypto_utils.encrypt_token(None) is None
        assert crypto_utils.decrypt_token(None) is None


class TestKeyConfiguredViaEnv:
    def test_roundtrip(self, monkeypatch):
        monkeypatch.setenv("TOKEN_ENCRYPTION_KEY", SAMPLE_KEY)
        encrypted = crypto_utils.encrypt_token("my_secret_token")
        assert encrypted != "my_secret_token"
        assert encrypted.startswith("enc:v1:")
        assert crypto_utils.decrypt_token(encrypted) == "my_secret_token"

    def test_decrypt_legacy_plaintext_still_works_after_key_added(self, monkeypatch):
        """की नंतर जोडली तरी, आधीच साठवलेले (उपसर्ग नसलेले) जुने plaintext rows वाचता यायलाच हवेत."""
        monkeypatch.setenv("TOKEN_ENCRYPTION_KEY", SAMPLE_KEY)
        assert crypto_utils.decrypt_token("old_plaintext_from_before_key_was_set") == "old_plaintext_from_before_key_was_set"

    def test_decrypt_with_wrong_key_returns_none_not_garbage(self, monkeypatch):
        monkeypatch.setenv("TOKEN_ENCRYPTION_KEY", SAMPLE_KEY)
        encrypted = crypto_utils.encrypt_token("my_secret_token")
        monkeypatch.setenv("TOKEN_ENCRYPTION_KEY", Fernet.generate_key().decode())
        assert crypto_utils.decrypt_token(encrypted) is None

    def test_invalid_key_format_falls_back_to_plaintext(self, monkeypatch):
        monkeypatch.setenv("TOKEN_ENCRYPTION_KEY", "not-a-valid-fernet-key")
        assert crypto_utils.encrypt_token("my_secret_token") == "my_secret_token"


class TestKeyConfiguredViaConfigFile:
    def test_reads_key_from_config_file_when_env_unset(self, monkeypatch, tmp_path):
        monkeypatch.delenv("TOKEN_ENCRYPTION_KEY", raising=False)
        cfg_path = tmp_path / "notification_config.json"
        cfg_path.write_text('{"token_encryption_key": "%s"}' % SAMPLE_KEY)
        monkeypatch.setattr(crypto_utils, "CONFIG_PATH", str(cfg_path))
        encrypted = crypto_utils.encrypt_token("my_secret_token")
        assert encrypted.startswith("enc:v1:")
        assert crypto_utils.decrypt_token(encrypted) == "my_secret_token"

    def test_env_var_takes_priority_over_config_file(self, monkeypatch, tmp_path):
        other_key = Fernet.generate_key().decode()
        monkeypatch.setenv("TOKEN_ENCRYPTION_KEY", SAMPLE_KEY)
        cfg_path = tmp_path / "notification_config.json"
        cfg_path.write_text('{"token_encryption_key": "%s"}' % other_key)
        monkeypatch.setattr(crypto_utils, "CONFIG_PATH", str(cfg_path))
        encrypted = crypto_utils.encrypt_token("my_secret_token")
        # SAMPLE_KEY (env) नेच encrypt झालं असेल, तर तेच decrypt करू शकेल -- other_key (file) ने नाही.
        assert crypto_utils.decrypt_token(encrypted) == "my_secret_token"
