"""Broker Accounts page — Multi-Broker Multi-Account व्यवस्थापन.
🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — established Dashboard वरच्या tab-गर्दी कमी करण्यासाठी,
हे (established page_dashboard.py चं जुनं tab9) आता एक स्वतंत्र sidebar page आहे — कुठल्याही
symbol/token context शी संबंध नसल्यामुळे (established सर्व symbols/strategies साठी सामायिक),
वेगळं page असणं तार्किकदृष्ट्याही जास्त योग्य आहे."""
import streamlit as st


def render():
    st.subheader("⚙️ Broker Accounts व्यवस्थापन (Multi-Broker Multi-Account)")
    st.caption("इथे नोंदवलेले, सक्रिय (Active) accounts established SRv2/Dynamic-S/R सारख्या रणनींतींनी एकाच वेळी (replicated) वापरले जातील.")

    try:
        import cloud_db
        with st.expander("➕ नवीन Account जोडा", expanded=False):
            new_account_id = st.text_input("Account ID (unique नाव, उदा. 'Abhi-Upstox-Main')", key="new_account_id")
            new_broker_type = st.selectbox("Broker", ["upstox", "fyers"], key="new_broker_type")
            new_nickname = st.text_input("Nickname (ऐच्छिक, उदा. 'माझं मुख्य खातं')", key="new_nickname")
            new_lot_multiplier = st.number_input("Lot Multiplier (उदा. 2.0 म्हणजे established base-lots च्या दुप्पट)", min_value=0.1, value=1.0, step=0.1, key="new_lot_multiplier")
            if new_broker_type == "fyers":
                st.warning("⚠️ Fyers अजून पूर्ण झालेला नाही (Option-Symbol पडताळणी बाकी) — जोडता येईल, पण established रणनींती त्याला वगळतील, स्पष्ट error सह.")
            if st.button("Account जोडा", type="primary"):
                if not new_account_id.strip():
                    st.error("Account ID रिकामं ठेवता येणार नाही.")
                else:
                    added = cloud_db.add_broker_account(new_account_id.strip(), new_broker_type, new_nickname.strip() or None, new_lot_multiplier)
                    if added:
                        st.success(f"'{new_account_id}' यशस्वीरित्या जोडला.")
                        st.rerun()
                    else:
                        st.error("Account जोडता आला नाही (Supabase जोडणी तपासा).")

        st.markdown("---")
        st.markdown("##### 📋 नोंदवलेले सर्व Accounts")
        accounts_df = cloud_db.get_all_broker_accounts(active_only=False)
        if accounts_df is None or accounts_df.empty:
            st.info("अजून कुठलाही account नोंदवलेला नाही — वरून एक जोडा.")
        else:
            for _, acc in accounts_df.iterrows():
                acol1, acol2, acol3, acol4, acol5 = st.columns([2, 1, 1, 1, 1])
                with acol1:
                    st.markdown(f"**{acc['account_id']}** ({acc['nickname'] or '—'})")
                with acol2:
                    st.caption(f"Broker: {acc['broker_type']}")
                with acol3:
                    st.caption(f"Lots ×{acc['lot_multiplier']}")
                with acol4:
                    status_label = "🟢 Active" if acc["is_active"] else "🔴 Inactive"
                    st.caption(status_label)
                with acol5:
                    toggle_label = "बंद करा" if acc["is_active"] else "सुरू करा"
                    if st.button(toggle_label, key=f"toggle_{acc['account_id']}"):
                        cloud_db.set_broker_account_active(acc["account_id"], not acc["is_active"])
                        st.rerun()
                if st.button(f"🗑️ '{acc['account_id']}' काढून टाका", key=f"delete_{acc['account_id']}"):
                    cloud_db.delete_broker_account(acc["account_id"])
                    st.rerun()
                st.markdown("---")
    except Exception as e:
        st.error(f"Broker Accounts मध्ये चूक: {type(e).__name__}: {e}")
