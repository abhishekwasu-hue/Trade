"""Review charts ⇒ Telegram (VPS वरून): manifest parse, sent log ⇒ duplicate नाही, reply parser (✔ / ✘ / missed), token नसताना स्पष्ट error."""
import json
import os

import pytest

from backtest_review import telegram as RT

def _png():
    import io
    from PIL import Image
    b = io.BytesIO()
    Image.new("RGB", (40, 30), (20, 30, 40)).save(b, "PNG")
    return b.getvalue()


PNG = _png()


def run_dir(tmp_path, n=2):
    d = tmp_path / "review" / "k10" / "run1"
    items = []
    for i in range(n):
        day = f"2026-08-0{i + 1}"
        (d / day).mkdir(parents=True)
        for f in ("day_1h.png", "day_15m.png"):
            (d / day / f).write_bytes(PNG)
        items.append({"n": i + 1, "date": day, "item": f"day:{day}", "reading": f"Trend: up · area B{i}",
                      "files": [f"{day}/day_1h.png", f"{day}/day_15m.png"]})
    (d / "manifest.json").write_text(json.dumps({"run_id": "k10_run1", "title": "K-10", "items": items}, ensure_ascii=False),
                                     encoding="utf-8")
    return str(d)


class FakeTG:
    def __init__(self, errors=()):
        self.calls, self.mid, self.errors = [], 100, list(errors)

    def __call__(self, method, data, files=None, timeout=20):
        self.calls.append((method, data, files))
        if self.errors:
            return self.errors.pop(0)
        n = len(json.loads(data["media"])) if method == "sendMediaGroup" else 1
        res = [{"message_id": self.mid + i} for i in range(n)]
        self.mid += n
        return {"ok": True, "result": res if method == "sendMediaGroup" else res[0]}


def creds():
    return "TOKEN-SECRET-123", "160201826"


def test_manifest_parse_and_caption(tmp_path):
    m = RT.load_manifest(run_dir(tmp_path))
    assert m["run_id"] == "k10_run1" and len(m["items"]) == 2
    c = RT.caption(m, m["items"][1])
    assert c.startswith("🔎 K-10 दिवस 2/2 · 2026-08-02") and "Trend: up" in c and len(c) <= 1024


def test_manifest_missing_file_is_clear_error(tmp_path):
    d = run_dir(tmp_path)
    os.remove(os.path.join(d, "2026-08-01", "day_1h.png"))
    with pytest.raises(ValueError, match="files नाहीत"):
        RT.load_manifest(d)


def test_sent_log_prevents_duplicates(tmp_path):
    d, log = run_dir(tmp_path), str(tmp_path / "sent.json")
    tg = FakeTG()
    out = RT.send_run(d, call=tg, creds=creds, sent=log, sleep=lambda s: None)
    assert out == {"sent": 2, "skipped": 0, "failed": []}
    assert [c[0] for c in tg.calls] == ["sendMediaGroup", "sendMediaGroup"]
    media = json.loads(tg.calls[0][1]["media"])
    assert media[0]["caption"].startswith("🔎 K-10 दिवस 1/2") and "caption" not in media[1]
    out2 = RT.send_run(d, call=tg, creds=creds, sent=log, sleep=lambda s: None)
    assert out2 == {"sent": 0, "skipped": 2, "failed": []} and len(tg.calls) == 2
    assert RT.lookup_message(101, log)["date"] == "2026-08-01"


def test_rejected_file_is_retried_smaller(tmp_path):
    tg = FakeTG([{"ok": False, "error_code": 400, "description": "PHOTO_INVALID_DIMENSIONS"}])
    out = RT.send_run(run_dir(tmp_path, 1), call=tg, creds=creds, sent=str(tmp_path / "s.json"), sleep=lambda s: None)
    assert out["sent"] == 1 and len(tg.calls) == 2
    assert tg.calls[1][2]["img0"][1] != PNG                                 # दुसऱ्यांदा लहान केलेली image


def test_429_waits_retry_after_and_resends_same_bytes(tmp_path):
    waits = []
    tg = FakeTG([{"ok": False, "error_code": 429, "parameters": {"retry_after": 7}}])
    out = RT.send_run(run_dir(tmp_path, 1), call=tg, creds=creds, sent=str(tmp_path / "s.json"), sleep=waits.append)
    assert out["sent"] == 1 and waits[0] == 8 and tg.calls[1][2]["img0"][1] == PNG


def test_network_error_is_not_resent(tmp_path):
    tg = FakeTG([None])
    out = RT.send_run(run_dir(tmp_path, 1), call=tg, creds=creds, sent=str(tmp_path / "s.json"), sleep=lambda s: None)
    assert out["sent"] == 0 and len(tg.calls) == 1 and "network" in out["failed"][0][1]


def test_manifest_file_count_and_corrupt_sent_log(tmp_path):
    d = run_dir(tmp_path, 1)
    m = json.load(open(os.path.join(d, "manifest.json"), encoding="utf-8"))
    m["items"][0]["files"] = []
    json.dump(m, open(os.path.join(d, "manifest.json"), "w", encoding="utf-8"))
    with pytest.raises(ValueError, match="files 1"):
        RT.load_manifest(d)
    bad = tmp_path / "bad.json"
    bad.write_text("{oops", encoding="utf-8")
    with pytest.raises(ValueError, match="sent log"):
        RT.send_run(run_dir(tmp_path / "y", 1), call=FakeTG(), creds=creds, sent=str(bad), sleep=lambda s: None)
    assert RT.load_sent(str(bad)) == {}                                      # listener lenient


def test_no_token_clear_error_without_printing_token(tmp_path, capsys):
    with pytest.raises(RT.NoCredentials) as e:
        RT.send_run(run_dir(tmp_path), call=FakeTG(), creds=lambda: (None, None), sent=str(tmp_path / "s.json"), sleep=lambda s: None)
    assert "TELEGRAM_BOT_TOKEN" in str(e.value)
    tg = FakeTG()
    RT.send_run(run_dir(tmp_path / "x"), call=tg, creds=creds, sent=str(tmp_path / "s2.json"), sleep=lambda s: None)
    out = capsys.readouterr()
    assert "TOKEN-SECRET-123" not in out.out + out.err


@pytest.mark.parametrize("text,verdict,reason,missed", [
    ("✔", "OK", "", None),
    ("✔️", "OK", "", None),
    ("✅ trend बरोबर", "OK", "trend बरोबर", None),
    ("✘ area चुकला", "WRONG", "area चुकला", None),
    ("❌ pause नाही", "WRONG", "pause नाही", None),
    ("? नक्की नाही", "UNCLEAR", "नक्की नाही", None),
    ("सुटलेला trade 13:30 bear", "WRONG", "सुटलेला trade 13:30 bear", {"time": "13:30", "side": "bear_call"}),
    ("✘ सुटलेला trade 9:45 bull, PDL flip", "WRONG", "सुटलेला trade 9:45 bull, PDL flip", {"time": "09:45", "side": "bull_put"}),
    ("✘ short covering नाही, सुटलेला 13:30 bull", "WRONG", "short covering नाही, सुटलेला 13:30 bull", {"time": "13:30", "side": "bull_put"}),
])
def test_reply_parser(text, verdict, reason, missed):
    p = RT.parse_reply(text)
    assert p == {"verdict": verdict, "reason": reason, "missed": missed}


def test_reply_parser_ignores_other_text():
    assert RT.parse_reply("hello") is None and RT.parse_reply("") is None


@pytest.mark.parametrize("text", ["सुटलेला trade 13:30", "सुटलेला trade 1:30 bear", "सुटलेला trade bear"])
def test_unclear_missed_trade_is_not_saved(text):
    assert "error" in RT.parse_reply(text)


def test_handle_reply_saves_only_for_approver_and_known_message(tmp_path):
    d, log = run_dir(tmp_path), str(tmp_path / "sent.json")
    RT.send_run(d, call=FakeTG(), creds=creds, sent=log, sleep=lambda s: None)
    saved, sent = [], []
    save = lambda *a: saved.append(a) or True                                # noqa: E731
    auth = lambda f, c: str(f["id"]) == "160201826" and str(c["id"]) == "160201826"   # noqa: E731
    msg = {"text": "✘ area चुकला", "from": {"id": 160201826}, "chat": {"id": 160201826}, "reply_to_message": {"message_id": 102}}
    assert RT.handle_reply(msg, auth, save=save, send=sent.append, sent=log) == (True, "saved")
    assert saved == [("day:2026-08-02", "2026-08-02", "day", "WRONG", "area चुकला", None, "k10_run1")]
    assert sent and sent[-1].startswith("नोंद ✓ 2026-08-02")
    other = dict(msg, **{"from": {"id": 999}, "chat": {"id": 999}})
    assert RT.handle_reply(other, auth, save=save, send=sent.append, sent=log) == (False, "unauthorized")
    stray = dict(msg, reply_to_message={"message_id": 5})
    assert RT.handle_reply(stray, auth, save=save, send=sent.append, sent=log) == (False, "not_review")
    bad = dict(msg, text="सुटलेला trade 13:30")
    assert RT.handle_reply(bad, auth, save=save, send=sent.append, sent=log) == (False, "unparsed") and sent[-1].startswith("❓")
    assert len(saved) == 1


def test_listener_routes_replies(monkeypatch, tmp_path):
    from vision import telegram_bot as TB
    seen = []
    monkeypatch.setattr(TB.TG, "get_updates", lambda off, timeout: [{"update_id": 7, "message": {"text": "✔", "reply_to_message":
                                                                                                    {"message_id": 1}}}])
    monkeypatch.setattr(TB.VS, "kv_set", lambda *a, **k: None)
    import backtest_review.telegram as RT2
    monkeypatch.setattr(RT2, "handle_reply", lambda m, auth, send=None: seen.append(m["text"]) or (True, "saved"))
    assert TB.poll_once(0, path=str(tmp_path / "v.db"), timeout=0) == 8 and seen == ["✔"]
