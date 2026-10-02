"""
position_stream_monitor.py
------------------------------
🎓 "OPEN positions च्या किमती रिअल-टाइम तपासल्या पाहिजेत, म्हणजे SL सुरक्षित आणि स्लिपेज कमी" -- आजचा तोटा ~३०%
स्लिपेजमुळे (SL threshold -0.07% असताना exit -0.12% वर, वेगवान घसरणीत). REST polling (दर ५ सेकंद) ऐवजी Upstox Market
Data Feed V3 (WebSocket) वरून tick-by-tick किमती; प्रत्येक बदलावर (कमाल दर ०.५ सेकंदाला) तोच एकमेव अधिकृत exit-logic
(`trade_monitor.run_monitor_cycle` -> `trading_engine.manage_open_trades`) `live_prices` देऊन चालवला जातो.

सुरक्षा-रचना:
  • हे ADDITIVE आहे -- cron चा `trade_monitor.py` (REST, दर ५ सेकंद) जसाच्या तसा चालू राहतो. Feed तुटला/जुना झाला/ही
    service बंद असली तरी SL/Target/EOD तपासणी थांबत नाही. दोघे एकाच वेळी exit करू शकत नाहीत (`position_exit_monitor`
    ProcessLock प्रत्येक cycle भोवती + order आधी DB status पुन्हा तपासला जातो).
  • Feed "healthy" तेव्हाच जेव्हा connected आणि शेवटचा संदेश <= `--max-feed-age` सेकंदांपूर्वी, आणि सर्व हव्या keys
    (OPEN trades चे सर्व legs + स्पॉट index) साठी किमान एक किंमत आलेली. नाहीतर या cycle ला काहीही नाही (REST monitor
    करतो).
  • LIVE positions: reconciliation/broker-MTM इथे नाही (positions=[]), ती cron च्या REST monitor कडेच; इथे किमतींवरून
    internal P&L.
  • बाजार-वेळेच्या बाहेर काहीच करत नाही; OPEN trade नसताना कुठलीही subscription नाही.

चालवणे (VPS वर, systemd: deploy/position_stream_monitor.service):
    python3 position_stream_monitor.py
    python3 position_stream_monitor.py --min-cycle-interval 0.5 --max-feed-age 5
    python3 position_stream_monitor.py --market mcx     # MCX Futures साठी (वेगळी service: position_stream_monitor_mcx)
"""
import argparse
import time

import cloud_db
import database
from config import is_market_open, is_mcx_market_open
from engine_service import MONITORED_SYMBOLS
from notifications import notify_error, write_heartbeat
from price_stream import FeedClient, PriceStore
from process_lock import ProcessLock, ProcessLockHeld
import trade_monitor
from upstox_api import get_instrument_key

SCRIPT_NAME = "position_stream_monitor"


def collect_needed_keys(symbols, keys_fn=None, spot_key_fn=None):
    """OPEN trades चे सर्व legs + त्या symbols चे स्पॉट index keys."""
    keys_fn = keys_fn or database.get_open_trade_instrument_keys
    spot_key_fn = spot_key_fn or get_instrument_key
    keys = set(keys_fn(list(symbols)))
    keys.update(k for k in (spot_key_fn(s) for s in symbols) if k)  # MCX futures ला वेगळा स्पॉट index नाही (None)
    return keys


def _make_mcx_cycle():
    """🎓 "mcx open trade sathi real time websocket use kra" -- MCX Futures साठी तोच stream monitor (--market mcx): OPEN MCX trades
    च्या futures legs च्या किमती WebSocket वरून, आणि तोच एकमेव अधिकृत MCX exit-logic (`mcx_futures_trader.run_exit_monitor_cycle`
    -> `manage_open_trades`) `live_prices` देऊन. रिटर्न: (MCX symbols, cycle_fn)."""
    import mcx_futures_trader

    symbols = list(mcx_futures_trader.MCX_FUTURES_SYMBOLS)

    def cycle(token, product_type, live_prices=None, live_price_age=None, heartbeat=False):
        results, _ok = mcx_futures_trader.run_exit_monitor_cycle(
            token, symbols, live_prices=live_prices, live_price_age=live_price_age,
        )
        return "\n".join(results)

    return symbols, cycle


def build_market(market):
    """--market nse (डीफॉल्ट, जुनं वर्तन) किंवा mcx. रिटर्न: StreamMonitor/main साठी सेटिंग्जची dict."""
    if market == "mcx":
        symbols, cycle = _make_mcx_cycle()
        return {
            "symbols": symbols, "cycle_fn": cycle, "market_open_fn": is_mcx_market_open, "spot_key_fn": lambda s: None,
            "script_name": "position_stream_monitor_mcx", "lock_name": "position_stream_monitor_mcx_singleton",
        }
    return {
        "symbols": list(MONITORED_SYMBOLS), "cycle_fn": None, "market_open_fn": None, "spot_key_fn": None,
        "script_name": SCRIPT_NAME, "lock_name": "position_stream_monitor_singleton",
    }


class StreamMonitor:
    def __init__(self, token_provider, client, store, cycle_fn=None, modes_fn=None, market_open_fn=None,
                 keys_fn=None, spot_key_fn=None, min_cycle_interval=0.5, force_interval=2.0, max_feed_age=5.0,
                 clock=time.monotonic, log=print, symbols=None):
        self._symbols = list(symbols) if symbols else list(MONITORED_SYMBOLS)
        self._token_provider = token_provider
        self.client = client
        self.store = store
        self._cycle_fn = cycle_fn or trade_monitor.run_monitor_cycle
        self._modes_fn = modes_fn or (lambda: database.get_open_trade_modes_by_symbol(self._symbols))
        self._market_open_fn = market_open_fn or is_market_open
        self._keys_fn = keys_fn
        self._spot_key_fn = spot_key_fn
        self.min_cycle_interval = min_cycle_interval
        self.force_interval = force_interval
        self.max_feed_age = max_feed_age
        self._clock = clock
        self._log = log
        self._last_version = None
        self._last_cycle_at = None
        self.cycles = 0

    def step(self):
        """एक पायरी. रिटर्न: स्थिती-स्ट्रिंग (टेस्ट/लॉगसाठी)."""
        if not self._market_open_fn():
            self.client.set_subscriptions([])
            return "market-closed"
        modes = self._modes_fn()
        symbols = [s for s in self._symbols if s in modes]
        if not symbols:
            self.client.set_subscriptions([])
            return "idle"
        needed = collect_needed_keys(symbols, self._keys_fn, self._spot_key_fn)
        self.client.set_subscriptions(needed)
        if not self.client.healthy(self.max_feed_age):
            return "feed-unhealthy"
        prices, ages = self.store.snapshot(needed)
        if prices is None:
            return "waiting-first-ticks"
        now = self._clock()
        since_last = None if self._last_cycle_at is None else now - self._last_cycle_at
        changed = self.store.version != self._last_version
        if since_last is not None and (
            since_last < self.min_cycle_interval or (not changed and since_last < self.force_interval)
        ):
            return "skipped"
        token = self._token_provider()
        if not token:
            return "no-token"
        self._last_version = self.store.version
        self._last_cycle_at = now
        result = self._cycle_fn(token, "D", live_prices=prices, live_price_age=ages, heartbeat=False)
        self.cycles += 1
        if result and "बंद" in str(result):
            self._log(result)
        return "cycle"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--token", default=None)
    parser.add_argument("--min-cycle-interval", type=float, default=0.5,
                        help="दोन exit-तपासण्यांमधलं किमान अंतर (सेकंद), किंमत बदलल्यावर. डीफॉल्ट 0.5.")
    parser.add_argument("--force-interval", type=float, default=2.0,
                        help="किंमत न बदलताही (वेळेवर आधारित नियम, उदा. EOD, साठी) किमान इतक्या सेकंदांनी तपासणी. डीफॉल्ट 2.")
    parser.add_argument("--max-feed-age", type=float, default=5.0,
                        help="feed कडून शेवटचा संदेश यापेक्षा जुना असेल तर feed 'unhealthy'. डीफॉल्ट 5.")
    parser.add_argument("--market", choices=["nse", "mcx"], default="nse",
                        help="nse (डीफॉल्ट: NIFTY/BANKNIFTY/SENSEX) किंवा mcx (MCX Futures: CRUDEOIL/NATURALGAS/GOLD/SILVER/COPPER).")
    args = parser.parse_args()
    market_cfg = build_market(args.market)

    from read_cache import install_monitor_read_cache
    install_monitor_read_cache(cloud_db)

    def token_provider():
        return cloud_db.get_effective_upstox_token(args.token)

    if not token_provider():
        print("❌ कुठलाही Upstox token उपलब्ध नाही.")
        raise SystemExit(1)

    try:
        with ProcessLock(market_cfg["lock_name"]):
            store = PriceStore()
            client = FeedClient(token_provider, store)
            monitor = StreamMonitor(token_provider, client, store, cycle_fn=market_cfg["cycle_fn"],
                                    market_open_fn=market_cfg["market_open_fn"], spot_key_fn=market_cfg["spot_key_fn"],
                                    symbols=market_cfg["symbols"], min_cycle_interval=args.min_cycle_interval,
                                    force_interval=args.force_interval, max_feed_age=args.max_feed_age)
            client.start()
            last_status, last_beat = None, 0.0
            print(f"▶️ Position stream monitor सुरू (WebSocket feed, {args.market.upper()})")
            while True:
                try:
                    status = monitor.step()
                except Exception as exc:  # एका चुकीमुळे service थांबू नये
                    status = "error"
                    notify_error(market_cfg["script_name"], str(exc))
                if status != last_status:
                    print(f"[{time.strftime('%H:%M:%S')}] status: {status}")
                    last_status = status
                if time.time() - last_beat > 30:
                    write_heartbeat(market_cfg["script_name"])
                    last_beat = time.time()
                time.sleep(0.2)
    except ProcessLockHeld:
        print("⏭️ दुसरी position_stream_monitor instance आधीच चालू आहे -- ही बाहेर पडते.")


if __name__ == "__main__":
    main()
