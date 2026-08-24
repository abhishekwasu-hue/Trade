"""
TradingView-style chart — त्यांच्याच open-source 'Lightweight Charts' library वापरून, Streamlit HTML
component म्हणून embed केलेला. Plotly ऐवजी — खरा TradingView candle-रेंडरिंग, smooth pan/zoom, आणि
मूलभूत Drawing Tools (Trendline + Horizontal Line — fibonacci सारखे advanced tools नाहीत).
"""
import json
import os
import pandas as pd

_LIB_PATH = os.path.join(os.path.dirname(__file__), "lib", "lightweight-charts.js")


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
    ema20_series=None, ema50_series=None, rsi_series=None,
    sr_levels=None, height=650,
):
    """
    संपूर्ण TradingView Lightweight Charts HTML/JS पान तयार करणे — candlestick + volume (वेगळा pane) +
    EMA20/EMA50 (मुख्य किंमत chart वर) + RSI (वेगळा pane) + Support/Resistance (आडव्या रेषा) +
    Drawing Toolbar (Trendline + Horizontal Line — क्लिक करून काढता येणारे, पण Streamlit rerun झाल्यावर
    रीसेट होतात, कारण हे client-side JS state आहे, server ला परत पाठवलं जात नाही).
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

    ema20_data = []
    if ema20_series is not None and not ema20_series.empty:
        ema20_data = [
            {"time": _to_unix_time(t), "value": round(float(v), 2)}
            for t, v in zip(df["timestamp"], ema20_series) if pd.notna(v)
        ]
    ema50_data = []
    if ema50_series is not None and not ema50_series.empty:
        ema50_data = [
            {"time": _to_unix_time(t), "value": round(float(v), 2)}
            for t, v in zip(df["timestamp"], ema50_series) if pd.notna(v)
        ]
    rsi_data = []
    if rsi_series is not None and not rsi_series.empty:
        rsi_data = [
            {"time": _to_unix_time(t), "value": round(float(v), 2)}
            for t, v in zip(df["timestamp"], rsi_series) if pd.notna(v)
        ]

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
  <div style="padding:10px 8px; background:#131722;">
    <div style="color:#d1d4dc; font-size:12px; font-weight:600; padding:4px 12px;">📊 Support / Resistance Levels (जितके जास्त touches, तितकी उच्च-probability पातळी)</div>
    <table style="width:100%; border-collapse:collapse; font-family:-apple-system,sans-serif;">
      <thead>
        <tr style="border-bottom:1px solid #2a2e3d;">
          <th style="padding:6px 12px; text-align:left; color:#787b86; font-size:11px;">प्रकार</th>
          <th style="padding:6px 12px; text-align:left; color:#787b86; font-size:11px;">किंमत</th>
          <th style="padding:6px 12px; text-align:left; color:#787b86; font-size:11px;">Touches</th>
        </tr>
      </thead>
      <tbody>{sr_table_html_rows}
      </tbody>
    </table>
  </div>"""

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
  body {{ margin: 0; padding: 0; background: #131722; font-family: -apple-system, BlinkMacSystemFont, 'Trebuchet MS', Roboto, Ubuntu, sans-serif; }}
  #toolbar {{ display: flex; gap: 6px; padding: 6px 8px; background: #1e222d; border-bottom: 1px solid #2a2e3d; }}
  .tool-btn {{
    background: #2a2e3d; color: #d1d4dc; border: 1px solid #363a45; border-radius: 4px;
    padding: 5px 12px; font-size: 12px; cursor: pointer;
  }}
  .tool-btn.active {{ background: #2962FF; color: white; border-color: #2962FF; }}
  .tool-btn:hover {{ background: #363a45; }}
  #chart_container {{ width: 100%; height: {height}px; }}
  #status {{ color: #787b86; font-size: 11px; padding: 4px 8px; }}
</style>
</head>
<body>
  <div id="toolbar">
    <button class="tool-btn" id="btn_trendline" onclick="setTool('trendline')">📈 Trendline</button>
    <button class="tool-btn" id="btn_hline" onclick="setTool('hline')">➖ Horizontal Line</button>
    <button class="tool-btn" onclick="setTool(null)">🖱️ Cursor</button>
    <button class="tool-btn" onclick="clearAllDrawings()">🗑️ सर्व मिटवा</button>
    <span id="status" style="align-self:center;"></span>
  </div>
  <div id="chart_container"></div>
{sr_table_section}

<script>
const chartOptions = {{
    layout: {{ background: {{ type: 'solid', color: '#131722' }}, textColor: '#d1d4dc', fontSize: 11 }},
    grid: {{ vertLines: {{ color: '#1e222d' }}, horzLines: {{ color: '#1e222d' }} }},
    crosshair: {{ mode: LightweightCharts.CrosshairMode.Normal }},
    timeScale: {{ timeVisible: true, secondsVisible: false, borderColor: '#2a2e3d' }},
    rightPriceScale: {{ borderColor: '#2a2e3d' }},
    autoSize: true,
}};
const chart = LightweightCharts.createChart(document.getElementById('chart_container'), chartOptions);

const candleSeries = chart.addSeries(LightweightCharts.CandlestickSeries, {{
    upColor: '#089981', downColor: '#F23645',
    borderUpColor: '#089981', borderDownColor: '#F23645',
    wickUpColor: '#089981', wickDownColor: '#F23645',
}});
candleSeries.setData({json.dumps(candle_data)});

const ema20Data = {json.dumps(ema20_data)};
if (ema20Data.length > 0) {{
    const ema20Series = chart.addSeries(LightweightCharts.LineSeries, {{ color: '#2962FF', lineWidth: 1, title: 'EMA20', lastValueVisible: false }});
    ema20Series.setData(ema20Data);
}}
const ema50Data = {json.dumps(ema50_data)};
if (ema50Data.length > 0) {{
    const ema50Series = chart.addSeries(LightweightCharts.LineSeries, {{ color: '#FF6D00', lineWidth: 1, title: 'EMA50', lastValueVisible: false }});
    ema50Series.setData(ema50Data);
}}

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

// --- Drawing Tools (Trendline + Horizontal Line) ---
let currentTool = null;
let trendlineFirstPoint = null;
const drawnSeries = [];

function setTool(tool) {{
    currentTool = tool;
    trendlineFirstPoint = null;
    document.getElementById('btn_trendline').classList.toggle('active', tool === 'trendline');
    document.getElementById('btn_hline').classList.toggle('active', tool === 'hline');
    document.getElementById('status').textContent = tool ? ('Tool: ' + tool + ' - chart वर क्लिक करा') : '';
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
        if (!trendlineFirstPoint) {{
            trendlineFirstPoint = {{ time: param.time, price: price }};
            document.getElementById('status').textContent = 'दुसरा बिंदू क्लिक करा';
            return;
        }}
        const lineSeries = chart.addSeries(LightweightCharts.LineSeries, {{
            color: '#2962FF', lineWidth: 2, lastValueVisible: false, priceLineVisible: false,
        }});
        lineSeries.setData([
            {{ time: trendlineFirstPoint.time, value: trendlineFirstPoint.price }},
            {{ time: param.time, value: price }},
        ]);
        drawnSeries.push({{ type: 'trendline', ref: lineSeries }});
        setTool(null);
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
