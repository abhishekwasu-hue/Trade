"""
migrate_nifty_1min_to_supabase.py
------------------------------------------
🎓 वापरकर्त्याशी चर्चा करून बांधलेली सुधारणा — established parquet file (data/nifty50_1min.parquet,
2015-01-09 ते 2024-03-27, ~८,५२,००० candles) मधला संपूर्ण इतिहास, एकदाच, Supabase च्या
nifty_1min_ohlc table मध्ये चढवणे (batch-insert, ON CONFLICT DO NOTHING मुळे पुन्हा चालवलं तरी
सुरक्षित/idempotent).

⚠️ ही script **एकदाच** चालवायची आहे (एक-वेळचं migration) — रोजचं अद्ययावतीकरण
`daily_nifty_1min_update.py` (वेगळी script) करते.

चालवणे:
    python3 migrate_nifty_1min_to_supabase.py
"""
import cloud_db
from real_nifty_data import load_nifty_1min

BATCH_SIZE = 5000  # 🎓 एकाच वेळी सर्व ८,५२,०००+ रांगा पाठवणं अव्यवहार्य (मोठा memory/network payload) --
                    # छोट्या batches मध्ये विभागून, प्रत्येक batch नंतर प्रगती दाखवत पुढे जाणे.


def migrate():
    cloud_db.init_cloud_table()
    df = load_nifty_1min()
    if df.empty:
        print("❌ स्थानिक parquet file रिकामी/सापडली नाही — data/nifty50_1min.parquet तपासा.")
        return False

    total = len(df)
    print(f"एकूण {total:,} candles migrate करायच्या आहेत...")

    for start in range(0, total, BATCH_SIZE):
        chunk = df.iloc[start:start + BATCH_SIZE]
        rows = chunk.to_dict("records")
        ok = cloud_db.save_nifty_1min_batch(rows)
        if not ok:
            print(f"❌ Batch {start}-{start + len(chunk)} साठवताना अडचण आली — थांबतोय.")
            return False
        done = min(start + BATCH_SIZE, total)
        print(f"  {done:,}/{total:,} ({done * 100 // total}%) पूर्ण")

    print("✅ Migration पूर्ण झालं.")
    return True


if __name__ == "__main__":
    migrate()
