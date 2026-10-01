"""
price_stream.py
------------------------------
🎓 "Position च्या किमती रिअल-टाइम तपासल्या पाहिजेत, म्हणजे SL सुरक्षित आणि स्लिपेज कमी" (आजचा तोटा ~३०% स्लिपेजमुळे) —
Upstox Market Data Feed V3 (WebSocket) वरून OPEN positions च्या LTP चे tick-by-tick अपडेट्स. REST polling
(दर ५ सेकंदांनी) च्या मर्यादा (Upstox rate-limits, प्रत्येक कॉलचा वेळ) या मार्गाने टळतात.

तीन तुकडे:
  • PriceStore       -- thread-safe, instrument_key -> (ltp, प्राप्त झाल्याची वेळ), feed-स्तरावरचा "शेवटचा संदेश" वेळ.
  • decode_feed_message() -- protobuf FeedResponse (upstox_feed_pb2) -> {instrument_key: ltp}.
  • FeedClient       -- websocket-client चा WebSocketApp (वेगळ्या thread मध्ये), subscription diff (sub/unsub),
                        auto-reconnect (backoff), TLS पडताळणी चालू (अधिकृत SDK च्या उलट, जो CERT_NONE वापरतो).

⚠️ हे module फक्त किमती आणतं; exit-निर्णय अजूनही `trading_engine.manage_open_trades()` मध्येच (एकमेव अधिकृत जागा) --
त्याला `live_prices` देऊन. Feed तुटला / जुना झाला तर कुणीही काहीच करत नाही -- cron चा REST `trade_monitor.py`
(दर ५ सेकंद) सुरक्षा-जाळं म्हणून चालूच राहतो.
"""
import json
import threading
import time
import uuid

import upstox_feed_pb2 as pb

FEED_URL = "wss://api.upstox.com/v3/feed/market-data-feed"


class PriceStore:
    """thread-safe LTP साठा. `last_message_at` = feed कडून कुठलाही संदेश (कुठल्याही key चा) शेवटचा आल्याची वेळ."""

    def __init__(self, clock=time.time):
        self._lock = threading.Lock()
        self._prices = {}
        self._clock = clock
        self.last_message_at = None
        self.version = 0

    def update(self, prices):
        now = self._clock()
        with self._lock:
            for key, ltp in prices.items():
                self._prices[key] = (float(ltp), now)
            self.last_message_at = now
            self.version += 1

    def touch(self):
        """किंमतीशिवाय संदेश (उदा. market_info) -- फक्त feed जिवंत असल्याची खूण."""
        with self._lock:
            self.last_message_at = self._clock()

    def snapshot(self, keys):
        """सर्व `keys` साठी किंमत असेल तर ({key: ltp}, {key: age_seconds}); एकही गहाळ असेल तर (None, None)."""
        now = self._clock()
        with self._lock:
            if any(k not in self._prices for k in keys):
                return None, None
            return ({k: self._prices[k][0] for k in keys}, {k: now - self._prices[k][1] for k in keys})

    def feed_age(self):
        """feed कडून शेवटचा संदेश किती सेकंदांपूर्वी आला (कधीच आला नसेल तर None)."""
        with self._lock:
            return None if self.last_message_at is None else self._clock() - self.last_message_at

    def clear(self):
        with self._lock:
            self._prices.clear()
            self.last_message_at = None


def _ltp_from_feed(feed):
    """एका Feed संदेशातून LTP (कुठल्याही mode मध्ये: ltpc / full / option_greeks) -- नसेल तर None."""
    which = feed.WhichOneof("FeedUnion")
    ltpc = None
    if which == "ltpc":
        ltpc = feed.ltpc
    elif which == "fullFeed":
        full = feed.fullFeed
        inner = full.WhichOneof("FullFeedUnion")
        if inner == "marketFF":
            ltpc = full.marketFF.ltpc
        elif inner == "indexFF":
            ltpc = full.indexFF.ltpc
    elif which == "firstLevelWithGreeks":
        ltpc = feed.firstLevelWithGreeks.ltpc
    if ltpc is None or not ltpc.ltp:
        return None
    return float(ltpc.ltp)


def decode_feed_message(buffer):
    """protobuf bytes -> {instrument_key: ltp}. ओळखता न येणारा/रिकामा संदेश -> {} (कधीच exception नाही)."""
    try:
        response = pb.FeedResponse.FromString(buffer)
    except Exception:
        return {}
    prices = {}
    for key, feed in response.feeds.items():
        ltp = _ltp_from_feed(feed)
        if ltp is not None:
            prices[key] = ltp
    return prices


def build_request(keys, method, mode=None):
    """Upstox च्या अपेक्षेनुसार binary(UTF-8 JSON) subscribe/unsubscribe विनंती (अधिकृत SDK सारखीच)."""
    payload = {"guid": str(uuid.uuid4()), "method": method, "data": {"instrumentKeys": sorted(keys)}}
    if mode is not None:
        payload["data"]["mode"] = mode
    return json.dumps(payload).encode("utf-8")


class FeedClient:
    """WebSocket thread + subscription व्यवस्थापन. `connect_fn(url, headers, handlers)` फक्त टेस्टसाठी बदलता येतं."""

    def __init__(self, token_provider, store, url=FEED_URL, mode="ltpc", log=print,
                 connect_fn=None, sleep_fn=time.sleep, max_backoff=30.0):
        self._token_provider = token_provider
        self.store = store
        self.url = url
        self.mode = mode
        self._log = log
        self._connect_fn = connect_fn or self._default_connect
        self._sleep = sleep_fn
        self._max_backoff = max_backoff
        self._wanted = set()          # आपल्याला हव्या असलेल्या keys
        self._subscribed = set()      # प्रत्यक्ष feed कडे subscribe केलेल्या keys
        self._lock = threading.Lock()
        self._ws = None
        self._connected = False
        self._stop = threading.Event()
        self._thread = None
        self.reconnects = 0

    # ---- सार्वजनिक ----
    @property
    def connected(self):
        return self._connected

    def start(self):
        self._thread = threading.Thread(target=self._run_forever, name="price-feed", daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        ws = self._ws
        if ws is not None:
            try:
                ws.close()
            except Exception:
                pass

    def set_subscriptions(self, keys):
        """हव्या असलेल्या keys चा संच बदला; connected असेल तर लगेच फरकापुरते sub/unsub पाठवतो."""
        with self._lock:
            self._wanted = set(keys)
        self._sync()

    def healthy(self, max_feed_age=5.0):
        age = self.store.feed_age()
        return bool(self._connected and age is not None and age <= max_feed_age)

    # ---- अंतर्गत ----
    def _send(self, payload):
        ws = self._ws
        if ws is None:
            raise RuntimeError("WebSocket is not open")
        ws.send(payload, opcode=0x2)  # binary

    def _sync(self):
        if not self._connected:
            return
        with self._lock:
            to_add = self._wanted - self._subscribed
            to_remove = self._subscribed - self._wanted
        try:
            if to_add:
                self._send(build_request(to_add, "sub", self.mode))
            if to_remove:
                self._send(build_request(to_remove, "unsub"))
        except Exception as exc:
            self._log(f"⚠️ Feed subscription पाठवता आलं नाही: {exc}")
            return
        with self._lock:
            self._subscribed = (self._subscribed | to_add) - to_remove

    def _on_open(self, ws):
        self._ws = ws
        self._connected = True
        with self._lock:
            self._subscribed = set()   # नवीन connection -- सर्व पुन्हा subscribe
        self._sync()

    def _on_message(self, ws, message):
        if isinstance(message, str):
            message = message.encode("utf-8")
        prices = decode_feed_message(message)
        if prices:
            self.store.update(prices)
        else:
            self.store.touch()

    def _on_close(self, ws, code=None, reason=None):
        self._connected = False

    def _on_error(self, ws, error):
        self._log(f"⚠️ Price feed त्रुटी: {error}")

    def _default_connect(self, url, headers, handlers):
        import websocket  # websocket-client
        app = websocket.WebSocketApp(
            url, header=headers, on_open=handlers["open"], on_message=handlers["message"],
            on_error=handlers["error"], on_close=handlers["close"],
        )
        # TLS पडताळणी चालू (डीफॉल्ट); ping ने मृत connection लवकर ओळखला जातो.
        app.run_forever(ping_interval=10, ping_timeout=5)

    def _run_forever(self):
        backoff = 1.0
        while not self._stop.is_set():
            token = None
            try:
                token = self._token_provider()
            except Exception as exc:
                self._log(f"⚠️ Upstox token मिळाला नाही: {exc}")
            if token:
                started = time.monotonic()
                headers = [f"Authorization: Bearer {str(token).strip()}", "Accept: */*"]
                handlers = {"open": self._on_open, "message": self._on_message,
                            "error": self._on_error, "close": self._on_close}
                try:
                    self._connect_fn(self.url, headers, handlers)
                except Exception as exc:
                    self._log(f"⚠️ Price feed connect अयशस्वी: {exc}")
                self._connected = False
                self.store.clear()          # जुन्या किमती पुढच्या connection वर कधीच वापरू नयेत
                if time.monotonic() - started > 30:
                    backoff = 1.0           # बराच वेळ टिकलेला connection होता -- backoff रीसेट
            if self._stop.is_set():
                break
            self.reconnects += 1
            self._sleep(backoff)
            backoff = min(backoff * 2, self._max_backoff)
