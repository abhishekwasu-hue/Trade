"""Q15 (Abhi FINAL) — degree-aware Daily Dow, synthetic fixtures (तारखा / किंमती code मध्ये नाहीत; फक्त रचना):
मोठा flat (A)-(B)-(C); (C) = पाच waves खाली. Minor LH तुटला तरी DOWN; protected (2) high ⇒ (4) high फक्त (3) low खाली close नंतर;
(5) मध्ये target जवळ maturity; origin close-break + उलट impulse ⇒ flip; फक्त close-break ⇒ DOWN (origin_broken)."""
import pytest

from decision3 import daily as DD
from tests.test_decision3 import daily_from_path

S = {"daily_min_sessions": 3, "daily_sigma_sessions": 3, "range_eq_sigma_d": 0.25}
#      pre  (A) (B) (1) (2)  ---------- (3) with minor swings ---------  (4)  ----- (5) -----
FLAT = [100, 60, 98, 85, 93, 82, 84.5, 84, 74, 76, 75.5, 62, 80, 70, 72, 58]   # minor bounces नंतर थांबा ⇒ confirm होतात


def _append_days(d, closes):
    """एक-दिवसाचे bars जोडा (जलद हालचाल — pivot confirm होण्याआधीच पुढचा टोक)."""
    import pandas as pd
    rows, prev, day = [], float(d["close"].iloc[-1]), d["timestamp"].iloc[-1]
    for c in closes:
        day = day + pd.offsets.BDay(1)
        rows.append({"timestamp": day, "open": prev, "high": max(prev, c) + 0.5, "low": min(prev, c) - 0.5, "close": float(c),
                     "bar_end": day + pd.Timedelta(hours=15, minutes=30)})
        prev = c
    return pd.concat([d, pd.DataFrame(rows)], ignore_index=True)


def _idx_first(st, cond):
    return next(i for i, x in enumerate(st) if cond(x))


def test_flat_c_five_waves_down_degree_aware():
    d = daily_from_path(FLAT)
    st = DD.fold(d, S)
    C = d["close"].to_numpy()
    b3 = _idx_first(st, lambda x: x.trend == "DOWN")
    assert C[b3] < 84.5 and st[b3].wave == "L3" and abs(st[b3].protected.price - 93.5) < 1e-9     # (2) high = origin
    low3 = 61.5
    adv = _idx_first(st, lambda x: x.protected is not None and abs(x.protected.price - 93.5) > 1e-9)
    assert all(x.trend == "DOWN" for x in st[b3:])                                             # (3), (4), (5) संपूर्ण DOWN
    assert C[adv] < low3 and all(C[j] >= low3 for j in range(b3, adv))                         # पहिल्या (3)-low-खालच्या close ला
    assert all(abs(x.protected.price - 93.5) < 1e-9 for x in st[b3:adv])                         # minor LH तुटले तरी (2) high
    assert abs(st[adv].protected.price - 80.5) < 1e-9 and st[adv].wave == "L5"                 # (4) high, फक्त (3) low खाली close नंतर
    corr = [x for x in st[b3:adv] if x.phase == "correction"]
    assert corr and all(x.wave == "L4" and x.corr_label for x in corr)                         # (4) = correction चालू (label सह)
    minor_lh = 76.5                                                                             # (3) आतला minor LH
    above = [j for j in range(b3, adv) if C[j] > minor_lh]
    assert above and all(st[j].trend == "DOWN" for j in above)                                 # minor LH वर close ⇒ trend बदलत नाही
    assert not any(x.mature for x in st[:adv]) and st[-1].mature                               # maturity फक्त (5) मध्ये target जवळ
    assert any(abs(t - 59.5) < 1e-9 for t in st[-1].targets)                                   # (A) low = मोठा आधीचा swing


def test_minor_daily_mode_flips_on_minor_lh_but_impulse_mode_does_not():
    d = daily_from_path(FLAT)
    old = DD.fold(d, {**S, "daily_trend_mode": "minor"})
    new = DD.fold(d, S)
    k = len(FLAT) and _idx_first(new, lambda x: x.trend == "DOWN")
    assert any(x.trend != "DOWN" for x in old[k:]) and all(x.trend == "DOWN" for x in new[k:])   # degree error दूर


def test_origin_close_break_alone_keeps_down_then_opposite_impulse_flips_up():
    path = FLAT[:12] + [96, 88, 104]                                                          # (3) नंतर origin (93.5) वर, HL, नवा HH
    d = daily_from_path(path)
    st = DD.fold(d, S)
    C = d["close"].to_numpy()
    brk = _idx_first(st, lambda x: x.phase == "origin_broken")
    assert C[brk] > 93.5 and st[brk].trend == "DOWN"                                           # फक्त close-break ⇒ trend संपत नाही
    up = _idx_first(st, lambda x: x.trend == "UP")
    assert up > brk and st[up].protected.kind == "L" and abs(st[up].protected.price - 87.5) < 1e-9   # origin = नवा HL
    assert C[up] > 96.5 and st[up].wave == "L3"


def test_new_low_after_origin_break_resumes_down_with_advanced_protected():
    path = FLAT[:12] + [95, 70, 55]                                                           # origin वर close, मग (3) low खाली
    d = daily_from_path(path)
    st = DD.fold(d, S)
    brk = _idx_first(st, lambda x: x.phase == "origin_broken")
    after = [x for x in st[brk:] if x.phase == "impulse"]
    assert after and after[-1].trend == "DOWN" and abs(after[-1].protected.price - 95.5) < 1e-9


def test_impulse_fold_truncation_invariant():
    d = daily_from_path(FLAT + [66, 50])
    full = DD.fold(d, S)
    key = lambda x: (x.trend, getattr(x.protected, "price", None), x.phase, x.wave, x.mature)   # noqa: E731
    for k in range(5, len(d)):
        part = DD.fold(d.iloc[:k], S)
        assert [key(x) for x in part] == [key(x) for x in full[:k]], k


def test_cap_helpers():
    from decision3 import method as M
    assert M.cap_min(None, "B") == "B" and M.cap_min("B", "weak") == "weak" and M.cap_min("weak", None) == "weak"
    assert M.cap_conv("A", "B") == "B" and M.cap_conv("A", "weak") == "weak" and M.cap_conv("against", "B") == "against"
    assert M.cap_conv("B", None) == "B"


def _V_with(daily_states, weekly_states):
    import pandas as pd
    from decision3 import engine as E3
    from decision3 import settings as S3
    V = E3.V22.__new__(E3.V22)
    V.s = S3.load()
    V.daily, V.weekly = daily_states, weekly_states
    V.bar_end = pd.Series([daily_states[-1].known_at + pd.Timedelta(days=1)])
    return V


def test_step1_weekly_against_caps_b_and_mature_or_origin_broken_caps_weak():
    d = daily_from_path(FLAT)
    st = DD.fold(d, S)
    wk_up = [DD.DState(0, st[0].day, st[0].known_at, "UP")]
    V = _V_with(st[:22], wk_up)                                                                # (3) impulse चालू, weekly UP
    ok, why, s1, ctx = V.step1(0)
    assert ok and ctx["trend"] == "DOWN" and ctx["cap"] == "B" and ctx["resolution"] == "daily impulse"
    V = _V_with(st, [DD.DState(0, st[0].day, st[0].known_at, "UNKNOWN")])                        # (5) mature
    ok, why, s1, ctx = V.step1(0)
    assert s1.mature and ctx["cap"] == "weak" and "mature" in " ".join(ctx["notes"])
    path = FLAT[:12] + [96]
    sb = DD.fold(daily_from_path(path), S)
    V = _V_with(sb, [DD.DState(0, sb[0].day, sb[0].known_at, "UNKNOWN")])
    ok, why, s1, ctx = V.step1(0)
    assert s1.phase == "origin_broken" and ctx["trend"] == "DOWN" and ctx["cap"] == "B" and ctx["notes"]    # Q23 (Abhi): कमाल B
    assert any("कमाल B" in x for x in ctx["notes"])                                             # cap ची नोंद ⇒ "गहाळ" यादीत येते


def test_step1_weekly_fallback_when_daily_unreadable():
    d = daily_from_path([100, 101, 100.5, 101.2])
    st = DD.fold(d, S)
    V = _V_with(st, [DD.DState(0, st[0].day, st[0].known_at, "DOWN")])
    ok, why, s1, ctx = V.step1(0)
    assert s1.trend in ("NEUTRAL", "UNKNOWN") and ok and ctx["trend"] == "DOWN" and ctx["resolution"] == "weekly fallback" \
        and ctx["cap"] == "B"


def test_weekly_from_daily_known_at_is_last_day():
    d = daily_from_path(FLAT)
    w = DD.weekly_from_daily(d)
    assert len(w) < len(d) and (w["bar_end"].diff().dropna() > __import__("pandas").Timedelta(0)).all()
    assert w["bar_end"].iloc[0] == d["bar_end"].iloc[(d["timestamp"].dt.to_period("W-FRI") == d["timestamp"].dt.to_period("W-FRI").iloc[0]).sum() - 1]


# (B) सरळ नाही: आतले swings (60 ⇒ 75 ⇒ 68 ⇒ 98). (A) low = 60 राहतो; (B) आतला low (68) maturity target नाही. flip नंतर origin =
# सर्वात उंच LH ((2) high) — सर्वात खालचा नाही (review fixture ने पकडलेला क्रम-bug).
FLAT_B_INNER = FLAT[:2] + [75, 68] + FLAT[2:]


def test_b_with_inner_swings_same_behaviour_and_maturity_targets_a_low():
    d = daily_from_path(FLAT_B_INNER)
    st = DD.fold(d, S)
    b3 = _idx_first(st, lambda x: x.trend == "DOWN")
    assert st[b3 - 1].trend == "UP"                    # Q28: data (A) पासून ⇒ (B) zigzag = UP impulse; (B) चा HL close ने तुटेपर्यंत UP
    assert all(x.trend == "DOWN" for x in st[b3:]) and abs(st[b3].protected.price - 93.5) < 1e-9   # flip ⇒ सर्वात उंच LH = (2) high
    assert abs(st[-1].protected.price - 80.5) < 1e-9 and st[-1].wave == "L5" and st[-1].mature
    assert any(abs(t - 59.5) < 1e-9 for t in st[-1].targets)                    # (A) low — leg चं टोक
    assert not any(abs(t - 67.5) < 1e-9 for t in st[-1].targets)                # (B) आतला minor low नाही


@pytest.mark.parametrize("prefix", [[120, 105, 112], [90, 110], [100, 95, 100], [60, 80, 70]])
def test_start_offset_invariance(prefix):
    """History कुठून सुरू होते त्यावर (C) ची degree / protected / wave अवलंबून नाही."""
    key = lambda x: (x.trend, getattr(x.protected, "price", None), x.phase, x.wave, x.mature)   # noqa: E731
    base = DD.fold(daily_from_path(FLAT), S)
    tail = DD.fold(daily_from_path(prefix + FLAT), S)[-len(base):]
    b3 = _idx_first(base, lambda x: x.trend == "DOWN")
    assert [key(x) for x in tail[b3:]] == [key(x) for x in base[b3:]]


def test_origin_break_with_existing_opposite_structure_flips_on_break_day():
    """(4) मध्येच HL + HH तयार, मग origin वर close ⇒ त्याच दिवशी UP; origin = तो HL (break नंतरच्या minor swing ची वाट नाही)."""
    d = daily_from_path(FLAT[:12] + [80, 72, 100, 104])
    st = DD.fold(d, S)
    C = d["close"].to_numpy()
    up = _idx_first(st, lambda x: x.trend == "UP")
    b3 = _idx_first(st, lambda x: x.trend == "DOWN")
    assert C[up] > 93.5 and all(C[j] <= 93.5 for j in range(b3, up))            # DOWN नंतरचा पहिलाच origin-वरचा close
    assert st[up].protected.kind == "L" and abs(st[up].protected.price - 71.5) < 1e-9 and st[up].wave == "L3"


def test_correction_top_confirmed_after_fast_new_low_still_advances_protected():
    """(4) टोक N bars नंतर confirm होतो; त्याआधीच (3) low खाली close झाला तरी correction हरवत नाही ⇒ protected = (4) high, wave (5)."""
    d = _append_days(daily_from_path(FLAT[:12]), [66, 72, 80, 60, 58, 57, 56])
    st = DD.fold(d, S)
    assert st[-1].trend == "DOWN" and st[-1].wave == "L5" and abs(st[-1].protected.price - 80.5) < 1e-9


def test_flip_origin_skips_hl_broken_later():
    """origin तुटल्यावर (अ) flip: नंतर किंमत ज्या HL खाली गेली तो origin होऊ शकत नाही."""
    d = _append_days(daily_from_path(FLAT[:12]), [68, 74, 80, 77, 73, 70, 77, 85, 92, 83, 75, 66, 75, 85, 94, 96])
    j = int(d["close"].to_numpy().tolist().index(92.0))
    d.loc[j, "high"] = 97.5                                                       # wick high (close origin खालीच)
    st = DD.fold(d, S)
    C = d["close"].to_numpy()
    brk = _idx_first(st, lambda x: x.phase == "origin_broken" or x.trend == "UP")
    assert C[brk] > 93.5
    assert all(not (x.trend == "UP" and abs(x.protected.price - 69.5) < 1e-9) for x in st)   # 69.5 HL नंतर 65.5 आला ⇒ origin नाही


def test_post_break_hl_must_be_inside_old_impulse_end():
    """(आ) break नंतरचा "HL" जुन्या impulse टोकाइतका / पलीकडे असेल तर तो HL नाही (double bottom) ⇒ flip नाही."""
    st = DD.fold(daily_from_path(FLAT[:12] + [96, 62, 99]), S)
    assert all(not (x.trend == "UP" and abs(x.protected.price - 61.5) < 1e-9) for x in st)
