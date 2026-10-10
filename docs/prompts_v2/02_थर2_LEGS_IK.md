# थर 2: Leg चा स्वभाव, Impulse (I) आणि Correction (K) (v2.1, 2026-10-09)

> Master लागू. **थर 1 ला ✔ + k निवड झाल्यावरच.** व्याप्ती: labels / I / K फक्त **D1 आणि D2** वर; D3 legs ला फक्त R.
>
> ## का
> Audit: impulse = "अलीकडचा ≥ 4 MR leg + एक मोठी candle"; correction = "पुढचे तीन pivots" ⇒ pullback "wave 3", नवा high "B".
>
> **संशोधनाचे धडे (`price_action/02_impulse_correction_momentum.md`, `impulse_vs_pullback.md`):**
> 1. Impulse = वेगवान, एकतर्फी, overlap नसलेला, टोकाजवळ closes, gaps/FVG; correction = संथ, overlapping, मिश्र, अरुंद, (बहुधा) कमी volume. (Brooks spike/channel; Wyckoff; Elliott; ICT.)
> 2. **स्वभाव ≠ भूमिका** (zigzag चे A, C आवेगी पण correction).
> 3. सगळी मापं सापेक्ष; U-shape (NIFTY futures 09:15–10:00 सगळ्यात volatile, 11:00–12:00 कमी) ⇒ **slot-normalise**.
> 4. "Pullback volume कमी" = doctrine (Abhi चा नियम ⇒ पुरावा, gate नाही). **KB K2 (NIFTY):** 57% pullbacks impulse इतके वेगवान, 62% displacement ⇒ वेग / displacement निर्णायक नाहीत.
> 5. CHoCH एकटा फसतो; I_strict_HL + displacement + LH/BOS.
> 6. **C > B नेहमी** ⇒ "मोठा leg = नवा impulse" म्हटलं तर entry च्या वेळी दिशा उलटते ⇒ **I sticky**, आणि I ची दिशा **D2 trend शी सुसंगत** हवी.

---

## 1. Leg आणि मापं (confirmed leg चं माप P_j च्या `known_at` ला, गोठलेलं; चालू leg प्रत्येक candle)
- Leg = लागोपाठचे confirmed pivots; bars (P_(j−1), P_j]; चालू leg = शेवटचा pivot → tentative.
- **Candle features** (gap नेहमी वगळून; Master व्याख्या): body%, CLV, **CLV_d** (d-दिशेने: up CLV, down 1−CLV), **wick_opp_d**, overlap (session-जोडी वगळ), **overlap3** (आधीच्या 3 candles च्या union शी), rng_ratio, trend_candle(d), displacement (Master), climax_candle(d), FVG(d).
- **Gap खूण:** leg मध्ये overnight gap ≥ 0.5 σ ⇒ `gap_in_leg` (थर 1 चं `gap_leg_theta` वेगळं); सगळी मापं नेहमीच gap वगळून.
- **Leg features:** size (σ), bars, speed, **ER** (close-to-close; overnight पद वजा; **clamp [0,1]; denominator 0 ⇒ NA**; start = P_(j−1) candle चा close), trend_candle%, max_run, avg_overlap, avg CLV_d, n_FVG, n_disp, wave_vol, wave_RVOL, effort_result = wave_vol / size.
- सध्याचे `market_state.overlap_ratio` / `chart_reader.volume.rel_vol` हीच व्याख्या असतील तर import; नसतील तर फरक register मध्ये.

## 2. भूमिका R
R = |leg| / |मागचा उलट leg| (wicks). R > 1 प्रबळ (P_(j−2) wick ने ओलांडलं; plain-close BOS वेगळी घटना), R ≤ 1 परतावा, थर 1 `eq` ⇒ बरोबरी, पहिला ⇒ अज्ञात.

## 3. स्वभाव C, V
- **C** = ER (↑), overlap (1−pct), body% (↑), दिशा-candles % (↑) यांच्या percentile ची सरासरी, त्याच degree च्या मागच्या 40 confirmed legs मध्ये (**स्वतः वगळून**, warmup / 1–2-bar / gap_leg_theta वगळून, `known_at` क्रम, holdout नाही, बरोबरी सरासरी rank). ≥ 0.6 आवेगी / ≤ 0.4 सुधारात्मक / मध्ये तटस्थ. 10–39 ⇒ warmup; < 10 ⇒ NA. 1–2 bars ⇒ तटस्थ.
- **V** = leg RVOL / मागच्या उलट leg RVOL; ≥ 1.2 / ≤ 0.83; data नाही / > ½ bars unreliable / कोणत्याही leg ला < 3 reliable bars ⇒ तटस्थ.
- **C×V मत:** आवेगी×{आवेगी,तटस्थ} ⇒ आवेगी; तटस्थ×आवेगी ⇒ आवेगी(कमकुवत); आरसा सुधारात्मक; उलट ⇒ तटस्थ.
- **नोंद (score नाही):** speed, n_disp, n_FVG, max_run, CLV; आतली रचना (खालच्या degree चे sub-legs; 5 ⇒ Elliott ✓ / overlap).

## 4. Label तक्ता (प्रबळ×आवेगी = आवेग; प्रबळ×तटस्थ = आवेग(कमकुवत); प्रबळ×सुधारात्मक = विरोध-1; परतावा×आवेगी = विरोध-2; परतावा×तटस्थ = सुधार(कमकुवत); परतावा×सुधारात्मक = सुधार; बरोबरी / अज्ञात तसेच). विरोध = निवड नाही (जांभळी). कारणांची ओळ.

## 5. I आणि K (D1; D2 आरसा-संदर्भ)
### 5.1 I शोधणं (I नाही / रद्द)
1. मागे जाताना पहिला confirmed D1 leg: label आवेग / आवेग(कमकुवत) **आणि दिशा = D2 trend state (थर 1)** किंवा त्या leg ने D1 plain-close BOS केला. C_na leg वरून I ⇒ `I_weak_basis`.
   - **`I_mode` = प्रत्येक candle ला D2 trend state चं function (Abhi, प्रश्न 4):** D2 RANGE ⇒ `range_alt` mode: I = range च्या जवळच्या कडेपासून दूर जाणारा शेवटचा D1 leg (कड = थर 1 RANGE पट्टा; **जवळची कड = t च्या close ला**, `range_alt_edge_from = close`; close मध्यापासून ±1 σ_1H मध्ये ⇒ कड नाही ⇒ I नाही; कड बदलली ⇒ I पुन्हा शोध), K = त्या कडेकडे येणारी चाल; `I_mode = range_alt` खूण; थर 3/4 त्यावर नेहमीसारखे चालतात; थर 7 §3a त्याच fields वापरतो. D2 RANGE तुटून trend ⇒ §5.1 ने trend I पुन्हा.
   - **D2 unknown / warm-up (प्रश्न 5):** D2 स्वतःचा Dow trend (RANGE ⇒ range_alt) + `htf_unknown` खूण; पालक माहीत झाला ⇒ I पुन्हा शोध.
2. **I_origin** (I वर): I_end आधीचा, I_end ≥ असलेला शेवटचा D1 high आणि I_end यांच्यामधला सगळ्यात खालचा D1 low; **असा high नसेल तर origin = D2 strong low (थर 1) आणि `origin_bounded`** (`origin_open` नाही).
3. **गुणवत्ता (नोंद):** spike (trend_candle% ≥ 0.7, max_run ≥ 5, avg_overlap ≤ 0.4, ER ≥ 0.6, FVG ≥ 1) / channel; `climax` (I च्या शेवटच्या 3 candles मध्ये climax_candle(d)); `SOT_trend` (I चे शेवटचे 3 with-trend pushes चे gains घटत).

### 5.2 I sticky: बदल फक्त
- I-दिशेने confirmed D1 leg ज्याचा pivot I_end पलीकडे **आणि त्या leg मध्ये close I_end पलीकडे** ⇒ I_end सरकतो (आवृत्ती यादी); फक्त wick ⇒ `sweep_of_I_end`, I_end तोच.
- **रद्द:** (a) I_origin चा real break (Master पातळी 2; frame = masked 15M, start = I_end bar, side = origin ची, `end = decision_bar`; settings dict नाव + register); (b) थर 1 ची दोन-पायरी reversal D1 वर पूर्ण (I-विरुद्ध); (c) **`parent_flip`** — D2 trend state थेट I-विरुद्ध trend_up / trend_down ⇒ trend-mode I रद्द, नव्या दिशेने §5.1 शोध (Abhi, batch 2 निर्णय 3; I_mode = D2 state चं function).
- Sticky फक्त trend-mode I च्या identity (I_end / I_origin) ला; mode बदल (trend ⇄ range_alt) त्याच्या बाहेर.
- K मधले आवेग legs I ची जागा घेत नाहीत.

### 5.3 K अवस्था (running D1 leg वर)
- **impulse चालू:** running D1 leg I-दिशेने, tentative I_end पलीकडे.
- **K सुरू झाला असावा:** tentative extreme नंतर D0 उलट pivot confirmed, D1 नाही; % परत.
- **K चालू:** ≥ 1 confirmed D1 leg I_end नंतर. **`I_strict_HL`** = I_end आधीचा D1 HL (I_end देणारा; Master). **खोली (मुख्य):** K टोक / शेवटचा with-trend D1 leg (I_strict_HL → I_end); दुय्यम: / पूर्ण I. वेळ = K bars / त्या leg bars. K चा C vs I चा C; `pullback_quiet` (K RVOL ≤ 1.2 आणि < I) / `pullback_heavy` (≥ 1.5).
- **counter-impulse** नोंद (K मध्ये I-विरुद्ध आवेग leg). **CHoCH strict** = close `I_strict_HL` खाली + `displacement` (Master) ⇒ `choch_disp` ⇒ "reversal candidate", नसेल तर "deep pullback".
- **Mechanical flags (थर 3 ला; resuming थर 3 ठरवतो):** `cisd` (ICT: K च्या शेवटच्या counter-close run च्या पहिल्या candle च्या open मधून I-दिशेने **body** close; 15M candles / D0 running leg वर; truncation-safe) आणि `last_leg_start_broken` (close K च्या running D0 leg च्या सुरुवातीपलीकडे).
- निर्णय नाही.

## 6. अंदाज register
| आकडा | default | पर्याय | वर्ग |
|---|---|---|---|
| C सीमा | 0.6 / 0.4 | 0.55/0.45, 0.65/0.35 | अंदाज |
| V सीमा | 1.2 / 0.83 | 1.15/0.87, 1.3/0.77 | NexusFi practitioner |
| baseline legs | 40 (min 10) | 30/40/60 | अंदाज |
| gap_in_leg | 0.5 σ | 0.3/0.5/0.8 | अंदाज |
| spike (0.7, 5, 0.4, 0.6) | — | ±20% | Brooks/NexusFi |
| quiet / heavy | 1.2 / 1.5 | ±0.1 | NexusFi |
| breaks.py settings | सध्याचे | ±1 पायरी | code (MR ≠ σ नोंद) |

## 7. मोजमाप (वर्णन)
Labels वाटप; C वितरण प्रबळ vs परतावा (KB K2); spike/channel/climax/SOT_trend; gap / NA / unreliable; sensitivity; I बदल / रद्द (कारणानुसार); K अवस्था; quiet/heavy %.

## 8. Charts
15M: legs (आवेग जाड / सुधार तुटक / विरोध जांभळी / फिकी), लेबल, I कंस + गुणवत्ता, K फिका, CHoCH ⚑, cisd ◇, RVOL panel. 1H D2. Box: I, K (अवस्था, खोली मुख्य/दुय्यम, वेळ, volume). महत्त्वाचे क्षण: I बदल / रद्द / CHoCH strict / cisd. Telegram "🧭 LEG CHECK".

## 9. Tests
Truncation (confirmed, चालू); bars; features (CLV_d, wick_opp_d, overlap3, climax_candle, ER clamp/NA, gap वगळ, session जोडी, H=L); baseline (स्वतः वगळ, 1–2-bar/gap वगळ, holdout, NA, degrees वेगळे, बरोबरी); V (< 3 bars तटस्थ; rollover; expiry field); C×V 9; labels; spike/channel/climax/SOT_trend; I: दिशा D2 शी, RANGE ⇒ none, origin_bounded, C_na ⇒ I_weak_basis, zigzag C ने I बदलत नाही, close-beyond ने I_end सरकतो / wick ⇒ sweep_of_I_end, रद्द दोन्ही कारणं, breaks.py settings नावाने + end; K अवस्था (running leg); खोली मुख्य/दुय्यम; cisd / last_leg_start_broken truncation; D2; register; caption / output / replay / shadow / तारीख.

## 10. क्रम
`legs2/` ⇒ suite ⇒ review ⇒ run ⇒ push ⇒ PDF ⇒ Telegram ⇒ Abhi ✔ ⇒ थर 3.
