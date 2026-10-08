"""chart_reader/setups.py — एक setup = एक entry (TRADE_KB_FULL_IMPLEMENTATION_PROMPT §8.3).

`evaluate` stateless आहे (प्रत्येक bar स्वतंत्र). "त्याच correction वर आधी entry झाली का" हे caller (backtest scan / live loop) ठेवतो:

    tr = SetupTracker()
    for each closed bar:  r = evaluate(...);  tr.on_bar(bar);  tr.apply(r)

  • setup key = त्याच correction ची ओळख: impulse (सुरुवात / शेवट वेळ) + correction चा A (वेळ). नवा correction (नवा A / नवा impulse) ⇒ नवी key.
  • त्या key वर पहिली valid entry ⇒ नोंद; पुढचे candidates `DUP_SETUP` (entry नाही), जोपर्यंत ती entry ची invalidation (spot) तुटत नाही
    किंवा नवा correction सुरू होत नाही. Invalidation तुटली ⇒ key मोकळी (correction लांबला ⇒ नव्या C-end वर पुन्हा संधी).
  • हा नियम gap / zone / पक्क्या नियमांनंतर लागतो: फक्त अन्यथा valid entry च "पहिली" ठरते (7 Oct 09:30 gap chase पहिली ठरत नाही).
"""


def setup_key(r):
    """evaluate निकाल ⇒ correction ची ओळख (tuple) / None."""
    ms = r.get("market_state") or {}
    imp, corr = ms.get("impulse") or {}, ms.get("correction") or {}
    if not imp:
        return None
    labels = corr.get("labels") or []
    a = next((lb for lb in labels if str(lb.get("label") or "").upper().startswith("A")), None)
    a_ts = str((a or {}).get("to_ts") or "")                              # A चं टोक (A leg चा शेवट)
    return (str(imp.get("from_ts")), str(imp.get("to_ts")), int(r.get("side") or 0), a_ts)


class SetupTracker:
    def __init__(self):
        self.used = {}                         # key ⇒ {"inv", "side", "at"}

    def on_bar(self, high, low):
        """नवा बंद bar: ज्या entries ची invalidation तुटली त्यांच्या keys मोकळ्या."""
        for k in list(self.used):
            u = self.used[k]
            if (u["side"] < 0 and high >= u["inv"]) or (u["side"] > 0 and low <= u["inv"]):
                del self.used[k]

    def apply(self, r):
        """valid entry असेल तर: key आधी वापरली ⇒ entry रद्द + `DUP_SETUP`; नाहीतर नोंद. r बदलतो आणि परत देतो."""
        key = setup_key(r)
        r["setup_key"] = key
        if not r.get("entry") or key is None:
            return r
        if key in self.used:
            u = self.used[key]
            r["entry"] = False
            r["why_no_entry"] = list(r.get("why_no_entry") or []) + [
                f"DUP_SETUP — याच correction वर {u['at']} ला entry झाली (invalidation {u['inv']:,.1f} अबाधित) ⇒ नवी entry नाही"]
            return r
        inv = (r.get("risk") or {}).get("invalidation")
        side = int(r.get("side") or 0)
        self.used[key] = {"inv": float(inv) if inv is not None else (float("-inf") if side > 0 else float("inf")),
                          "side": side, "at": str(r.get("asof"))[11:16]}
        return r


class LineMemory:
    """Trendline स्थिर ओळख (Abhi 2026-10-08 (b)): scan / live loop मध्ये bar-दर-bar रेषा लक्षात. evaluate(..., memory=LineMemory())."""

    def __init__(self):
        self.lines = {}                        # role ⇒ {"anchors": [a0, a1], "id"}
        self.log = []                          # [(asof, role, कारण)] — फक्त बदल / पहिली निवड

    def keep(self):
        return {role: v["anchors"] for role, v in self.lines.items()}

    def update(self, asof, cands):
        for z in cands or []:
            if z.get("tool") != "f" or not z.get("tl_reason"):
                continue
            role = z.get("role")
            prev = self.lines.get(role)
            self.lines[role] = {"anchors": list(z.get("pair") or z["anchors"][:2]), "id": z["id"]}
            if prev is None or prev["id"] != z["id"]:
                self.log.append((str(asof), role, z["tl_reason"]))
