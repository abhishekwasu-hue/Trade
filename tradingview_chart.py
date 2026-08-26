"""
TradingView-style chart — त्यांच्याच open-source 'Lightweight Charts' library वापरून, Streamlit HTML
component म्हणून embed केलेला. Plotly ऐवजी — खरा TradingView candle-रेंडरिंग, smooth pan/zoom.

🎓 वापरकर्त्याशी चर्चा करून ठरवलेली मोठी सुधारणा:
  - अधिक घट्ट (deeper) dark theme, grid पूर्णपणे बंद
  - Drawing Tools: Trendline, Horizontal Line, Fibonacci Retracement, Rectangle, Measure Tool
  - Crosshair वर OHLC माहिती-पेटी
  - EMA20/EMA50 काढले — त्याऐवजी 1-Day व 1-Hour Supertrend overlay (डीफॉल्ट, period=10, multiplier=3)
  - मागच्या 2-3 candles पेक्षा मोठे Hammer/Shooting Star मार्कर्सने ठळक
"""
import json
import os
import pandas as pd

_LIB_PATH = os.path.join(os.path.dirname(__file__), "lib", "lightweight-charts.js")

# 🎓 घट्ट (deeper) dark theme रंग — आधीच्या #131722 पेक्षा जास्त गडद, TradingView च्या Pro थीमसारखा
BG_COLOR = "#0a0d13"
PANEL_COLOR = "#0d1017"
BORDER_COLOR = "#1c2129"
TEXT_COLOR = "#c9cdd6"


def _load_library_js():
    """
    Library चा संपूर्ण JS कोड file मधून वाचून थेट HTML मध्ये embed करण्यासाठी — CDN वर अवलंबून
    राहण्याऐवजी (CDN अनुपलब्ध/धीमं असेल तर chart दिसणारच नाही, याउलट embed केल्यास तसं होत नाही).
    """
    with open(_LIB_PATH, encoding="utf-8") as f:
        return f.read()


def _to_unix_time(ts):
    """pandas Timestamp -> Unix seconds (lightweight-charts ला हेच हवं)."""
    return int(pd.Timestamp(ts).timestamp())


def build_lightweight_chart_html(
    df, symbol="NIFTY", timeframe_label="15M",
    supertrend_1d_series=None, supertrend_1d_direction=None,
    supertrend_1h_series=None, supertrend_1h_direction=None,
    supertrend_15m_series=None, supertrend_15m_direction=None,
    rsi_series=None, sr_levels=None, pattern_markers=None, height=650,
):
    """
    संपूर्ण TradingView Lightweight Charts HTML/JS पान तयार करणे — candlestick + volume (वेगळा pane) +
    1D/1H Supertrend (मुख्य किंमत chart वर, डीफॉल्ट — EMA20/EMA50 ऐवजी) + RSI (वेगळा pane) +
    Support/Resistance (आडव्या रेषा) + Hammer/Shooting-Star मार्कर्स (मागच्या 2-3 candles पेक्षा मोठे
    असतील तेच) + Drawing Toolbar (Trendline, Horizontal Line, Fibonacci, Rectangle, Measure).

    supertrend_*_series/direction: pandas Series, df च्याच timestamps शी आधीच अलाइन केलेले (no-lookahead
    merge_asof ने) — इथे फक्त रेंडर केले जातात, अलाइनमेंट page_dashboard.py मध्ये होते.
    """
    if df is None or df.empty:
        return "<div style='color:#888;padding:20px;'>चार्टसाठी डेटा उपलब्ध नाही.</div>"

    candle_data = [
        {
            "time": _to_unix_time(row.timestamp), "open": round(float(row.open), 2),
            "high": round(float(row.high), 2), "low": round(float(row.low), 2), "close": round(float(row.close), 2),
        }
        for row in df.itertuples()
    ]
    volume_data = [
        {
            "time": _to_unix_time(row.timestamp),
            "value": float(row.volume) if hasattr(row, "volume") and pd.notna(row.volume) else 0,
            "color": "#089981" if row.close >= row.open else "#F23645",
        }
        for row in df.itertuples()
    ]

    def _build_supertrend_segments(line_series, dir_series):
        """
        🎓 वापरकर्त्याशी चर्चा करून दुरुस्त केलं — Supertrend ला दिशेनुसार (bullish=हिरवा/bearish=लाल)
        दोन वेगळ्या series मध्ये विभागावं लागतं (lightweight-charts मध्ये एकाच रेषेचा रंग मध्येच बदलता
        येत नाही), पण आधी दिशा-बदलाच्या क्षणी दोन्ही भाग एकमेकांना स्पर्श करत नव्हते — रेषा तुटलेली/वेगळी
        दिसायची. आता दिशा बदलण्याच्या नेमक्या बिंदूवर तोच बिंदू दोन्ही भागांत जोडला जातो (सांधा) —
        त्यामुळे दृश्यतः एकच सलग रेषा दिसते, फक्त रंग बदलतो.
        """
        bullish, bearish = [], []
        if line_series is None or dir_series is None or line_series.empty:
            return bullish, bearish
        values = line_series.reset_index(drop=True)
        dirs = dir_series.reset_index(drop=True)
        times = df["timestamp"].reset_index(drop=True)
        n = len(values)
        for i in range(n):
            if pd.isna(values.iloc[i]) or pd.isna(dirs.iloc[i]):
                continue
            point = {"time": _to_unix_time(times.iloc[i]), "value": round(float(values.iloc[i]), 2)}
            current_dir = int(dirs.iloc[i])
            (bullish if current_dir == 1 else bearish).append(point)
            # पुढचा बिंदू दिशा बदलणार असेल, तर आत्ताचाच बिंदू त्या नवीन दिशेतही जोडणे (सांधा)
            if i + 1 < n and not pd.isna(dirs.iloc[i + 1]) and int(dirs.iloc[i + 1]) != current_dir:
                (bullish if int(dirs.iloc[i + 1]) == 1 else bearish).append(point)
        return bullish, bearish

    st1d_bull, st1d_bear = _build_supertrend_segments(supertrend_1d_series, supertrend_1d_direction)
    st1h_bull, st1h_bear = _build_supertrend_segments(supertrend_1h_series, supertrend_1h_direction)
    st15m_bull, st15m_bear = _build_supertrend_segments(supertrend_15m_series, supertrend_15m_direction)

    rsi_data = []
    if rsi_series is not None and not rsi_series.empty:
        rsi_data = [
            {"time": _to_unix_time(t), "value": round(float(v), 2)}
            for t, v in zip(df["timestamp"], rsi_series) if pd.notna(v)
        ]

    # 🎓 Hammer/Shooting-Star मार्कर्स (मागच्या 2-3 candles पेक्षा मोठे असतील तेच) — lightweight-charts
    # च्या setMarkers() ला हवा तो फॉरमॅट: वर बाणाने Shooting Star (bearish), खाली बाणाने Hammer (bullish)
    marker_data = []
    if pattern_markers:
        for idx, pattern in pattern_markers:
            if idx >= len(df):
                continue
            row = df.iloc[idx]
            if pattern == "HAMMER":
                marker_data.append({
                    "time": _to_unix_time(row["timestamp"]), "position": "belowBar",
                    "color": "#089981", "shape": "arrowUp", "text": "H",
                })
            else:  # SHOOTING_STAR
                marker_data.append({
                    "time": _to_unix_time(row["timestamp"]), "position": "aboveBar",
                    "color": "#F23645", "shape": "arrowDown", "text": "SS",
                })

    sr_lines_js = []
    sr_table_rows = []  # खाली दाखवायच्या table साठी — [type, level, touches]
    if sr_levels:
        # 🎓 touches (किती वेळा त्या level ला किंमतीने स्पर्श केला) जितके जास्त, तितकी high-probability
        # पातळी — रेषा जितकी जाड (bold) आणि रंग जितका ठळक (गडद/संपृक्त), तितकी जास्त प्रभावी पातळी
        def _width_and_opacity(touches):
            if touches >= 4:
                return 4, 1.0
            elif touches == 3:
                return 3, 0.9
            elif touches == 2:
                return 2, 0.75
            else:
                return 1, 0.55

        for item in sr_levels.get("resistance", [])[:5]:
            lvl = item.get("level") if isinstance(item, dict) else item
            touches = item.get("touches", 1) if isinstance(item, dict) else 1
            if lvl is not None:
                width, opacity = _width_and_opacity(touches)
                sr_lines_js.append({
                    "price": round(float(lvl), 2), "color": f"rgba(242,54,69,{opacity})",
                    "title": f"R ({touches}x)", "width": width,
                })
                sr_table_rows.append({"type": "Resistance", "level": round(float(lvl), 2), "touches": touches})
        for item in sr_levels.get("support", [])[:5]:
            lvl = item.get("level") if isinstance(item, dict) else item
            touches = item.get("touches", 1) if isinstance(item, dict) else 1
            if lvl is not None:
                width, opacity = _width_and_opacity(touches)
                sr_lines_js.append({
                    "price": round(float(lvl), 2), "color": f"rgba(8,153,129,{opacity})",
                    "title": f"S ({touches}x)", "width": width,
                })
                sr_table_rows.append({"type": "Support", "level": round(float(lvl), 2), "touches": touches})

    # table सर्वात जास्त touches (high-probability) आधी दाखवण्यासाठी क्रमवारी
    sr_table_rows.sort(key=lambda r: -r["touches"])
    sr_table_html_rows = ""
    for r in sr_table_rows:
        row_color = "#F23645" if r["type"] == "Resistance" else "#089981"
        is_strong = r["touches"] >= 3
        weight = "700" if is_strong else "500"
        bg = "background:#1e222d;" if is_strong else ""
        sr_table_html_rows += f"""
        <tr style="{bg}">
            <td style="padding:6px 12px; color:{row_color}; font-weight:{weight};">{r['type']}</td>
            <td style="padding:6px 12px; color:#d1d4dc; font-weight:{weight}; font-size:{'14px' if is_strong else '12px'};">{r['level']:,.2f}</td>
            <td style="padding:6px 12px; color:{row_color}; font-weight:{weight};">{r['touches']}x{' 🔥' if is_strong else ''}</td>
        </tr>"""
    sr_table_section = ""
    if sr_table_rows:
        sr_table_section = f"""
  <div style="padding:10px 8px; background:{BG_COLOR};">
    <div style="color:{TEXT_COLOR}; font-size:12px; font-weight:600; padding:4px 12px;">📊 Support / Resistance Levels (जितके जास्त touches, तितकी उच्च-probability पातळी)</div>
    <table style="width:100%; border-collapse:collapse; font-family:-apple-system,sans-serif;">
      <thead>
        <tr style="border-bottom:1px solid {BORDER_COLOR};">
          <th style="padding:6px 12px; text-align:left; color:#787b86; font-size:11px;">प्रकार</th>
          <th style="padding:6px 12px; text-align:left; color:#787b86; font-size:11px;">किंमत</th>
          <th style="padding:6px 12px; text-align:left; color:#787b86; font-size:11px;">Touches</th>
        </tr>
      </thead>
      <tbody>{sr_table_html_rows}
      </tbody>
    </table>
  </div>"""

    st_legend_html = ""
    if st1d_bull or st1d_bear or st1h_bull or st1h_bear or st15m_bull or st15m_bear:
        legend_lines = []
        if st1d_bull or st1d_bear:
            legend_lines.append('<div><span class="st-line" style="border-top-width:3px; border-top-color:#9598a1;"></span>1D Supertrend</div>')
        if st1h_bull or st1h_bear:
            legend_lines.append('<div><span class="st-line" style="border-top-width:2px; border-top-color:#9598a1;"></span>1H Supertrend</div>')
        if st15m_bull or st15m_bear:
            legend_lines.append('<div><span class="st-line" style="border-top-width:1px; border-top-color:#9598a1;"></span>15M Supertrend</div>')
        st_legend_html = (
            '<div id="st_legend">' + "".join(legend_lines) +
            '<div style="margin-top:3px; font-size:9.5px; color:#787b86;">🟢 हिरवा=Bullish · 🔴 लाल=Bearish (एकाच रेषेची दिशा)</div></div>'
        )

    library_js = _load_library_js()
    html = f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8" />
<script>
{library_js}
</script>
<style>
  body {{ margin: 0; padding: 0; background: {BG_COLOR}; font-family: -apple-system, BlinkMacSystemFont, 'Trebuchet MS', Roboto, Ubuntu, sans-serif; }}
  #toolbar {{ display: flex; gap: 5px; padding: 6px 8px; background: {PANEL_COLOR}; border-bottom: 1px solid {BORDER_COLOR}; flex-wrap: wrap; }}
  .tool-btn {{
    background: #161a22; color: {TEXT_COLOR}; border: 1px solid {BORDER_COLOR}; border-radius: 4px;
    padding: 5px 10px; font-size: 11px; cursor: pointer;
  }}
  .tool-btn.active {{ background: #2962FF; color: white; border-color: #2962FF; }}
  .tool-btn:hover {{ background: #1c212b; }}
  #chart_container {{ width: 100%; height: {height}px; position: relative; }}
  #status {{ color: #787b86; font-size: 11px; padding: 4px 8px; }}
  #ohlc_box {{
    position: absolute; top: 8px; left: 8px; z-index: 5; background: rgba(13,16,23,0.85);
    border: 1px solid {BORDER_COLOR}; border-radius: 4px; padding: 6px 10px; font-size: 11px;
    color: {TEXT_COLOR}; display: none; pointer-events: none;
  }}
  #ohlc_box span.up {{ color: #089981; }}
  #ohlc_box span.down {{ color: #F23645; }}
  #st_legend {{
    position: absolute; top: 8px; right: 8px; z-index: 5; background: rgba(13,16,23,0.85);
    border: 1px solid {BORDER_COLOR}; border-radius: 4px; padding: 5px 10px; font-size: 10.5px;
    color: {TEXT_COLOR}; pointer-events: none;
  }}
  #st_legend .st-line {{ display: inline-block; width: 16px; height: 0; border-top-style: solid; margin-right: 4px; vertical-align: middle; }}
</style>
</head>
<body>
  <div id="toolbar">
    <button class="tool-btn" id="btn_trendline" onclick="setTool('trendline')">📈 Trendline</button>
    <button class="tool-btn" id="btn_hline" onclick="setTool('hline')">➖ H-Line</button>
    <button class="tool-btn" id="btn_fib" onclick="setTool('fib')">🌀 Fibonacci</button>
    <button class="tool-btn" id="btn_rect" onclick="setTool('rect')">▭ Rectangle</button>
    <button class="tool-btn" id="btn_measure" onclick="setTool('measure')">📏 Measure</button>
    <button class="tool-btn" onclick="setTool(null)">🖱️ Cursor</button>
    <button class="tool-btn" onclick="clearAllDrawings()">🗑️ सर्व मिटवा</button>
    <span id="status" style="align-self:center;"></span>
  </div>
  <div id="chart_container">
    <div id="ohlc_box"></div>
    {st_legend_html}
  </div>
{sr_table_section}

<script>
const chartOptions = {{
    layout: {{ background: {{ type: 'solid', color: '{BG_COLOR}' }}, textColor: '{TEXT_COLOR}', fontSize: 11 }},
    grid: {{ vertLines: {{ visible: false }}, horzLines: {{ visible: false }} }},
    crosshair: {{ mode: LightweightCharts.CrosshairMode.Normal }},
    timeScale: {{ timeVisible: true, secondsVisible: false, borderColor: '{BORDER_COLOR}' }},
    rightPriceScale: {{ borderColor: '{BORDER_COLOR}' }},
    autoSize: true,
}};
const chart = LightweightCharts.createChart(document.getElementById('chart_container'), chartOptions);

const candleSeries = chart.addSeries(LightweightCharts.CandlestickSeries, {{
    upColor: '#089981', downColor: '#F23645',
    borderUpColor: '#089981', borderDownColor: '#F23645',
    wickUpColor: '#089981', wickDownColor: '#F23645',
}});
candleSeries.setData({json.dumps(candle_data)});

const markerData = {json.dumps(marker_data)};
if (markerData.length > 0) {{
    LightweightCharts.createSeriesMarkers(candleSeries, markerData);
}}

// 🎓 1-Day व 1-Hour Supertrend (डीफॉल्ट, EMA20/EMA50 ऐवजी) — दिशेनुसार हिरवा(bullish)/लाल(bearish).
// आतून अजूनही 2 series (bullish+bearish भाग) आहेत (LightweightCharts मध्ये एका रेषेचा रंग मध्येच
// बदलता येत नाही म्हणून), पण टायटल रिकामं ठेवलं — "Bull"/"Bear" वेगळे indicators वाटून गोंधळ होत होता
// (वापरकर्त्याने निदर्शनास आणलं). एकच, स्वच्छ legend (टाईमफ्रेमनुसार, दिशेनुसार नाही) खाली दिली आहे.
function addSupertrendSeries(bullData, bearData, widthPx) {{
    if (bullData.length > 0) {{
        const s = chart.addSeries(LightweightCharts.LineSeries, {{
            color: '#089981', lineWidth: widthPx, title: '',
            lastValueVisible: false, priceLineVisible: false,
        }});
        s.setData(bullData);
    }}
    if (bearData.length > 0) {{
        const s = chart.addSeries(LightweightCharts.LineSeries, {{
            color: '#F23645', lineWidth: widthPx, title: '',
            lastValueVisible: false, priceLineVisible: false,
        }});
        s.setData(bearData);
    }}
}}
addSupertrendSeries({json.dumps(st1d_bull)}, {json.dumps(st1d_bear)}, 3);
addSupertrendSeries({json.dumps(st1h_bull)}, {json.dumps(st1h_bear)}, 2);
addSupertrendSeries({json.dumps(st15m_bull)}, {json.dumps(st15m_bear)}, 1);

const volumeData = {json.dumps(volume_data)};
if (volumeData.length > 0) {{
    const volumePane = chart.addPane();
    const volumeSeries = volumePane.addSeries(LightweightCharts.HistogramSeries, {{ color: '#26a69a', priceFormat: {{ type: 'volume' }} }});
    volumeSeries.setData(volumeData);
    volumePane.setHeight(80);
}}

const rsiData = {json.dumps(rsi_data)};
if (rsiData.length > 0) {{
    const rsiPane = chart.addPane();
    const rsiSeries = rsiPane.addSeries(LightweightCharts.LineSeries, {{ color: '#7e57c2', lineWidth: 1.5, title: 'RSI-14', lastValueVisible: false }});
    rsiSeries.setData(rsiData);
    rsiSeries.createPriceLine({{ price: 70, color: '#787b86', lineWidth: 1, lineStyle: LightweightCharts.LineStyle.Dashed }});
    rsiSeries.createPriceLine({{ price: 30, color: '#787b86', lineWidth: 1, lineStyle: LightweightCharts.LineStyle.Dashed }});
    rsiPane.setHeight(100);
}}

const srLines = {json.dumps(sr_lines_js)};
srLines.forEach(l => {{
    candleSeries.createPriceLine({{
        price: l.price, color: l.color, lineWidth: l.width,
        lineStyle: LightweightCharts.LineStyle.Dashed, title: l.title,
    }});
}});

chart.timeScale().fitContent();

// --- Crosshair वर OHLC माहिती-पेटी ---
const ohlcBox = document.getElementById('ohlc_box');
chart.subscribeCrosshairMove((param) => {{
    if (!param.time || !param.seriesData || !param.seriesData.get(candleSeries)) {{
        ohlcBox.style.display = 'none';
        return;
    }}
    const d = param.seriesData.get(candleSeries);
    const up = d.close >= d.open;
    ohlcBox.innerHTML = `<b>{symbol} · {timeframe_label}</b> &nbsp; O <span class="${{up ? 'up' : 'down'}}">${{d.open.toFixed(2)}}</span> ` +
        `H <span class="${{up ? 'up' : 'down'}}">${{d.high.toFixed(2)}}</span> L <span class="${{up ? 'up' : 'down'}}">${{d.low.toFixed(2)}}</span> ` +
        `C <span class="${{up ? 'up' : 'down'}}">${{d.close.toFixed(2)}}</span>`;
    ohlcBox.style.display = 'block';
}});

// --- Drawing Tools: Trendline, Horizontal Line, Fibonacci, Rectangle, Measure ---
let currentTool = null;
let firstPoint = null;
const drawnSeries = [];
const FIB_LEVELS = [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0];
const FIB_COLORS = ['#787b86', '#F23645', '#FF6D00', '#FFB400', '#089981', '#2962FF', '#787b86'];

function setTool(tool) {{
    currentTool = tool;
    firstPoint = null;
    ['trendline', 'hline', 'fib', 'rect', 'measure'].forEach(t => {{
        const btn = document.getElementById('btn_' + t);
        if (btn) btn.classList.toggle('active', tool === t);
    }});
    document.getElementById('status').textContent = tool ? ('Tool: ' + tool + ' — chart वर क्लिक करा') : '';
}}

chart.subscribeClick((param) => {{
    if (!currentTool || !param.point || param.time === undefined) return;
    const price = candleSeries.coordinateToPrice(param.point.y);
    if (price === null) return;

    if (currentTool === 'hline') {{
        const line = candleSeries.createPriceLine({{
            price: price, color: '#FFB400', lineWidth: 2,
            lineStyle: LightweightCharts.LineStyle.Solid, title: 'H-Line',
        }});
        drawnSeries.push({{ type: 'hline', ref: line }});
        setTool(null);
        return;
    }}

    if (currentTool === 'trendline') {{
        if (!firstPoint) {{
            firstPoint = {{ time: param.time, price: price }};
            document.getElementById('status').textContent = 'दुसरा बिंदू क्लिक करा';
            return;
        }}
        const lineSeries = chart.addSeries(LightweightCharts.LineSeries, {{
            color: '#2962FF', lineWidth: 2, lastValueVisible: false, priceLineVisible: false,
        }});
        lineSeries.setData([
            {{ time: firstPoint.time, value: firstPoint.price }},
            {{ time: param.time, value: price }},
        ]);
        drawnSeries.push({{ type: 'series', ref: lineSeries }});
        setTool(null);
        return;
    }}

    if (currentTool === 'fib') {{
        if (!firstPoint) {{
            firstPoint = {{ time: param.time, price: price }};
            document.getElementById('status').textContent = 'दुसरा बिंदू क्लिक करा (Fibonacci)';
            return;
        }}
        const high = Math.max(firstPoint.price, price);
        const low = Math.min(firstPoint.price, price);
        const range = high - low;
        FIB_LEVELS.forEach((lvl, i) => {{
            const lvlPrice = high - range * lvl;
            const s = chart.addSeries(LightweightCharts.LineSeries, {{
                color: FIB_COLORS[i], lineWidth: 1, lastValueVisible: false, priceLineVisible: false,
                title: (lvl * 100).toFixed(1) + '% (' + lvlPrice.toFixed(2) + ')',
            }});
            s.setData([
                {{ time: firstPoint.time, value: lvlPrice }},
                {{ time: param.time, value: lvlPrice }},
            ]);
            drawnSeries.push({{ type: 'series', ref: s }});
        }});
        setTool(null);
        return;
    }}

    if (currentTool === 'rect') {{
        if (!firstPoint) {{
            firstPoint = {{ time: param.time, price: price }};
            document.getElementById('status').textContent = 'विरुद्ध कोपरा क्लिक करा (Rectangle)';
            return;
        }}
        // 🎓 खरी भरीव (filled) rectangle lightweight-charts मध्ये सोप्या API ने शक्य नाही —
        // वरची व खालची सीमा-रेषा काढून झोन (zone) दाखवणे, जे व्यवहारात तेवढंच उपयुक्त आहे
        [firstPoint.price, price].forEach((p, i) => {{
            const s = chart.addSeries(LightweightCharts.LineSeries, {{
                color: '#2962FF', lineWidth: 2, lastValueVisible: false, priceLineVisible: false,
                lineStyle: LightweightCharts.LineStyle.Dashed,
            }});
            s.setData([
                {{ time: firstPoint.time, value: p }},
                {{ time: param.time, value: p }},
            ]);
            drawnSeries.push({{ type: 'series', ref: s }});
        }});
        setTool(null);
        return;
    }}

    if (currentTool === 'measure') {{
        if (!firstPoint) {{
            firstPoint = {{ time: param.time, price: price, x: param.point.x }};
            document.getElementById('status').textContent = 'दुसरा बिंदू क्लिक करा (Measure)';
            return;
        }}
        const deltaPrice = price - firstPoint.price;
        const deltaPct = (deltaPrice / firstPoint.price) * 100;
        const deltaTime = Math.abs(param.time - firstPoint.time);
        const sign = deltaPrice >= 0 ? '+' : '';
        document.getElementById('status').innerHTML =
            `📏 Δ ${{sign}}${{deltaPrice.toFixed(2)}} (${{sign}}${{deltaPct.toFixed(2)}}%) · ${{Math.round(deltaTime/60)}} मिनिटं`;
        const s = chart.addSeries(LightweightCharts.LineSeries, {{
            color: '#FFB400', lineWidth: 2, lastValueVisible: false, priceLineVisible: false,
            lineStyle: LightweightCharts.LineStyle.Dotted,
        }});
        s.setData([
            {{ time: firstPoint.time, value: firstPoint.price }},
            {{ time: param.time, value: price }},
        ]);
        drawnSeries.push({{ type: 'series', ref: s }});
        currentTool = null;
        firstPoint = null;
        ['trendline', 'hline', 'fib', 'rect', 'measure'].forEach(t => {{
            const btn = document.getElementById('btn_' + t);
            if (btn) btn.classList.toggle('active', false);
        }});
    }}
}});

function clearAllDrawings() {{
    drawnSeries.forEach(d => {{
        if (d.type === 'hline') {{ candleSeries.removePriceLine(d.ref); }}
        else {{ chart.removeSeries(d.ref); }}
    }});
    drawnSeries.length = 0;
    document.getElementById('status').textContent = 'सर्व drawings मिटवले';
}}
</script>
</body>
</html>
"""
    return html
