# Test Suite — AMW A1 Trading System

या संपूर्ण संभाषणात **manually पडताळलेल्या** गोष्टींना (RSI/ATR/Supertrend Wilder's bugs, OI Signal
flip-flop fix, ३ वाजताचा Carry-Forward निर्णय, Strike Selection, इ.) कायमच्या, आपोआप चालणाऱ्या
regression tests मध्ये उतरवलं आहे — जेणेकरून **प्रत्येक भावी बदलानंतर**, हे सर्व अजूनही बरोबर आहे
याची काही सेकंदात खात्री करता येईल.

## चालवणे

```bash
pip install -r requirements-dev.txt
pytest tests/ -v
```

## रचना

| File | काय तपासतं |
|---|---|
| `test_signals.py` | RSI (Wilder's), ATR (Trailing SL), Supertrend, Candlestick, S/R |
| `test_oi_analysis.py` | OI Signal स्थिरता (flip-flop fix), Entry Gate, Put/Call Writing/Buying |
| `test_sr_dynamic.py` | Pine Script Pivot-Clustering S/R algorithm |
| `test_strategy_selection.py` | Strike Selection (Fixed + PoP-आधारित), Position Sizing |
| `test_strategies.py` | ५ orchestrator strategies (oi_pcr, ict_fvg, bb_squeeze, vwap, sr_bounce) |
| `test_trading_engine.py` | SL/Target गणित, ३ वाजताचा Carry-Forward निर्णय (खऱ्या पैशाशी थेट संबंधित) |
| `test_database.py` | DB Migrations — जुन्या DB वरही सुरक्षित |
| `test_real_data_integration.py` | खऱ्या साठवलेल्या NIFTY डेटावर — Backtest Engine, कामगिरी (performance) regression |

## महत्त्वाचं

- `test_real_data_integration.py` खऱ्या `data/nifty50_1min.parquet` फाईलवर अवलंबून आहे — ती
  उपलब्ध नसेल (उदा. वेगळ्या मशीनवर, फक्त कोड clone केला असेल) तर आपोआप **skip** होतं, अपयशी होत नाही.
- **कुठलाही नवीन bug सापडल्यास, आधी इथे त्याची चाचणी लिहा (ती अयशस्वी होताना बघा), मग दुरुस्ती करा** —
  यामुळे तोच bug पुन्हा कधीच परत येणार नाही याची खात्री मिळते (Test-Driven Bug-Fixing).
