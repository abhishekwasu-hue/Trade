"""
pnl_reports.py
------------------------------
Daily / Weekly / Monthly P&L Report — बंद झालेल्या trades चा Gross P&L आणि charges.py वरून
मोजलेलं वास्तविक ब्रोकरेज शुल्क एकत्र करून, प्रत्येक कालावधीसाठी Net P&L दाखवणारा रिपोर्ट.
"""
import pandas as pd

from charges import compute_charges, get_account_broker_map
from database import get_closed_trades_for_report, get_orders_with_account

PERIOD_FREQ = {"Daily": "D", "Weekly": "W", "Monthly": "MS"}

_EMPTY_REPORT_COLUMNS = ["Period", "Trades", "Gross P&L", "Charges", "Net P&L", "Orders"]
_EMPTY_TOTALS = {
    "total_trades": 0, "gross_pnl": 0.0, "total_charges": 0.0, "net_pnl": 0.0,
    "total_orders": 0, "charges_by_broker": {},
}


def generate_pnl_report(symbol, period, start_date, end_date, mode_filter=None):
    """
    period: "Daily" | "Weekly" | "Monthly"
    start_date/end_date: datetime.date

    रिटर्न: (report_df, totals)
      report_df columns: Period, Trades, Gross P&L, Charges, Net P&L, Orders
      totals: {"total_trades", "gross_pnl", "total_charges", "net_pnl", "total_orders", "charges_by_broker"}
    """
    trades_df = get_closed_trades_for_report(symbol, start_date, end_date, mode_filter=mode_filter)
    orders_df = get_orders_with_account(symbol, start_date, end_date, mode_filter=mode_filter)

    broker_map = get_account_broker_map()
    daily_charges_df, charges_summary = compute_charges(orders_df, start_date, end_date, broker_map=broker_map)

    if trades_df.empty:
        daily_pnl = pd.DataFrame(columns=["date", "Trades", "Gross P&L"])
    else:
        trades_df = trades_df.copy()
        trades_df["date"] = trades_df["exit_time"].dt.date
        daily_pnl = (
            trades_df.groupby("date")["realized_pnl"]
            .agg(Trades="count", **{"Gross P&L": "sum"})
            .reset_index()
        )

    if daily_charges_df.empty:
        daily_charge_agg = pd.DataFrame(columns=["date", "Orders", "Charges"])
    else:
        daily_charge_agg = (
            daily_charges_df.groupby("date")
            .agg(Orders=("orders", "sum"), Charges=("charge", "sum"))
            .reset_index()
        )

    merged = pd.merge(daily_pnl, daily_charge_agg, on="date", how="outer").fillna(0)
    if merged.empty:
        return pd.DataFrame(columns=_EMPTY_REPORT_COLUMNS), dict(_EMPTY_TOTALS)

    merged["date"] = pd.to_datetime(merged["date"])
    merged = merged.set_index("date").sort_index()

    freq = PERIOD_FREQ.get(period, "D")
    resampled = merged.resample(freq).sum()
    resampled = resampled[(resampled["Trades"] > 0) | (resampled["Orders"] > 0) | (resampled["Charges"] != 0)]
    if resampled.empty:
        return pd.DataFrame(columns=_EMPTY_REPORT_COLUMNS), dict(_EMPTY_TOTALS)

    resampled["Net P&L"] = resampled["Gross P&L"] - resampled["Charges"]
    resampled = resampled.reset_index()

    if period == "Daily":
        resampled["Period"] = resampled["date"].dt.strftime("%Y-%m-%d")
    elif period == "Weekly":
        resampled["Period"] = resampled["date"].dt.strftime("%Y-%m-%d") + " आठवडा सुरू"
    else:
        resampled["Period"] = resampled["date"].dt.strftime("%Y-%m")

    report_df = resampled[["Period", "Trades", "Gross P&L", "Charges", "Net P&L", "Orders"]].copy()
    report_df["Trades"] = report_df["Trades"].astype(int)
    report_df["Orders"] = report_df["Orders"].astype(int)
    for col in ["Gross P&L", "Charges", "Net P&L"]:
        report_df[col] = report_df[col].round(2)

    totals = {
        "total_trades": int(report_df["Trades"].sum()),
        "gross_pnl": round(report_df["Gross P&L"].sum(), 2),
        "total_charges": round(report_df["Charges"].sum(), 2),
        "net_pnl": round(report_df["Net P&L"].sum(), 2),
        # 🎓 charges_summary["total_orders"] वापरणे आवश्यक — report_df["Orders"] कॉलम फक्त
        # प्रति-ऑर्डर ब्रोकर्स (Upstox/Fyers/Shoonya) मोजतो; Stocko चं निश्चित मासिक शुल्क कुठल्याही
        # एका दिवसाशी बांधलेलं नसल्याने त्या दिवसागणिक रांगांत orders=0 असतो (report_df["Orders"].sum()
        # केलं तर Stocko चे प्रत्यक्ष ऑर्डर्स मोजलेच जाणार नाहीत).
        "total_orders": charges_summary["total_orders"],
        "charges_by_broker": charges_summary["per_broker"],
    }
    return report_df, totals
