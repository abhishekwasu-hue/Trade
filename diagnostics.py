"""System health checks: PDF dependency availability and the combined 'ready to trade' diagnostics runner."""
import datetime
import os

from upstox_api import get_available_margin, get_static_ip_proxy_url, check_proxy_egress_ip, get_registered_static_ips
from database import check_database_health, get_data_freshness

def check_pdf_dependencies():
    """PDF रिपोर्टसाठी लागणारी kaleido व reportlab पॅकेजेस उपलब्ध आहेत का तपासणे."""
    result = {}
    try:
        import kaleido  # noqa: F401
        result["kaleido"] = True
    except ImportError:
        result["kaleido"] = False
    try:
        import reportlab  # noqa: F401
        result["reportlab"] = True
    except ImportError:
        result["reportlab"] = False
    _font_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")
    result["fonts_present"] = os.path.exists(os.path.join(_font_dir, "DejaVuSans.ttf"))
    return result

def run_system_diagnostics(access_token, symbol):
    """वरील सर्व तपासण्या एकत्र चालवून एक संपूर्ण ✅/❌ रिपोर्ट तयार करणे — रोज ट्रेडिंग सुरू करण्याआधी वापरण्यासाठी."""
    diagnostics = {"checked_at": (datetime.datetime.utcnow() + datetime.timedelta(hours=5, minutes=30)).strftime("%Y-%m-%d %H:%M:%S IST")}

    # १. Token Validity — आधीच verified असलेला funds endpoint वापरणे (नवीन endpoint गृहीत धरण्याऐवजी)
    margin = get_available_margin(access_token)
    diagnostics["token_valid"] = margin is not None

    # २. Static IP Proxy
    proxy_url = get_static_ip_proxy_url()
    diagnostics["proxy_configured"] = proxy_url is not None
    if proxy_url:
        egress_ip = check_proxy_egress_ip(proxy_url)
        registered = get_registered_static_ips(access_token)
        diagnostics["proxy_ip_match"] = (
            egress_ip is not None and registered is not None
            and egress_ip in {registered.get("primary_ip"), registered.get("secondary_ip")}
        )
    else:
        diagnostics["proxy_ip_match"] = None  # लागू नाही

    # ३. Database Health
    diagnostics["db_health"] = check_database_health()

    # ४. PDF Dependencies
    diagnostics["pdf_deps"] = check_pdf_dependencies()

    # ५. Data Freshness
    diagnostics["data_freshness"] = get_data_freshness(symbol)

    return diagnostics
