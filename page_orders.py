"""Orders page — order book, System Diagnostics, and Data Safety / Broker Reconciliation."""
import datetime
import pandas as pd
import streamlit as st

from config import get_ist_now, get_ist_today
from database import get_order_log_full, get_db_backup_bytes, restore_db_from_bytes
from diagnostics import run_system_diagnostics
from trading_engine import reconcile_positions
from upstox_api import fetch_long_history, upload_to_google_drive
from ui_headers import mega_header, sub_header, HDR_BLUE, HDR_TEAL, HDR_PURPLE

def render():
    symbol = st.session_state["symbol"]
    token_input = st.session_state["token_input"]
    underlying_price = st.session_state.get("underlying_price", 0)

    with st.expander("🩺 System Diagnostics — रोज ट्रेडिंग सुरू करण्याआधी तपासा", expanded=False):
        if st.button("🔍 पूर्ण Diagnostics चालवा"):
            with st.spinner("तपासत आहे..."):
                diag = run_system_diagnostics(token_input, symbol)

            st.caption(f"तपासलं: {diag['checked_at']}")

            dcol1, dcol2 = st.columns(2)
            with dcol1:
                st.markdown(f"**Upstox Token:** {'✅ वैध' if diag['token_valid'] else '❌ अवैध / एरर'}")
                if diag["proxy_configured"]:
                    st.markdown(f"**Static IP Proxy:** {'✅ जुळतो' if diag['proxy_ip_match'] else '❌ जुळत नाही'}")
                else:
                    st.markdown("**Static IP Proxy:** ⚪ कॉन्फिगर केलेला नाही")
                fresh = diag["data_freshness"]
                if fresh.get("has_data"):
                    fresh_ok = fresh["minutes_ago"] < 60
                    st.markdown(f"**OI Data Freshness:** {'✅' if fresh_ok else '⚠️'} शेवटचा snapshot {fresh['minutes_ago']:.0f} मिनिटांपूर्वी")
                else:
                    st.markdown("**OI Data Freshness:** ⚪ अजून कोणताही snapshot नाही")

            with dcol2:
                pdf_deps = diag["pdf_deps"]
                st.markdown(f"**kaleido (चार्ट्ससाठी):** {'✅' if pdf_deps['kaleido'] else '❌ नाही'}")
                st.markdown(f"**reportlab (PDF साठी):** {'✅' if pdf_deps['reportlab'] else '❌ नाही'}")
                st.markdown(f"**Fonts (fonts/DejaVuSans.ttf):** {'✅' if pdf_deps['fonts_present'] else '❌ नाही'}")

            db_health = diag["db_health"]
            if db_health["status"] == "ok":
                st.markdown("**Database Tables:**")
                db_rows = [{"Table": t, "Exists": "✅" if info["exists"] else "❌", "Rows": info["rows"]} for t, info in db_health["tables"].items()]
                st.dataframe(pd.DataFrame(db_rows), width="stretch", hide_index=True)
            else:
                st.error(f"❌ Database तपासणी अयशस्वी: {db_health.get('message')}")

            all_ok = (
                diag["token_valid"] and (diag["proxy_ip_match"] is not False)
                and pdf_deps["kaleido"] and pdf_deps["reportlab"]
                and db_health["status"] == "ok"
            )
            if all_ok:
                st.success("✅ सिस्टीम ट्रेडिंगसाठी तयार दिसतंय.")
            else:
                st.warning("⚠️ वरील एक किंवा अधिक तपासण्यांमध्ये समस्या आढळली — ट्रेडिंग सुरू करण्याआधी बघा.")

    st.markdown("---")
    mega_header("📝 Order Book", HDR_BLUE)
    ord_mode_choice = st.radio("दाखवा:", ["सर्व", "फक्त LIVE", "फक्त PAPER"], horizontal=True, key="ord_mode_filter")
    ord_mode_f = None if ord_mode_choice == "सर्व" else ("LIVE" if "LIVE" in ord_mode_choice else "PAPER")

    # 🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — Order Book आता तारीख-रेंज निवडता येतो
    # (डीफॉल्ट: आजचीच तारीख) — आधी फक्त "अलीकडचे २००" दिसायचे, तारीख फिल्टर नव्हता.
    today_d = get_ist_today()
    ord_range_choice = st.radio(
        "कालावधी", ["आज", "गेले 7 दिवस", "गेला महिना", "कस्टम रेंज"], horizontal=True, key="orders_range_choice",
    )
    if ord_range_choice == "आज":
        ord_from, ord_to = today_d, today_d
    elif ord_range_choice == "गेले 7 दिवस":
        ord_from, ord_to = today_d - datetime.timedelta(days=7), today_d
    elif ord_range_choice == "गेला महिना":
        ord_from, ord_to = today_d - datetime.timedelta(days=30), today_d
    else:
        odcol1, odcol2 = st.columns(2)
        with odcol1:
            ord_from = st.date_input("पासून", value=today_d, key="orders_from")
        with odcol2:
            ord_to = st.date_input("पर्यंत", value=today_d, key="orders_to")

    if ord_from > ord_to:
        st.error("'पर्यंत' ही तारीख 'पासून' नंतरची असावी.")
    else:
        orders_df = get_order_log_full(symbol, start_date=ord_from, end_date=ord_to, mode_filter=ord_mode_f)
        if orders_df.empty:
            st.info("या कालावधीत कोणतेही ऑर्डर्स नाहीत.")
        else:
            st.dataframe(orders_df, width='stretch', height=400)
            st.caption(f"{ord_from} ते {ord_to}: एकूण {len(orders_df)} ऑर्डर्स (नवीनतम आधी) — Single, Basket, A1 Engine व SL/Target/EOD close या सर्वांच्या नोंदी.")
            order_dl_csv = orders_df.to_csv(index=False).encode("utf-8")
            st.download_button(
                "📥 Order Log CSV डाऊनलोड करा", data=order_dl_csv,
                file_name=f"{symbol}_OrderLog_{ord_from}_{ord_to}.csv",
                mime="text/csv", key="orders_dl_download",
            )

    st.markdown("---")
    with st.expander("🛡️ Data Safety & Broker Reconciliation"):
        sub_header("💾 Database Backup / Restore", HDR_TEAL)
        st.caption(
            "Streamlit Cloud चा storage ephemeral आहे — container restart/redeploy झाला तर हा DB (सर्व trade "
            "history, OI history) मिटू शकतो. नियमितपणे (उदा. रोज ट्रेडिंगनंतर) backup डाऊनलोड करून ठेवा."
        )
        bcol1, bcol2 = st.columns(2)
        with bcol1:
            backup_bytes = get_db_backup_bytes()
            if backup_bytes:
                st.download_button(
                    "📥 Download DB Backup", data=backup_bytes,
                    file_name=f"amw_a1_backup_{get_ist_now().strftime('%Y%m%d_%H%M%S')}.db",
                    mime="application/octet-stream",
                )
            else:
                st.warning("Backup तयार करता आला नाही.")
        with bcol2:
            restore_file = st.file_uploader("Backup वरून Restore करा", type=["db"], key="restore_uploader")
            if restore_file is not None:
                confirm_restore = st.checkbox("⚠️ मला समजते — यामुळे सद्य DB (आजचे trades सुद्धा) बदलले जातील", key="confirm_restore")
                if st.button("🔄 Restore करा", disabled=not confirm_restore):
                    ok, msg = restore_db_from_bytes(restore_file.read())
                    if ok:
                        st.success(f"✅ {msg} — पेज रिफ्रेश करा.")
                    else:
                        st.error(f"❌ {msg}")

        st.markdown("---")
        sub_header("🔄 Broker Reconciliation (फक्त LIVE ट्रेड्ससाठी)", HDR_PURPLE)
        st.caption(
            "स्थानिक DB मधील OPEN LIVE ट्रेड्सची तुलना Upstox कडील खऱ्या पोझिशन्सशी करणे — तुम्ही Upstox "
            "app मधून manually एखादी पोझिशन बंद केली असेल, तर ती इथे लगेच दिसेल."
        )
        if st.button("🔍 Reconciliation Check चालवा"):
            with st.spinner("Broker positions तपासत आहे..."):
                recon_result = reconcile_positions(token_input, symbol)
            if recon_result["status"] == "error":
                st.error(f"❌ {recon_result['message']}")
            else:
                st.caption(f"तपासलं: {recon_result['checked_at']}")
                if not recon_result["mismatches"] and not recon_result["unexplained_broker_positions"]:
                    st.success("✅ सर्व स्थानिक LIVE ट्रेड्स व Broker पोझिशन्स जुळतात — कोणतीही विसंगती नाही.")
                if recon_result["mismatches"]:
                    st.error(f"🚨 {len(recon_result['mismatches'])} leg(s) स्थानिक DB मध्ये OPEN आहेत पण Broker कडे बंद झालेल्या दिसतायत:")
                    st.dataframe(pd.DataFrame(recon_result["mismatches"]), width='stretch')
                    st.caption("शक्य कारण: तुम्ही Upstox app मधून manually बंद केलं असेल. वरील Trade ID साठी स्थानिक स्टेटस मॅन्युअली अपडेट करावा लागेल.")
                if recon_result["unexplained_broker_positions"]:
                    st.warning(f"ℹ️ Broker कडे {len(recon_result['unexplained_broker_positions'])} पोझिशन्स आहेत ज्या या app मध्ये ट्रॅक केलेल्या नाहीत (या NIFTY शीच संबंधित असतील असं नाही — स्वतः तपासा):")
                    st.dataframe(pd.DataFrame(recon_result["unexplained_broker_positions"]), width='stretch')

    with st.expander("☁️ NIFTY 20-Year History → Google Drive (Backtest साठी)"):
        st.caption(
            "Upstox च्या V3 API नुसार Daily डेटा जानेवारी 2000 पासून उपलब्ध आहे — त्यामुळे जास्तीत जास्त "
            "20 वर्षांचा (किंवा तितका जुना डेटा उपलब्ध असेल तितका) Daily NIFTY डेटा एकदा fetch करून "
            "Google Drive वर CSV म्हणून साठवता येतो. **सेटअप आवश्यक**: Streamlit secrets मध्ये "
            "`[gdrive]` अंतर्गत `service_account_json` व `folder_id` (आणि तो फोल्डर त्या service "
            "account च्या ईमेलसोबत आधी शेअर केलेला असावा) — नसेल तर हे बटण स्पष्ट त्रुटी दाखवेल."
        )
        years_to_fetch = st.number_input("किती वर्षांचा डेटा (कमाल)", min_value=1, max_value=26, value=20, step=1, key="gdrive_years")
        if st.button("📥 Fetch करून Google Drive वर Save करा"):
            progress_bar = st.progress(0.0)
            status_text = st.empty()

            def _progress_cb(frac, c_start, c_end):
                progress_bar.progress(frac)
                status_text.caption(f"फेच होत आहे: {c_start} → {c_end}")

            with st.spinner("ऐतिहासिक डेटा फेच होत आहे — यास काही मिनिटं लागू शकतात..."):
                hist_df = fetch_long_history(token_input, symbol, years=years_to_fetch, progress_callback=_progress_cb)

            progress_bar.empty()
            status_text.empty()

            if hist_df.empty:
                st.error("❌ कोणताही ऐतिहासिक डेटा मिळाला नाही.")
            else:
                st.success(f"✅ {len(hist_df):,} दैनिक candles मिळाले ({hist_df['timestamp'].min().date()} ते {hist_df['timestamp'].max().date()}).")
                csv_bytes = hist_df.to_csv(index=False).encode("utf-8")
                filename = f"{symbol}_daily_history_{get_ist_today().strftime('%Y%m%d')}.csv"

                with st.spinner("Google Drive वर अपलोड होत आहे..."):
                    ok, result = upload_to_google_drive(csv_bytes, filename, mime_type="text/csv")
                if ok:
                    st.success(f"✅ Google Drive वर सेव्ह झालं: {result}")
                else:
                    st.error(f"❌ Google Drive अपलोड अयशस्वी: {result}")
                    st.info("तरीही, खालून हा डेटा थेट डाऊनलोड करता येईल:")

                st.download_button(
                    "📥 CSV थेट डाऊनलोड करा (backup)", data=csv_bytes, file_name=filename, mime="text/csv",
                )

