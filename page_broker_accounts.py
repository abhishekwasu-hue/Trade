"""Broker Accounts page — Multi-Broker Multi-Account व्यवस्थापन.
🎓 वापरकर्त्याशी चर्चा करून जोडलेली सुधारणा — established Dashboard वरच्या tab-गर्दी कमी करण्यासाठी,
हे (established page_dashboard.py चं जुनं tab9) आता एक स्वतंत्र sidebar page आहे — कुठल्याही
symbol/token context शी संबंध नसल्यामुळे (established सर्व symbols/strategies साठी सामायिक),
वेगळं page असणं तार्किकदृष्ट्याही जास्त योग्य आहे.

🎓 वापरकर्त्याशी चर्चा करून वाढवलेली सुधारणा (User-Friendly Login Wizard) — आधी नवीन account
जोडणं (Broker Accounts पान) आणि प्रत्यक्ष broker login (टर्मिनल/SSH मधून established
get_upstox_token_manual.py/get_fyers_token_manual.py स्वतंत्रपणे चालवून) — या दोन वेगळ्या, गोंधळात
टाकणाऱ्या पायऱ्या होत्या (established Account ID कुठला "user id" आहे असा गोंधळ व्हायचा). आता
established दोन्ही एकाच फॉर्ममध्ये, एकदाच — टर्मिनलची गरजच नाही."""
import streamlit as st


def render():
    st.subheader("⚙️ Settings")

    try:
        import cloud_db

        st.markdown("##### 🎯 SRv2 Momentum-Reversal Settings (15M/30M/60M)")
        st.caption(
            "Lots आणि Hedge Width Points — इथून बदलले की लगेच पुढच्या cycle पासून लागू होतील "
            "(hardcoded नाहीत — कधीही, वेळोवेळी बदलता येतील)."
        )
        srv2_settings_symbol = st.selectbox(
            "Symbol", ["NIFTY", "BANKNIFTY", "SENSEX"], key="srv2_settings_symbol",
        )
        current_srv2_settings = cloud_db.get_srv2_settings(srv2_settings_symbol)
        srv2_col1, srv2_col2 = st.columns(2)
        with srv2_col1:
            new_srv2_lots = st.number_input(
                "Lots", min_value=1, max_value=50, value=int(current_srv2_settings["lots"]),
                step=1, key="srv2_lots_input",
            )
        with srv2_col2:
            new_srv2_hedge_width = st.number_input(
                "Hedge Width Points", min_value=25.0, max_value=1000.0,
                value=float(current_srv2_settings["hedge_width_points"]), step=25.0,
                key="srv2_hedge_width_input",
            )
        if st.button("💾 SRv2 Settings जतन करा", key="save_srv2_settings_btn"):
            ok = cloud_db.save_srv2_settings(srv2_settings_symbol, int(new_srv2_lots), float(new_srv2_hedge_width))
            if ok:
                st.success(f"✅ {srv2_settings_symbol} साठी जतन झालं — Lots: {int(new_srv2_lots)}, Hedge Width: {float(new_srv2_hedge_width)}")
            else:
                st.error("जतन करता आलं नाही (Supabase जोडणी तपासा).")

        st.markdown("---")
        st.markdown("##### 🏦 Broker Accounts (Multi-Broker Multi-Account)")
        st.caption("इथे नोंदवलेले, सक्रिय (Active) accounts SRv2/Dynamic-S/R सारख्या रणनींतींनी एकाच वेळी (replicated) वापरले जातील.")


        with st.expander("➕ नवीन Account जोडा (Login सह — एकाच वेळी, शिफारस केलेली पद्धत)", expanded=False):
            st.caption(
                "Account नोंदणी + Broker Login — established दोन्ही एकाच वेळी, इथूनच. "
                "टर्मिनल/SSH ची गरज नाही. established आधी Upstox/Fyers च्या Developer Console मध्ये "
                "एक App तयार केलेलं असावं (App ID/Secret + Redirect URI मिळण्यासाठी, एकदाच)."
            )
            st.info(
                "📱 **मोबाईलवर सूचना** — लॉगिन करण्यासाठी ब्राउझरचं नवीन टॅब उघडेल. लॉगिन करून परत या "
                "टॅबवर आल्यावर वरची माहिती (App ID/Secret) गायब दिसली, तर पुन्हा टाका — मोबाईल ब्राउझर "
                "कधीकधी टॅब बदलताना जुनी माहिती विसरतो. यासाठी App ID/Secret एका नोट्स ॲपमध्ये आधीच "
                "कॉपी ठेवलं तर पुन्हा टाकणं झटपट होईल."
            )
            wiz_broker_type = st.selectbox("Broker", ["upstox", "fyers"], key="wiz_broker_type")
            wiz_account_id = st.text_input(
                "Account ID (तुम्हीच ठरवलेलं, कुठलंही unique नाव — उदा. 'Abhi-Fyers'; हा Broker चा User ID नाही, फक्त इथलं लेबल)",
                key="wiz_account_id",
            )
            wiz_nickname = st.text_input("Nickname (ऐच्छिक, उदा. 'माझं Fyers खातं')", key="wiz_nickname")
            wiz_lot_multiplier = st.number_input(
                "Lot Multiplier (उदा. 2.0 म्हणजे established base-lots च्या दुप्पट)",
                min_value=0.1, value=1.0, step=0.1, key="wiz_lot_multiplier",
            )

            st.markdown("---")
            st.markdown(f"**{wiz_broker_type.title()} Developer App तपशील**")
            # 🎓 वापरकर्त्याने विचारलेला प्रश्न ("खरंच user-friendly आहे का?") — पहिल्यांदाच हे करणाऱ्याला
            # "App ID कुठून मिळणार" हेच माहीत नसतं — इथेच स्पष्ट मार्गदर्शन.
            if wiz_broker_type == "upstox":
                st.caption("🔗 App नसेल तर आधी तयार करा: [Upstox Developer Console](https://account.upstox.com/developer/apps)")
            else:
                st.caption("🔗 App नसेल तर आधी तयार करा: [Fyers Developer Console](https://myapi.fyers.in/dashboard)")
            st.caption("Redirect URI कुठलाही चालतो (उदा. `https://127.0.0.1`) — फक्त App मध्ये नोंदवलेला आणि इथे टाकलेला **तंतोतंत सारखाच** हवा.")
            if wiz_broker_type == "upstox":
                wiz_app_id = st.text_input("Client ID", key="wiz_upstox_client_id")
                wiz_app_secret = st.text_input("Client Secret", type="password", key="wiz_upstox_client_secret")
            else:
                wiz_app_id = st.text_input("App ID (उदा. XXXXXX-100)", key="wiz_fyers_app_id")
                wiz_app_secret = st.text_input("App Secret", type="password", key="wiz_fyers_app_secret")
            wiz_redirect_uri = st.text_input(
                "Redirect URI (तुमच्या App मध्ये established नोंदवलेलाच, तंतोतंत तसाच)",
                key="wiz_redirect_uri",
            )

            if st.button("१. Login URL तयार करा", key="wiz_gen_url"):
                if not (wiz_account_id.strip() and wiz_app_id.strip() and wiz_app_secret.strip() and wiz_redirect_uri.strip()):
                    st.error("वरची सर्व माहिती (Account ID, App ID/Client ID, Secret, Redirect URI) आधी भरा.")
                else:
                    if wiz_broker_type == "upstox":
                        from get_upstox_token_manual import build_login_url as _build_url
                    else:
                        from get_fyers_token_manual import build_login_url as _build_url
                    st.session_state["wiz_login_url"] = _build_url(wiz_app_id.strip(), wiz_redirect_uri.strip())

            if st.session_state.get("wiz_login_url"):
                # 🎓 वापरकर्त्याने विचारलेला प्रश्न — established आधी st.code() (फक्त कॉपी, क्लिक करता
                # येत नाही) होतं, मोबाईलवर विशेष त्रासदायक — आता खरी क्लिक करण्याजोगी लिंक.
                st.markdown(f"**पायरी अ — इथे क्लिक करून लॉगिन करा:** [🔗 {wiz_broker_type.title()} Login उघडा]({st.session_state['wiz_login_url']})")
                with st.expander("URL कॉपी करायचंय? (लिंक चालत नसेल तरच)"):
                    st.code(st.session_state["wiz_login_url"])

                code_field_name = "auth_code" if wiz_broker_type == "fyers" else "code"
                st.warning(
                    f"⚠️ **लॉगिन नंतर पान \"होत नाही उघडत\"/\"Error\" दाखवेल — हे सामान्य आहे, काळजी करू नका.** "
                    f"त्या (error दाखवणाऱ्या) पानाच्या **address bar** मध्ये बघा — तिथल्या URL मध्ये "
                    f"'{code_field_name}=' नंतरचा भाग (पुढच्या '&' चिन्हापर्यंतच, त्यानंतरचं काहीही नाही) "
                    f"निवडून कॉपी करा — तेच खाली पेस्ट करायचं आहे, संपूर्ण URL नाही."
                )
                st.caption(f"पायरी ब — established '{code_field_name}=' नंतरचा भागच (पूर्ण URL नाही) इथे पेस्ट करा:")
                wiz_auth_code = st.text_input(code_field_name.title(), key="wiz_auth_code")
                # 🎓 established चुकून संपूर्ण URL paste केला (फक्त code ऐवजी) तर लगेच कळावं म्हणून तपासणी.
                if wiz_auth_code.strip().startswith("http"):
                    st.error(f"हा तर संपूर्ण URL दिसतोय — फक्त '{code_field_name}=' नंतरचा भाग (URL नाही) टाका.")

                if st.button("२. Setup पूर्ण करा (Token मिळवा + Account नोंदवा)", type="primary", key="wiz_complete"):
                    if not wiz_auth_code.strip() or wiz_auth_code.strip().startswith("http"):
                        st.error(f"आधी वरचा बरोबर {code_field_name} टाका (पूर्ण URL नाही, फक्त तो भाग).")
                    else:
                        if wiz_broker_type == "upstox":
                            from get_upstox_token_manual import exchange_code_for_token
                            token, error = exchange_code_for_token(
                                wiz_app_id.strip(), wiz_app_secret.strip(), wiz_redirect_uri.strip(), wiz_auth_code.strip(),
                            )
                        else:
                            from fyers_api import exchange_auth_code_for_token
                            token, error = exchange_auth_code_for_token(
                                wiz_app_id.strip(), wiz_app_secret.strip(), wiz_auth_code.strip(),
                            )

                        if error:
                            st.error(f"Token मिळवताना अयशस्वी: {error}")
                        else:
                            cloud_db.init_cloud_table()
                            token_saved = cloud_db.save_upstox_token(token, account_id=wiz_account_id.strip())
                            account_added = cloud_db.add_broker_account(
                                wiz_account_id.strip(), wiz_broker_type, wiz_nickname.strip() or None, wiz_lot_multiplier,
                            )
                            if token_saved and account_added:
                                st.success(f"✅ '{wiz_account_id}' — token साठवला आणि account नोंदवला. आता Strategy Builder/इतर strategies मध्ये हे account निवडता येईल.")
                                del st.session_state["wiz_login_url"]
                                st.rerun()
                            else:
                                st.warning("⚠️ token/account साठवताना अंशतः अयशस्वी — SUPABASE_DB_URL सेट आहे का तपासा.")

            st.caption(
                "🔁 **रोजची आठवण** — Upstox/Fyers दोन्हीचे token रोज expire होतात (broker च्याच धोरणामुळे). "
                "रोज सकाळी हीच पायरी (Login URL → लॉगिन → code पेस्ट → Setup पूर्ण करा) पुन्हा करावी लागेल — "
                "'Account नोंदणी' पुन्हा करावी लागणार नाही (established आपोआप अद्ययावत/upsert होते), फक्त token ताजा होतो."
            )

        with st.expander("🔧 Advanced — आधीच token असेल तर (फक्त Account नोंदणी)", expanded=False):
            st.caption("जर तुम्ही CLI script (get_upstox_token_manual.py/get_fyers_token_manual.py) द्वारे आधीच token साठवलेला असेल, तर फक्त Account इथे नोंदवा.")
            new_account_id = st.text_input("Account ID (unique नाव, उदा. 'Abhi-Upstox-Main')", key="new_account_id")
            new_broker_type = st.selectbox("Broker", ["upstox", "fyers"], key="new_broker_type")
            new_nickname = st.text_input("Nickname (ऐच्छिक, उदा. 'माझं मुख्य खातं')", key="new_nickname")
            new_lot_multiplier = st.number_input("Lot Multiplier (उदा. 2.0 म्हणजे established base-lots च्या दुप्पट)", min_value=0.1, value=1.0, step=0.1, key="new_lot_multiplier")
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
