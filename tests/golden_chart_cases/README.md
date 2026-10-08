# Golden chart cases (V2)

Abhi ने वाचलेले charts ⇒ code ची अपेक्षा. **Public repo मध्ये फक्त अपेक्षा JSON**; candles `trade-data` (private) मध्ये
(`$TRADE_DATA/<data>`; नसेल तर test skip). सगळे cases pass झाल्याशिवाय C-V1 merge नाही.
Contaminated काळ (2026-07-01 → 2026-10-08) ⇒ फक्त regression, tuning नाही.

## नवीन case जोडणं
1. `YYYY-MM-DD_<नाव>.json` (एक chart = एक file). `data` = trade-data मधला path.
2. `window` (from / to / step_min) — प्रत्येक बंद 15M bar वर `market_state.read` आणि (असेल तर) `chart_reader.evaluate`.
3. `expect` (सगळ्या window bars वर): `trend.dir`, `trend.protected`, `impulse` (dir/from/to), `correction` (dir, labels,
   `c_top_range`, `status_in`), `active_area` (tool, slope, value_range, anchors_near), `side`. किंमती ± `tolerance_pts`.
4. `checkpoints` (ऐच्छिक): विशिष्ट वेळी `correction_labels`, `no_entry_side` (त्या बाजूची entry नको).
5. `tests/test_golden_chart_cases.py` आपोआप सगळ्या JSON वर चालतो.
