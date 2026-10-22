"""Review fixes on T-1 / T-5: approval mode never promises a shadow trade; engine rows reuse engine audits only."""
import json

from vision import notify as VN
from vision import store as VS


def test_approval_mode_lines_never_promise_a_shadow_trade():
    for line in (VN.rejected_line("2026-10-22 10:00"), VN.no_reply_line("2026-10-22 10:00"), VN.drift_line("x")):
        assert "will be recorded" not in line and VN.NO_SHADOW_APPROVAL in line
    for line in (VN.rejected_line("2026-10-22 10:00", False), VN.no_reply_line("2026-10-22 10:00", None, False),
                 VN.drift_line("x", False)):
        assert VN.SHADOW_NEXT in line
    assert "comparison only" in VN.NO_SHADOW_APPROVAL


def test_engine_row_reuses_an_engine_audit(tmp_path):
    from vision import engine_audit as EA
    p = str(tmp_path / "v.db")
    base = {"bot": "srv2_momentum_reversal", "symbol": "NIFTY", "trading_mode": "PAPER", "mode": "approve", "direction": "BEARISH",
            "level": 22747.0, "setup_tf": "15M", "role": "resistance", "setup": {"tags": {"engine": True, "entry_model": "E4"}}}
    sid = VS.insert_signal({**base, "signal_ts": "2026-10-22T10:00:00"}, path=p)
    VS.finish(sid, "DONE", path=p, verdict="agree", vision_json=json.dumps({"audits": []}), prompt_version=EA.PROMPT_VERSION)
    row = {**base, "signal_ts": "2026-10-22T10:05:00", "setup_json": json.dumps(base["setup"])}
    assert VS.find_reusable(row, 30, path=p, prompt_version=EA.PROMPT_VERSION)["signal_id"] == sid
