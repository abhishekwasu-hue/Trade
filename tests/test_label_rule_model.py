"""DECISIONS 54 (owner rule) — the entry model's A / B label, `label_rule = model` (default; `legacy` = the old 6a set, what-if):

  • the required set = the fired model's OWN conditions (E1 / E2 / E3 / E4 a / E4 b, listed by name) ⇒ every fired entry has a label;
  • A = the model's conditions + ≥ 1 of the five confirming pieces (RSI divergence, volume growing inside, confluence, correction line
    closed through, counter channel broken), B = the model's conditions only;
  • the label never blocks: entries / invalidation / gates are byte-identical to `label_rule = legacy` except the label / evidence-list
    fields (15M decide AND the 5M trigger read5, both mirrors); `legacy` = the code before this build, byte for byte (the PIN15 digests);
  • an E4 (b) at a broken line: the line is the object, never its own confluence (NA);
  • the Vision facts / card words follow the rule.
Synthetic only (CI-safe)."""
import json

import pytest

from decision3 import engine as E3
from decision3 import entry_models as EM
from decision3 import entry_models5 as EM5
from decision3 import settings as S3
from tests.test_decision3_entry_models import AREA, BEAR, SWINGS, _bare
from tests.test_trigger_5m import PIN15, REFINE, _digest, _rows15, _v5
from tests.test_entry_models_inside_area import REF, REF_SW
from vision import card_summary as CS
from vision import engine_audit as EA

LABEL_KEYS = {"label", "evidence", "evidence_list", "confirming", "conviction", "mark", "missing"}   # the label / evidence-list fields


def strip(x):
    if isinstance(x, dict):
        return {k: strip(v) for k, v in x.items() if k not in LABEL_KEYS}
    if isinstance(x, list):
        return [strip(v) for v in x]
    return x


def dump(x):
    return json.dumps(x, sort_keys=True, default=str, ensure_ascii=False)


def check_entry(e):
    el = e["evidence_list"]
    assert el["label_rule"] == "model" and el["required"] == "present" and el["model_conditions"]
    assert all(v == "present" for v in el["model_conditions"].values())
    assert list(el["confirming"]) == list(EM.LABEL_PIECES)
    got = [k for k, v in e["confirming"].items() if v is True]
    assert e["label"] == ("A" if got else "B")                              # A = + ≥ 1 confirming piece, B = the model's conditions only
    assert el["label_pieces"] == [EM.CONF_NAME[k] for k in got]
    assert e["evidence"][0][0].endswith("the model's own conditions (required set)") and e["evidence"][0][1] == "✓"
    names = [n for n, _m in e["evidence"]]
    assert all(EM.CONF_NAME[k] in names for k in EM.LABEL_PIECES)
    assert sum(1 for n in names if " condition: " in n) == len(el["model_conditions"])
    assert el["legacy_required"] in ("present", "absent")


# ------------------------------------------------------------------------------------------------ setting
def test_label_rule_setting_registered_and_validated():
    assert S3.DEFAULTS["label_rule"] == "model" and S3.REGISTER["label_rule"][0] == "model"
    V, _lvl, _d = _bare(BEAR, SWINGS, s={"label_rule": "nope"})
    with pytest.raises(ValueError):
        EM.Reader(V).label_rule()
    for r in EM.LABEL_RULES:
        V, _lvl, _d = _bare(BEAR, SWINGS, s={"label_rule": r})
        assert EM.Reader(V).label_rule() == r


# ------------------------------------------------------------------------------------------------ never blocks: the pin
@pytest.mark.parametrize("name", sorted(PIN15))
def test_15m_legacy_is_byte_identical_and_model_changes_only_the_label_fields(name):
    leg = _rows15(name, {"label_rule": "legacy"})
    assert _digest(leg) == PIN15[name]                                      # legacy = the code before this build, byte for byte
    mod = _rows15(name, {})
    assert dump(strip(mod)) == dump(strip(leg))                             # entries / invalidation / gates identical
    for r in mod:
        for e in r.get("entries") or []:
            check_entry(e)


@pytest.fixture(scope="module", params=[False, True], ids=["bear_call", "bull_put_mirror"])
def oct12_area(request):
    from tests import oct12_fixture as F
    m15, fut, ltf = F.build(mirror=request.param)
    out = {}
    for rule in ("model", "legacy"):
        V = E3.V22(m15, s={"level_death_side": "role", "label_rule": rule, **AREA}, ltf=ltf, futures=fut)
        ts = V.levels.ts
        last = ts.dt.normalize().iloc[-1]
        out[rule] = [V.decide(t) for t in range(len(ts)) if ts.dt.normalize().iloc[t] == last]
    return out


def test_15m_every_fired_entry_has_a_label_both_mirrors(oct12_area):
    mod, leg = oct12_area["model"], oct12_area["legacy"]
    ents = [e for r in mod for e in r["entries"]]
    assert ents and dump(strip(mod)) == dump(strip(leg))
    for e in ents:
        check_entry(e)
    old = [e for r in leg for e in r["entries"]]
    assert all((e["label"] is None) == (e["evidence_list"]["required"] != "present") for e in old)   # legacy: the old 6a rule


@pytest.mark.parametrize("mirror", [False, True], ids=["bear_call", "bull_put"])
def test_5m_read5_label_both_mirrors_and_the_entry_unchanged(mirror):
    out = {}
    for rule in ("model", "legacy"):
        V, lvl, d = _v5(REF, REF_SW, (100.0, 104.0), mirror, s={**REFINE, "label_rule": rule})
        V.step2 = None
        V.rsi_divergence = lambda *a, **k: {"found": None, "na": "test"}
        V.range_structure = lambda t: None
        out[rule] = [{k: v for k, v in e.items() if not k.startswith("_")} for j in range(18, 30)
                     for e in EM5.read5(V, j, "UP" if mirror else "DOWN", [lvl])["entries"]]
    assert out["model"] and dump(strip(out["model"])) == dump(strip(out["legacy"]))
    for e in out["model"]:
        check_entry(e)
        assert any("5M" in n for n in e["evidence_list"]["model_conditions"])   # the 5M trigger is named


# ------------------------------------------------------------------------------------------------ the model's own conditions
def _R(s=None):
    V, _lvl, _d = _bare(BEAR, SWINGS, s=s)
    return EM.Reader(V)


def test_model_conditions_name_each_models_own_checks():
    R = _R({"entry_trigger_rule": "traded_inside"})
    rb = {"lo": 1.0, "hi": 2.0}
    c1 = R.model_conditions({"model": "E1", "refined": rb}, "5M")
    assert any("first 5M candle at the refined base" in c for c in c1) and any("traded into the refined 15M base" in c for c in c1)
    c2 = R.model_conditions({"model": "E2", "refined": rb}, "5M")
    assert any("commitment candle" in c and "FUT volume" in c for c in c2) and "no absorption without a handover" in c2
    c3 = R.model_conditions({"model": "E3", "refined": rb})
    assert any("LTF CHoCH by close" in c for c in c3) and "no absorption without a handover" in c3
    c4 = R.model_conditions({"model": "E4", "variant": "a", "refined": rb, "facts": {"swept": "the area's far edge"}})
    assert any("sweep beyond the area's far edge" in c for c in c4) and any("next push failed" in c for c in c4)
    c5 = R.model_conditions({"model": "E4", "variant": "b", "kind": "line", "facts": {"form": "engulf"}}, "5M")
    assert any("broken line" in c for c in c5) and any("break side" in c for c in c5) and any("(engulf)" in c for c in c5)
    assert not any("refined" in c for c in c5)
    for c in (c1, c2, c3, c4, c5):
        assert c[0].startswith("trend side")
    legacy = _R({"entry_trigger_rule": "legacy"}).model_conditions({"model": "E2", "refined": rb})
    assert not any("traded" in c or "invalidation" in c for c in legacy)    # only the checks really made
    anyside = _R({"e4b_approach_rule": "any"}).model_conditions({"model": "E4", "variant": "b", "kind": "area", "facts": {}})
    assert not any("break side" in c for c in anyside)


def _ml(R, lvl, confirm, chx):
    el = {"required": "absent", "entry_hours": "inside", "context": {}}
    return R._model_label({"model": "E4", "variant": "b", "kind": "line", "facts": {}}, "5M", el, confirm, chx, lvl, {}, {}, {}, None,
                          {})


def test_a_or_b_from_the_five_pieces_and_a_line_is_never_its_own_confluence():
    R = _R()
    none = {"volume_growing": None, "rsi_divergence": False, "confluence": True, "correction_line_closed_through": None}
    line = {"tf": "line", "confluence_line": True, "confluence": []}
    ev = _ml(R, line, none, {"present": False})
    assert ev["label"] == "B" and ev["confirming"]["confluence"] is None and ev["evidence_list"]["confirming"]["confluence"] == "NA"
    ev = _ml(R, line, none, {"present": True})
    assert ev["label"] == "A" and ev["evidence_list"]["label_pieces"] == ["counter channel broken"]
    ev = _ml(R, {"tf": "1H", "confluence": []}, none, {"present": False})
    assert ev["label"] == "A" and ev["evidence_list"]["label_pieces"] == ["confluence"]   # an area: the confluence fact as read


# ------------------------------------------------------------------------------------------------ the words
def test_label_words_follow_the_model_rule():
    ev = [["E2 — the model's own conditions (required set)", "✓"], ["RSI divergence", "✓"], ["volume growing inside", "✗"],
          ["counter channel broken", "✓"]]
    assert EA.label_words({"model": "E2", "grade": "A", "evidence": ev}) == (
        " | label A (the model's own conditions + at least one confirming piece: RSI divergence, counter channel broken)")
    assert EA.label_words({"model": "E2", "grade": "B"}) == " | label B (the model's own conditions only)"
    assert EA.label_words({"model": "E2", "grade": None}) == " | no A / B label (the legacy 6a required set reads absent)"
    assert EA.label_words({"model": None}) == ""
    assert "required set reads absent" not in EA.label_words({"model": "E1", "grade": "B"})


def test_card_reader_line_names_the_models_conditions():
    el = {"label_rule": "model", "required": "present", "required_set": "the E3 model's own conditions",
          "confirming": {"counter_channel_broken": "present", "rsi_divergence": "absent"}}
    tags = {"engine": True, "gate": {"mode": "engine", "reader": {"evidence_list": el}}}
    ln = CS.line_reader({"tags": tags})
    assert "✓ the E3 model's own conditions" in ln and "counter channel broken" in ln and "handover" not in ln
