"""simple_core — Abhi 2026-10-08: "analysis paralysis" थांबवा. Engine चं काम फक्त (1) entry चा area शोधणं, (2) confirmation (commitment
candle) झाल्यावर ENTRY SIGNAL. SL / target / R:R / instrument / strike / lots / expiry = execution settings (dashboard), engine मध्ये नाहीत.

  engine.py     trend (market_state) + area (chart_reader.zones) + pause + commitment ⇒ signal (ref_levels फक्त माहिती)
  execution.py  signal + execution settings ⇒ trade plan / "settings निवडलेले नाहीत" ; simulate (backtest / review तुलना)
  settings.py   engine चे detection आकडे (MR च्या पटीत) + execution settings store (प्रति profile, hash)
जड chart_reader (gap, Elliott, volume, divergence, patterns, VIX, 23 बाबी, गुण) = shadow / context — entry ठरवत नाही.
"""
