"""
refresh_market_structure_intraday.py
------------------------------------
बाजार सत्रात, प्रत्येक closed 15M bar नंतर Structure Journal (1H/15M state, events, zone mitigation, gap status) ताजा करणे — refresh_market_structure.py (EOD) चाच logic, पण
लहान lookback आणि बाजार-वेळेची मर्यादा. स्वतंत्र script (refresh_market_zones_intraday.py सारखं) जेणेकरून EOD चालवण्यावर परिणाम नाही. कुठलाही order नाही.

    python3 refresh_market_structure_intraday.py [--force]    # --force: बाजार-वेळेबाहेरही चालवा (चाचणी)
"""
import datetime
import sys

import pytz

import refresh_market_structure as eod

IST = pytz.timezone("Asia/Kolkata")


def market_is_open(now=None):
    """सोम–शुक्र, 09:30–15:35 IST (शेवटचा 15M bar 15:30 ला बंद होतो; त्यानंतर EOD script)."""
    now = now or datetime.datetime.now(IST)
    return now.weekday() < 5 and datetime.time(9, 30) <= now.time() <= datetime.time(15, 35)


def main(argv=None, now=None, fetch_fn=eod.fetch, store_mod=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    force = "--force" in argv
    argv = [a for a in argv if a != "--force"]
    if not force and not market_is_open(now):
        print("⏸️ बाजार बंद — intraday refresh वगळला (--force ने चालवता येतो).")
        return 0
    return eod.main(argv, mode="intraday", fetch_fn=fetch_fn, store_mod=store_mod)


if __name__ == "__main__":
    sys.exit(main())
