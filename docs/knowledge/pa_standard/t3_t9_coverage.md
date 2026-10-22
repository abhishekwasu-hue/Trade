# T3 (channels per timeframe) and T9 (evidence wiring) — report first, then the build

Order: owner-orders README row 1 ("Price Action Standard … done (T3 channels per TF, T9 evidence wiring open)", #362). Checked
against CLAUDE.md, DECISIONS 3, 5, 6, 7, 9, 14, 26, 28, 35, the method doc §8 and KB K6 (Method Pack 3 "Trendlines and channels").

## 1. What the two tracks require

Neither track has its own document in this folder (T1, T2, T4–T8 do). What they are, from the repo itself:

* **T3 — §2E lines / channels, per timeframe.** The coverage map has a row per PA concept except §2E (METHOD_MAP rows "PA T1 … T8";
  `t4_chart_patterns.md`: "§2E belongs to the lines / channels track"). The lines and channels were built inside the entry-models work
  (7ef548f, "lines on both sides and both directions + channels", Abhi 21 Oct) — but only on the 15M chart's two swing degrees. The
  standard reads every concept per timeframe in one vocabulary (§1, `t1_mtf_state.md`: W, D, 1H, 15M, 5M, each from its own swings);
  KB K6 / Method Pack 3: a trendline runs through *the structure's own swings*, a channel is its parallel through the opposite extreme,
  broken = a close beyond + a swing beyond (K6.5). So T3 = the same line / channel reader run on each timeframe's own swings and bars.
* **T9 — evidence wiring.** Every track document defers the same item to T9: `t1_mtf_state.md` ("Track T9 wires its output into the
  evidence list"), `t2_area_types.md`, `t4_chart_patterns.md` (retest levels — hook), `t5_candle_forms.md` ("wiring into the evidence
  list is T9"), `t6_rsi_hidden_divergence.md` ("Track T9 adds it to the evidence list"), `t7_range_edges.md` (`armable` hook, "wiring =
  T9"), `t8_output_objects.md` (`evidence` wording on each object; objects into the gate tags). CLAUDE.md: "Evidence is listed and never
  blocks." So T9 = each track's facts listed on each entry, display only.

## 2. What exists

| piece | where | what it does today |
|---|---|---|
| lines (4 families) | `decision3/trendline.channel_lines(V, t, degree)` | rising / falling line of highs / lows on swings of one swings2 degree of the **15M bars**; anchors, touches by reactions, K6.5 break |
| channels | `trendline.channels(V, t, degree)` | each line + its parallel; state inside / outside / broken / retest |
| degrees read | `trendline.line_degrees` = (`level_degree` D2, D1); `TF_OF_DEGREE` = {2: "1H", 1: "15M"} | two degrees of the 15M chart only — **no Daily, no Weekly channel** |
| row | `engine.decide` row `channel_lines`, `channels` | the two degrees above, every bar |
| E4 (b) objects | `entry_models.Reader.broken_objects` | broken lines / parallels of the trend degree (D2) only |
| per-entry evidence | `entry_models.Reader.evidence` ⇒ entry `evidence` / `evidence_list` / `channel_evidence` | the 6a marks (required set, 4 confirming pieces) + one channel mark (counter channel broken, 1H / 15M) |
| PA track facts | `mtf_state.evidence`, `legs_compare.evidence`, `area_types` (`evidence` per area), `confluence_pa` (`label` per area), `liquidity_pa` (`evidence` per extreme / inducement), `patterns_pa` (`evidence`), `candle_forms` (`evidence`), `volume_read` (`evidence`), `rsi_hidden` (`statements`), `range_edges.range_state` | each track writes its own evidence words — **none of them reaches an entry** |
| Chart Reading Report | `decision3/chart_reading.collect` | reads the same tracks per symbol (not per entry); OFF until Abhi approves the sample |
| live path | `paper/engine_entry.entry_tags` (`entry_evidence`) ⇒ `vision/card_summary.model_lines` ("📋 evidence") | shows the 6a marks only |

## 3. The exact gaps

T3
1. No channel on the Daily / Weekly timeframes (their swings exist: `mtf_state.swings`, the Daily / Weekly fold).
2. The two degrees of the 15M chart are the 1H and 15M structure (as `mtf_state` reads them) — correct; the timeframe word comes from a
   fixed map (kept: it is the existing approved reading, no change).
3. No 5M channel — **provisional (OPEN_QUESTIONS T3-1):** the 5M swing is the LTF-CHoCH trigger definition (a high above its left
   neighbour), not a structure swing; a line on it would read wiggles (method §3 "small wiggles inside a leg are not swings"). 5M stays
   without lines.

T9
4. No PA track fact on an entry (T1 MTF state + leg nature, T2 area base / departure + confluence + liquidity / inducement, T3 channels per
   TF, T4 patterns, T5 candle forms + volume reads, T6 hidden divergence, T7 range state / range edge).
5. The live card / payload carries only the 6a marks.

Not gaps for this change (they would change entries, or are another track's display item) — left open, listed in OPEN_QUESTIONS:
6. `patterns_pa.retest_levels` as E4 (b) objects (`PATTERN_HOOK`) and `range_edges.armable` as armed areas: both ADD trade locations ⇒
   new entries. That is a reading change, not evidence; it needs Abhi's word and a replay. Not wired.
7. Daily / Weekly broken channel lines as E4 (b) objects: the same — not wired (E4 (b) keeps the trend degree's lines).
8. T8 objects into the gate tags (`chart_objects`, default off) and the PA list in the Vision prompt (Vision input and its paid tokens
   unchanged): not wired.

## 4. The build (smallest, reuse first)

* `trendline.py`: the line / channel reader split into a core that takes any timeframe's bars + its own swings (the 15M-chart path calls
  it exactly as before — rows byte-identical), plus `channels_by_tf(V, t)` = {W, D, 1H, 15M}: 1H / 15M = the existing degrees; D / W =
  the same core on the Daily / Weekly candles known at t with the swings `mtf_state.swings` reads (no new swing detector, no number).
  The row gets `channels_htf` (D / W, compact) next to the existing `channels`.
* `decision3/pa_evidence.py` (new): `for_entry(V, t, d, area, visit_start)` = one list of rows {track, concept, tf, text, src} copied
  from each track's own evidence words; each track read with bars ≤ t; one track failing gives an NA row, never stops the rest; selection
  is by identity / comparison only (the entry's own area id, overlap with the entry band, the reader's own "nearest" flag, the channel
  price is in now). Volume rows say "FUT volume missing" when the FUT volume is missing (never spot).
* `entry_models.read`: every entry gets `pa_evidence` (the 6a `evidence`, its label and every decision field untouched).
* Live display: `paper/engine_entry` tag `entry_pa_evidence`; the card adds one "🧩 PA evidence" line (display only).
* No setting, no number, no rule, no gate. Pinned by a test: entries / decisions identical with the wiring replaced by an empty list.
