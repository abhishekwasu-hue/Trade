"""
test_supabase_connection.py
--------------------------------
तुमच्या Supabase (PostgreSQL) जोडणीची पूर्ण, पायरी-पायरीने चाचणी — local machine वर चालवायची.
आपल्याच cloud_db.py मधली खरी (production) functions वापरतो — वेगळी, समांतर logic नाही.

⚙️ वापरणे:
  पद्धत १ (environment variable, जास्त सुरक्षित — कुठेही टाईप/save होत नाही):
    export SUPABASE_DB_URL="postgresql://postgres:PASSWORD@db.xxxxx.supabase.co:5432/postgres"
    python3 test_supabase_connection.py

  पद्धत २ (थेट argument म्हणून):
    python3 test_supabase_connection.py "postgresql://postgres:PASSWORD@db.xxxxx.supabase.co:5432/postgres"

⚠️ पासवर्डमध्ये @ # % यासारखी विशेष चिन्हं असतील, तर ती URL-encode करावी लागतील
   (उदा. @ -> %40, # -> %23) — Python मध्ये असं करता येतं:
   python3 -c "import urllib.parse; print(urllib.parse.quote('तुमचा-पासवर्ड', safe=''))"
"""
import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main():
    print("=" * 60)
    print("Supabase (PostgreSQL) जोडणी — पूर्ण चाचणी")
    print("=" * 60)

    conn_url = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("SUPABASE_DB_URL")
    if not conn_url:
        print("\n❌ Connection String सापडली नाही.")
        print("   एकतर: export SUPABASE_DB_URL=\"postgresql://...\"")
        print("   किंवा: python3 test_supabase_connection.py \"postgresql://...\"")
        sys.exit(1)

    os.environ["SUPABASE_DB_URL"] = conn_url  # cloud_db.py याच पर्यावरण चलातून वाचतं
    import cloud_db

    # --- पायरी १: मूलभूत जोडणी ---
    print("\n[१/५] मूलभूत जोडणी तपासतेय...")
    conn, error_detail = cloud_db.get_connection_with_error()
    if conn is None:
        print("   ❌ अयशस्वी — खरं कारण (Supabase/psycopg2 कडून थेट):")
        print(f"      {error_detail}")
        print("\n   सामान्य कारणं:")
        print("   • Supabase free-tier project निष्क्रियतेमुळे आपोआप 'Paused' झालेला असू शकतो —")
        print("     Supabase dashboard उघडून प्रोजेक्ट Active आहे का तपासा (असल्यास 'Restore' बटण दाबा).")
        print("   • Connection String मधला password चुकीचा किंवा जुना असू शकतो.")
        print("   • Hostname/port चुकीचे असू शकतात (Supabase dashboard वरून पुन्हा कॉपी करून बघा).")
        sys.exit(1)
    conn.close()
    print("   ✅ यशस्वी — Supabase शी जोडणी झाली.")

    # --- पायरी २: Table तयार करणे ---
    print("\n[२/५] oi_diff_snapshots table तयार करतेय (नसेल तर)...")
    if cloud_db.init_cloud_table():
        print("   ✅ यशस्वी — table तयार आहे.")
    else:
        print("   ❌ अयशस्वी — table तयार करता आली नाही.")
        sys.exit(1)

    # --- पायरी ३: एक टेस्ट snapshot साठवणे ---
    print("\n[३/५] एक टेस्ट OI snapshot साठवतेय...")
    test_date = "1999-01-01"  # खऱ्या डेटाशी गल्लत होऊ नये म्हणून जुनी, स्पष्ट टेस्ट-तारीख
    saved = cloud_db.save_oi_snapshot_cloud(
        "TEST_SYMBOL", test_date, "09:00", 100000, 120000, 20000, 0, "🟢 BULLISH (Strong)",
        24500.0, 500.0, 450.0,
    )
    if saved:
        print("   ✅ यशस्वी — snapshot साठवला.")
    else:
        print("   ❌ अयशस्वी — snapshot साठवता आला नाही.")
        sys.exit(1)

    # --- पायरी ४: तोच snapshot परत वाचणे ---
    print("\n[४/५] साठवलेला snapshot परत वाचतेय...")
    history = cloud_db.get_oi_history_cloud("TEST_SYMBOL", test_date)
    if history and any(r["snapshot_time"] == "09:00" and r["diff"] == 20000 for r in history):
        print(f"   ✅ यशस्वी — {len(history)} रेकॉर्ड सापडले, डेटा तंतोतंत जुळतो.")
    else:
        print("   ❌ अयशस्वी — डेटा परत मिळाला नाही किंवा जुळत नाही.")
        sys.exit(1)

    # --- पायरी ५: डुप्लिकेट-प्रतिबंध (ON CONFLICT DO NOTHING) तपासणे ---
    print("\n[५/५] डुप्लिकेट-प्रतिबंध तपासतेय (त्याच वेळेला पुन्हा साठवण्याचा प्रयत्न)...")
    cloud_db.save_oi_snapshot_cloud(
        "TEST_SYMBOL", test_date, "09:00", 999999, 999999, 999999, 0, "बदललेला", 0, 0, 0,
    )
    history_after = cloud_db.get_oi_history_cloud("TEST_SYMBOL", test_date)
    matching = [r for r in history_after if r["snapshot_time"] == "09:00"]
    if len(matching) == 1 and matching[0]["diff"] == 20000:
        print("   ✅ यशस्वी — डुप्लिकेट तयार झाला नाही, मूळ डेटाच कायम राहिला.")
    else:
        print("   ⚠️ अनपेक्षित वर्तन — कृपया तपासा.")

    print("\n" + "=" * 60)
    print("🎉 सर्व चाचण्या यशस्वी! Cloud DB वापरासाठी पूर्ण तयार आहे.")
    print("=" * 60)
    print(f"\nपुढची पायरी: ही Connection String Streamlit Cloud च्या Secrets मध्ये आणि तुमच्या")
    print(f"local machine च्या environment variable (SUPABASE_DB_URL) मध्ये कायमची ठेवा.")
    print(f"\n(TEST_SYMBOL चा टेस्ट-डेटा Supabase मध्ये तसाच राहील — हवं असल्यास स्वतः तिथूनच मिटवू शकता,")
    print(f"किंवा तो कुठलीही खऱ्या डेटाशी गल्लत करणार नाही, कारण symbol='TEST_SYMBOL' आहे.)")


if __name__ == "__main__":
    main()
