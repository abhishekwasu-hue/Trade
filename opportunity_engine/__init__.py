"""opportunity_engine — MTF Price-Action Opportunity Engine (strategy_id: `opportunity_engine`).

🎓 PR-1a (पाया): फक्त *वाचन/मोजणी* — structure (trend state machine), zones, level quality, in-memory journal.
कुठलाही order, bot किंवा DB write नाही; जुना कोड (sr_dynamic, market_zones, V3, bots) अबाधित.
कुठलाही indicator (EMA/RSI/ATR/Supertrend/VWAP/Bollinger) वापरलेला नाही — फक्त किंमत आणि `measures.py` ची मोजपट्टी.
"""
