"""
log_setup.py
--------------------
केंद्रीभूत rotating-file logger. 🎓 Production-readiness सुधारणा — याआधी बहुतांश ठिकाणी
`except Exception: pass` (किंवा तत्सम) वापरून अपयश हेतुपुरस्सर गप्प गिळलं जायचं (resilience साठी —
एका मॉड्यूलचं अपयश संपूर्ण dashboard/script थांबवू नये म्हणून). हे तत्त्व तसंच कायम ठेवत, आता
प्रत्येक असा except block किमान `get_logger(__name__).exception(...)` कॉल करतो — script/dashboard
आधीसारखाच थांबत नाही, पण अपयश आता `data/app.log` मध्ये (traceback सकट, आपोआप rotate होणाऱ्या
फाईलमध्ये) नोंदवलं जातं आणि शोधण्यायोग्य राहतं (आधी पूर्णपणे अदृश्य होतं).
"""
import logging
import logging.handlers
import os

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(_BASE_DIR, "data", "app.log")

_configured = False


def get_logger(name):
    """दिलेल्या module/script साठी logger परत करणे. पहिल्यांदाच बोलावल्यावर एकदाच rotating file
    handler सेट होतो (५ MB प्रति फाईल, ३ जुन्या फाईल्स ठेवल्या जातात) — नंतर सर्व मॉड्यूल्स तोच
    शेअर करतात (प्रत्येकाचं स्वतःचं वेगळं नाव — logger tree द्वारे)."""
    global _configured
    root = logging.getLogger("amw_a1")
    if not _configured:
        try:
            os.makedirs(os.path.join(_BASE_DIR, "data"), exist_ok=True)
            handler = logging.handlers.RotatingFileHandler(
                LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8",
            )
            handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s"))
            root.addHandler(handler)
            root.setLevel(logging.INFO)
        except Exception:
            pass  # log फाईल सेटअप अयशस्वी झाली (उदा. read-only filesystem) तरी काहीही क्रॅश होऊ नये
        _configured = True
    return root.getChild(name)
