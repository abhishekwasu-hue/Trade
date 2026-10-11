"""review7 (Abhi-पद्धत review खुणा, shadow) — एका चाचणीला एकच बाण, lookahead नाही (truncation), तारीख-मुक्त, caption मर्यादा."""
import os
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from decision2 import settings as DS
from review7 import charts as RC
from review7 import method as RM
from tests.test_legs2 import DATE_RX_I

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def _ck(t, c1=True, c2=True, c3=True, c4=(), c6=False, area="z1", d=-1):
    return {"t": t, "c1": c1, "deg": 2, "trend": "DOWN" if d < 0 else "UP", "dir": d, "c2": c2,
            "area": {"kind": "zone", "id": area, "bot": 100.0, "top": 101.0, "stars": 2, "self": False} if c2 else None, "c3": c3,
            "c4": list(c4), "c5": False, "c6": c6, "pattern": "flat/complete_resuming", "cm": {"candle": {"c": 99.0, "h": 101.5, "l": 98.0}},
            "K_extreme": 101.2, "I_end": 90.0}


def _fake_c(n=80):
    ts = pd.Series(pd.Timestamp(0) + pd.to_timedelta(np.arange(n) * 15, unit="min"))
    c = np.full(n, 99.0)
    A = {"o": c + 0.2, "h": c + 1.0, "l": c - 1.0, "c": c}
    return SimpleNamespace(ts=ts, day=ts.dt.normalize(), A=A, res={"sigma": {}}, Z=SimpleNamespace(snap={}))


def _scan(monkeypatch, seq, bars):
    by_t = {ck["t"]: ck for ck in seq}
    monkeypatch.setattr(RM, "checklist", lambda C, t, s=None: by_t.get(t) or _ck(t, c1=False, c2=False, c3=False))
    return RM.scan(_fake_c(300), bars, D={})


def test_one_arrow_per_test_full_and_partial(monkeypatch):
    seq = [_ck(t) for t in range(10, 15)] + [_ck(15, c4=("momentum",), c6=True), _ck(16, c4=("shrink",), c6=True)]
    marks = _scan(monkeypatch, seq, range(0, 40))
    assert [(m["type"], m["bar"]) for m in marks] == [("✅", 15)]                     # 16 वा bar त्याच चाचणीत ⇒ दुसरा बाण नाही
    assert marks[0]["sl"] >= 101.2 and marks[0]["rr"] is not None
    seq2 = [_ck(t) for t in range(20, 24)]                                              # ①②③ पण ④/⑥ नाही ⇒ 🟡 (पहिल्या bar ला)
    marks = _scan(monkeypatch, seq2, range(0, 40))
    assert [(m["type"], m["bar"], m["final"]) for m in marks] == [("🟡", 20, True)]
    flick = [_ck(t, area="z1" if t % 2 else "z2") for t in range(20, 28)]          # लागून दोन zones मध्ये उड्या ⇒ तरी एकच चाचणी
    assert [m["type"] for m in _scan(monkeypatch, flick, range(0, 40))] == ["🟡"]
    seq3 = [_ck(t) for t in range(20, 24)] + [_ck(t, area="z2") for t in range(30, 33)]   # खंड > gap ⇒ दुसरी चाचणी
    assert [m["area"]["id"] for m in _scan(monkeypatch, seq3, range(0, 40))] == ["z1", "z2"]
    late = [_ck(30, c4=("RSI",)), _ck(31), _ck(32, c6=True)]                        # ④ आधी, ⑥ नंतर (चाचणीत जमा) ⇒ ✅ 32 ला
    m = _scan(monkeypatch, late, range(0, 40))
    assert [(x["type"], x["bar"]) for x in m] == [("✅", 32)] and m[0]["c4"] == ["RSI"]


def test_truncation_final_marks_never_change(monkeypatch):
    rng = np.random.default_rng(7)
    seq = []
    for t in range(5, 200):
        if rng.random() < 0.45:
            seq.append(_ck(t, c4=("RSI",) if rng.random() < 0.3 else (), c6=rng.random() < 0.3, area=f"z{int(rng.integers(0, 3))}",
                           d=-1 if t < 120 else 1))
    full = _scan(monkeypatch, seq, range(0, 220))
    for cut in (30, 77, 121, 150, 199):
        part = _scan(monkeypatch, seq, range(0, cut + 1))
        fin = lambda ms: [(m["type"], m["bar"], m["area"]["id"]) for m in ms if m["final"] and m["known_at"] <= cut]  # noqa: E731
        assert fin(part) == fin(full)
        assert sum(1 for m in part if not m["final"]) <= 1                             # फक्त चालू चाचणी pending


def test_checklist_uses_only_known_bars():
    """checklist(t) ला t नंतरचा data बदलला तरी तेच उत्तर (फक्त ≤ t वाचतो)."""
    n = 60
    C = _fake_c(n)
    C.m15 = pd.DataFrame({"open": C.A["o"], "high": C.A["h"], "low": C.A["l"], "close": C.A["c"]})
    C.rr = np.full(n, 1.0)
    C.s = DS.load()
    C.A["first"] = np.array([t.hour == 0 and t.minute == 0 for t in C.ts])
    C.lg = {"settings": {"climax_rng_ratio": 2.0}}
    C.res = {"sigma": {}, "pivots": {3: []}, "segments": {}}
    st = {"trend": "DOWN", "protected": 110.0, "range": None}
    C.st = {1: {"states": [st] * n}, 2: {"states": [st] * n}}
    I = {"dir": -1, "end": SimpleNamespace(bar=10, price=95.0), "origin": SimpleNamespace(bar=2, price=110.0)}
    C.trk = {1: SimpleNamespace(state=lambda t: {"state": "K चालू", "K": {"extreme": 100.5}}, I_at=lambda t: I)}
    C.f1 = SimpleNamespace(out={})
    C.L4, C.L6 = {}, {40: {"label": "continuation trap / risk"}}                   # ④ साठी हा label नाही
    C.L5 = {}
    C.Z = SimpleNamespace(snap={t: [{"id": "z", "role": "seller", "status": "active", "bottom": 99.5, "top": 100.5, "stars": 2,
                                     "pivot_bar": 30}] for t in range(n)})
    a = RM.checklist(C, 40)
    C.A["h"][41:] += 50.0
    C.A["c"][41:] -= 30.0
    b = RM.checklist(C, 40)
    a.pop("cm", None), b.pop("cm", None)
    assert a == b and a["c1"] and a["c2"] and a["c3"] and a["area"]["self"]          # pivot_bar 30 > I_end 10 ⇒ self (खूण, वगळत नाही)
    C.Z.snap = {}
    C.L5 = {40: {"lines": [{"id": "L7", "name": "primary", "class": "trade-योग्य", "value_now": 99.9}]}}
    ln = RM.checklist(C, 40)
    assert ln["c2"] and ln["area"]["kind"] == "line" and ln["area"]["id"] == "L7" and "RSI" not in ln["c4"]


def test_caption_limit_and_labels():
    marks = [{"type": "🟡" if i % 2 else "✅", "bar": i, "ts": str(pd.Timestamp(0) + pd.Timedelta(minutes=15 * i)), "dir": -1,
              "side": "bear call", "deg": 2, "trend": "DOWN", "area": {"kind": "zone", "id": f"z{i}", "bot": 24000.0 + i, "top": 24010.0 + i,
                                                                       "stars": 2, "self": i % 3 == 0},
              "pattern": "flat/x", "c4": ["momentum"], "c5": False, "c6": True, "engine": "wait G-A", "final": True} for i in range(60)]
    pl = {"deg": 2, "trend": "DOWN", "regime": "drift", "state": "K चालू", "items": [], "invalid": "D2 संरक्षित high 24,143 तुटला"}
    cap = RC.caption("🧭 head", marks, len(marks), pl)
    assert RC.u16(cap) <= RC.MAX_CAPTION and "बाकी तक्त्यात" in cap and "रद्द" in cap
    lab = RC.label(marks[3])
    assert "D2↓" in lab and "self" in lab and "engine: wait G-A" in lab


def test_review7_source_date_free_and_no_orders():
    src = "".join(open(os.path.join(ROOT, "review7", f), encoding="utf-8").read() for f in os.listdir(os.path.join(ROOT, "review7"))
                  if f.endswith(".py"))
    assert not [ln for ln in src.splitlines() if any(rx.search(ln) for rx in DATE_RX_I)]
    for bad in ("broker", "place_order", "requests", "telegram"):
        assert f"import {bad}" not in src and f"from {bad}" not in src


@pytest.mark.parametrize("d", [1, -1])
def test_mark_levels_direction(monkeypatch, d):
    ck = _ck(5, c4=("shrink",), c6=True, d=d)
    if d > 0:
        ck["area"].update(bot=100.0, top=101.0)
        ck["cm"] = {"candle": {"c": 102.0, "h": 103.0, "l": 99.5}}
        ck["K_extreme"], ck["I_end"] = 99.0, 110.0
    m = _scan(monkeypatch, [ck], range(0, 10))[0]
    assert m["type"] == "✅" and (m["sl"] - m["entry"]) * d < 0 and (m["target"] - m["entry"]) * d > 0 and m["rr"] > 0
