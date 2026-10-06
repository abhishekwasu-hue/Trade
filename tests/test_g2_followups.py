"""tests/test_g2_followups.py — G2 follow-up helpers: अंतर-buckets, touches मोजणी (उगमानंतरचा overlap वगळून), पूर्ण आठवडे; network नाही."""
import numpy as np
import pandas as pd

import g2_followups as G


def test_distance_buckets():
    assert G._bucket(0.5) == "0.5–1.0%" and G._bucket(1.99) == "1.0–2.0%" and G._bucket(3.9) == "2.0–4.0%"
    assert G._bucket(0.3) is None and G._bucket(4.0) is None


def test_touches_skip_initial_overlap_and_count_visits():
    #           0    1    2    3    4    5    6    7
    h = np.array([10.5, 10.4, 13, 13, 10.6, 13, 10.2, 13])
    l = np.array([9.5, 9.8, 12, 12, 9.9, 12, 9.7, 12])
    assert G._touches(h, l, 10.0, 10.5, 0, 7) == 2                                 # bars 0–1 = उगमानंतरचा overlap, मग 4 आणि 6
    assert G._touches(h, l, 10.0, 10.5, 5, 4) == 0


def test_weekly_labels_monday_and_complete_weeks_only():
    d = pd.DataFrame({"timestamp": pd.bdate_range("2024-01-01", periods=10), "open": range(10), "high": range(1, 11), "low": range(10), "close": range(10)})
    w = G.weekly(d)
    assert list(w["timestamp"].dt.dayofweek) == [0, 0] and w["high"].iloc[0] == 5 and w["open"].iloc[1] == 5


def test_month_key():
    assert G.month_key("2021-12-31") == 202112


def test_cluster_z_wider_than_naive_for_duplicated_rows():
    import numpy as np
    rng = np.random.default_rng(0)
    a = rng.random(40) < 0.6
    b = rng.random(40) < 0.4
    a_cl, b_cl = np.arange(40), np.arange(40)
    z1 = G.cluster_z(a, a_cl, b, b_cl)
    # तेच rows 10 वेळा (एकाच cluster मध्ये) ⇒ cluster z बदलू नये (साधा z √10 पट फुगला असता)
    z10 = G.cluster_z(np.repeat(a, 10), np.repeat(a_cl, 10), np.repeat(b, 10), np.repeat(b_cl, 10))
    assert abs(z10 - z1) < 0.35 * abs(z1)
    assert np.isnan(G.cluster_z([1, 0], [1, 2], [1, 0, 1, 0, 1], [1, 2, 3, 4, 5]))
