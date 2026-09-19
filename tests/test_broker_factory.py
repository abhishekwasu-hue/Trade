"""
tests/test_broker_factory.py
--------------------------------
🎓 वापरकर्त्याने मागितलेली सुधारणा ("प्रत्येक strategy साठी वापरकर्ता स्वतः एक किंवा अनेक broker
accounts निवडू शकेल") — broker_factory.get_adapters_for_accounts() साठी टेस्ट्स — get_all_active_adapters()
सारखंच, पण "सर्व सक्रिय" ऐवजी फक्त caller ने दिलेल्या account_ids साठीच.
"""
from unittest.mock import patch

import pandas as pd

import broker_factory


def _accounts_df():
    return pd.DataFrame([
        {"account_id": "ACC_A", "broker_type": "upstox", "nickname": "A", "is_active": True, "lot_multiplier": 1.0},
        {"account_id": "ACC_B", "broker_type": "shoonya", "nickname": "B", "is_active": False, "lot_multiplier": 2.0},
    ])


class TestGetAdaptersForAccounts:
    def test_empty_account_ids_returns_empty(self):
        adapters, errors = broker_factory.get_adapters_for_accounts([])
        assert adapters == []
        assert errors == []

    def test_none_account_ids_returns_empty(self):
        adapters, errors = broker_factory.get_adapters_for_accounts(None)
        assert adapters == []
        assert errors == []

    def test_resolves_only_selected_account(self):
        with patch.object(broker_factory.cloud_db, "get_all_broker_accounts", return_value=_accounts_df()), \
             patch.object(broker_factory.cloud_db, "get_effective_upstox_token", return_value="fake_token"):
            adapters, errors = broker_factory.get_adapters_for_accounts(["ACC_A"])
        assert len(adapters) == 1
        adapter, lot_multiplier = adapters[0]
        assert adapter.get_account_id() == "ACC_A"
        assert lot_multiplier == 1.0
        assert errors == []

    def test_includes_inactive_account_if_explicitly_selected(self):
        """वापरकर्त्याने स्पष्टपणे निवडलेला असेल, तर is_active=False असला तरीही वगळला जाऊ नये."""
        with patch.object(broker_factory.cloud_db, "get_all_broker_accounts", return_value=_accounts_df()), \
             patch.object(broker_factory.cloud_db, "get_effective_upstox_token", return_value="fake_token"):
            adapters, errors = broker_factory.get_adapters_for_accounts(["ACC_B"])
        assert len(adapters) == 1
        assert adapters[0][0].get_account_id() == "ACC_B"

    def test_unknown_account_id_reported_as_error(self):
        with patch.object(broker_factory.cloud_db, "get_all_broker_accounts", return_value=_accounts_df()):
            adapters, errors = broker_factory.get_adapters_for_accounts(["ACC_NOT_REGISTERED"])
        assert adapters == []
        assert len(errors) == 1
        assert "ACC_NOT_REGISTERED" in errors[0]

    def test_no_accounts_registered_at_all_returns_error(self):
        with patch.object(broker_factory.cloud_db, "get_all_broker_accounts", return_value=None):
            adapters, errors = broker_factory.get_adapters_for_accounts(["ACC_A"])
        assert adapters == []
        assert len(errors) == 1

    def test_multiple_selected_accounts_partial_success(self):
        """एक account token न मिळाल्याने अयशस्वी झाला तरी दुसरा यशस्वी व्हायलाच हवा."""
        def _token_side_effect(_token, account_id=None):
            return "fake_token" if account_id == "ACC_A" else None
        with patch.object(broker_factory.cloud_db, "get_all_broker_accounts", return_value=_accounts_df()), \
             patch.object(broker_factory.cloud_db, "get_effective_upstox_token", side_effect=_token_side_effect):
            adapters, errors = broker_factory.get_adapters_for_accounts(["ACC_A", "ACC_B"])
        assert len(adapters) == 1
        assert adapters[0][0].get_account_id() == "ACC_A"
        assert len(errors) == 1
