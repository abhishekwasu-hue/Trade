"""थर v2.2 what-if अहवाल: फक्त register मधले पर्याय, default variant = defaults, summarize funnel / खुणा बरोबर."""
from decision3 import engine as E3
from decision3 import settings as S3
from scripts import v22_whatif as W
from tests.test_decision3_method import _abc_m15


def test_variants_only_register_options_and_default_first():
    assert W.VARIANTS[0][1] == {}
    for name, ov, q in W.VARIANTS[1:]:
        assert ov and q.startswith("Q")
        for k, v in ov.items():
            assert k in S3.DEFAULTS and S3.DEFAULTS[k] != v
            opts = [reg for key, reg in S3.REGISTER.items() if k in [x.strip() for x in key.split("/")]][0][1]
            assert str(v) in [x.strip() for x in str(opts).split("/")], (k, v, opts)   # पर्याय register च्या "पर्याय" स्तंभात (exact)


def test_summarize_counts_and_marks():
    V = E3.V22(_abc_m15())
    rows = V.run()
    day = rows[300]["ts"][:10]
    sm = W.summarize(rows, [day])
    assert sm["funnel"]["①"]["ok"] + sm["funnel"]["①"]["no"] == len(rows)
    assert len(sm["setups"]) == sum(1 for r in rows if r["decision"] == "setup") >= 1
    assert sm["marks"][day]["trend"] in S3.TRENDS
    assert sm["marks"][day]["setups"] or sm["marks"][day]["stop"]


def test_stop_reason_never_points_at_evidence_step_4():
    V = E3.V22(_abc_m15())
    rows = V.run()
    days = sorted({r["ts"][:10] for r in rows})
    sm = W.summarize(rows, days)
    assert all(not (v["stop"] or "").startswith("④") for v in sm["marks"].values())
