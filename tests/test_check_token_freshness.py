"""
tests/test_check_token_freshness.py
--------------------------------------
🎓 वापरकर्त्याने रागाने, पण अगदी बरोबर दुरुस्त केलेला मुद्दा — "मोबाईलवर Approve करूनही 401
चालूच" या तक्रारीनंतर जोडलेला `--verify-live` मोड — freshness (वेळ) ठीक असूनही token प्रत्यक्ष
Upstox कडून नाकारला जाऊ शकतो, हे वेगळेपणाने ओळखून वेगळा (🆘) alert द्यायला हवा.
"""
from unittest.mock import patch

import check_token_freshness


class TestCheckAndAlertVerifyLive:
    def test_verify_live_false_skips_live_check_keeps_old_behavior(self):
        with patch.object(check_token_freshness.cloud_db, "is_cloud_db_configured", return_value=True), \
             patch.object(check_token_freshness.cloud_db, "get_token_age_hours", return_value=2.0), \
             patch.object(check_token_freshness, "verify_token_live") as mock_verify, \
             patch.object(check_token_freshness, "send_telegram_message"):
            is_stale, msg = check_token_freshness.check_and_alert(verify_live=False)
        mock_verify.assert_not_called()
        assert is_stale is False
        assert "ताजा आहे" in msg

    def test_fresh_but_rejected_token_fires_urgent_alert(self):
        with patch.object(check_token_freshness.cloud_db, "is_cloud_db_configured", return_value=True), \
             patch.object(check_token_freshness.cloud_db, "get_token_age_hours", return_value=2.0), \
             patch.object(check_token_freshness.cloud_db, "get_latest_upstox_token", return_value="stale_token"), \
             patch.object(check_token_freshness, "verify_token_live", return_value=(False, "401 Unauthorized — ...")), \
             patch.object(check_token_freshness, "send_telegram_message") as mock_send:
            is_stale, msg = check_token_freshness.check_and_alert(verify_live=True)
        assert is_stale is True
        assert "401" in msg
        mock_send.assert_called_once()

    def test_fresh_and_valid_token_stays_quiet(self):
        with patch.object(check_token_freshness.cloud_db, "is_cloud_db_configured", return_value=True), \
             patch.object(check_token_freshness.cloud_db, "get_token_age_hours", return_value=2.0), \
             patch.object(check_token_freshness.cloud_db, "get_latest_upstox_token", return_value="good_token"), \
             patch.object(check_token_freshness, "verify_token_live", return_value=(True, "token वैध आहे (Upstox ने 200 दिला)")), \
             patch.object(check_token_freshness, "send_telegram_message") as mock_send:
            is_stale, msg = check_token_freshness.check_and_alert(verify_live=True)
        assert is_stale is False
        assert "वैधही आहे" in msg
        mock_send.assert_not_called()

    def test_stale_by_age_never_reaches_live_check(self):
        """आधीच जुना (वेळेनुसार) ठरला, तर live-check अनावश्यक — जुनंच वर्तन कायम."""
        with patch.object(check_token_freshness.cloud_db, "is_cloud_db_configured", return_value=True), \
             patch.object(check_token_freshness.cloud_db, "get_token_age_hours", return_value=30.0), \
             patch.object(check_token_freshness, "verify_token_live") as mock_verify, \
             patch.object(check_token_freshness, "send_telegram_message"):
            is_stale, msg = check_token_freshness.check_and_alert(verify_live=True, max_age_hours=20.0)
        mock_verify.assert_not_called()
        assert is_stale is True
        assert "जुना झालाय" in msg
