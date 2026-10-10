# v2.1 audit (83 मुद्दे) — #279 च्या head वर पुन्हा तपासणी

Audit `main` (#278 नंतर) वर होतं. प्रत्येक मुद्दा PR #279 च्या head वर पुन्हा तपासला. स्थिती: **fixed** = already fixed in #279 @ file:line;
**partial** = काही भाग #279 मध्ये; **open** = अजून. दुरुस्त्या थर 1 पासून क्रमाने (🔴 आधी), प्रत्येकाला bug पकडणारा unit test.

| # | थर | तीव्रता | स्थिती | #279 मध्ये / नोंद |
|---|---|---|---|---|
| 1 | 1 | 🟡 | fixed (l1) | l1: structure.py `p.confirm_bar > choch_bar` |
| 2 | 1 | 🟡 | fixed (l1) | l1: `strong_price()` |
| 3 | 1 | 🟡 | fixed (l1) | l1: `weak_level()` |
| 4 | 1 | 🟡 | fixed (l1) | l1: `rhea_settings()` (15M, ×k2/k1) |
| 5 | 1 | 🟡 | fixed (l1) | l1: register `range_band_source` + 01 §2.1 |
| 6 | 1 | 🟡 | fixed (l1) | l1: stream `order` + `pivots/dc.py` `order_fn` |
| 7 | 1 | 🟡 | fixed (l1) | l1: K_OPTIONS[2] 4/6/8 + MASTER/01 docs |
| 8 | 1 | 🟡 | fixed (l1) | l1: `k_compare_days` = 3 |
| 9 | 1 | 🟢 | fixed (l1) | l1: split for 1m first_rev |
| 10 | 1 | tests | fixed (l1) | l1: `test_audit*` (थर 1 log तक्ता) |
| 11 | 2 | 🔴 | open |  |
| 12 | 2 | 🟡 | open |  |
| 13 | 2 | 🟡 | open |  |
| 14 | 2 | 🟡 | fixed | legs2/ik2.py:87 `ctx()` — पालक unknown ⇒ स्वतःचा Dow trend + `htf_unknown`; band नसेल तरच I नाही; test `test_unknown_parent_uses_own_trend_with_htf_unknown` (`test_unknown_parent_no_I` बदलला) |
| 15 | 2 | 🟡 | fixed | legs2/ik2.py:244–259 — trend ⇄ range_alt दोन्ही बदल I_mode = पालक state चं function; register legs2/settings2.py:51 `I_mode / रद्द कारणं` |
| 16 | 2 | 🟡 | open |  |
| 17 | 2 | 🟡 | open |  |
| 18 | 2 | 🟡 | open |  |
| 19 | 2 | 🟢 | open |  |
| 20 | 2 | tests | partial | range_alt दिशा / कड-बदल / parent_flip tests जोडले; बाकी open |
| 21 | 3 | 🔴 | open |  |
| 22 | 3 | 🟡 | open |  |
| 23 | 3 | 🟡 | fixed | patterns2/fold2.py:327 `measured_move()` — (a)+(b)+(c); test `test_final_flag_measured_move` |
| 24 | 3 | 🟡 | open |  |
| 25 | 3 | 🟡 | open |  |
| 26 | 3 | 🟡 | open |  |
| 27 | 3 | 🟡 | open |  |
| 28 | 3 | 🟢 | open |  |
| 29 | 3 | tests | partial | final_flag_risk test जोडला; बाकी (12 items hand-built ctx, danger, partial_rise, resuming failed, wxy, apex, D2-I fixture) open |
| 30 | 4 | 🔴 | open |  |
| 31 | 4 | 🔴 | open |  |
| 32 | 4 | 🟡 | open |  |
| 33 | 4 | 🟡 | partial | zones2/engine.py:605 `sessions_profile()` — 5 पूर्ण sessions, कमी ⇒ NA; naked POC, score मधला profile term, rollover `bad[j]` mask अजून open |
| 34 | 4 | 🟡 | fixed | zones2/engine.py:302 `assign_ids()` — id बदलत नाही (वारसा / merge / split + lineage), तोच state पुढे; tests `test_zone_id_lineage_prune_merge_split` |
| 35 | 4 | 🟡 | open |  |
| 36 | 4 | 🟡 | open |  |
| 37 | 4 | 🟡 | open |  |
| 38 | 4 | 🟡 | open |  |
| 39 | 4 | 🟡 | open |  |
| 40 | 4 | tests | partial | merge / split id + pruning lineage + 5-session profile tests जोडले; बाकी open |
| 41 | 5 | 🔴 | open |  |
| 42 | 5 | 🟡 | open |  |
| 43 | 5 | 🟡 | open |  |
| 44 | 5 | 🟡 | open |  |
| 45 | 5 | 🟡 | open |  |
| 46 | 5 | 🟡 | open |  |
| 47 | 5 | 🟡 | open |  |
| 48 | 5 | 🟡 | open |  |
| 49 | 5 | 🟢 | fixed | trendlines2/engine.py:364 `line_class()`, :375 `prov_ok()` — 2 held + 3रा touch (close आत) + K आधार-रेघ break ≤ 6; charts भाग (anchor / held ठिपके, projection) अजून open |
| 50 | 5 | tests | partial | provisional / तीव्र वर्ग tests जोडले; बाकी open |
| 51 | 6 | 🟡 | partial | rsi2 `line_clear_strict` (engine.py:145) + register 0/1/2 केलं; रिकामं check = clear नाही (engine.py:106) आणि मूळ-कारण नोंद open |
| 52 | 6 | 🟡 | open |  |
| 53 | 6 | 🟡 | open |  |
| 54 | 6 | 🟡 | open |  |
| 55 | 6 | 🟡 | open |  |
| 56 | 6 | 🟡 | open |  |
| 57 | 6 | 🟡 | open |  |
| 58 | 6 | 🟡 | fixed | rsi2/engine.py:290 `cascade()` — (type, degree) नुसार, त्याच degree चे pivots; test `test_cascade_is_degree_wise` |
| 59 | 6 | 🟡 | open |  |
| 60 | 6 | 🟢 | open |  |
| 61 | 6 | tests | partial | cascade per degree + line_clear_strict tests जोडले; बाकी open |
| 62 | 7 | 🔴 | open |  |
| 63 | 7 | 🔴 | open |  |
| 64 | 7 | 🟡 | open |  |
| 65 | 7 | 🟡 | open |  |
| 66 | 7 | 🟡 | open |  |
| 67 | 7 | 🟡 | open |  |
| 68 | 7 | 🟡 | partial | decision2/engine.py:625 `commit_tier()` — tier 2 implement; tier 0 `load()` मध्ये नाकारणं open |
| 69 | 7 | 🟡 | partial | decision2/engine.py:363, :614 `area_touched()` — area ≤ N (6) आधी, `tl_break_n` वापरात; `break_entry_mode`, invalidation = K tentative टोक open |
| 70 | 7 | 🟡 | open |  |
| 71 | 7 | 🟡 | open |  |
| 72 | 7 | 🟡 | open |  |
| 73 | 7 | 🟡 | open |  |
| 74 | 7 | 🟡 | partial | VIX / event / macro आता फक्त size + नोंद (उत्तर 14, context.py); `vix_lo` unused, VIX 18–22 ⇒ +0.5σ strike, `missing_ext_action` register, PDF नोंद open |
| 75 | 7 | 🟡 | partial | decision2/events.yaml मध्ये expiry (NIFTY / SENSEX weekly, monthly) आणि holidays data आलं; `ext["expiries"]` आणि `expiry_choice` holidays त्याला जोडणं open |
| 76 | 7 | 🟡 | open |  |
| 77 | 7 | 🟢 | open |  |
| 78 | 7 | tests | partial | tier 2, trendline-break (area ≤ 6 सह / शिवाय), range area a/b/c, context known_at tests जोडले; बाकी open |
| 79 | MASTER | 🟡 | open |  |
| 80 | MASTER | 🟡 | open |  |
| 81 | MASTER | 🟡 | partial | `tl_break_n`, tier 2, `profile_sessions` आता वापरात; `break_entry_mode, target_mode, room_mode, premium_lo/hi, expiry_exit_time, vix_lo` open |
| 82 | MASTER | 🟡 | open |  |
| 83 | MASTER | 🟢 | open |  |

**सारांश:** fixed 6, partial 13, open 64. 🔴 सातही (#11, 21, 30, 31, 41, 62, 63) open.

**नोंद:** #13 (BOS clause ला D2 दिशा ठेवायची) — code तसाच; prompt 02 §5.1 चं वाक्य थर 2 च्या दुरुस्तीत बदलायचं. #14 चा निर्णय =
Abhi उत्तर 5, #15 = उत्तर 4 + batch 2 निर्णय 3 (parent_flip). #49 = उत्तर 10-ब (code bug नाही).
