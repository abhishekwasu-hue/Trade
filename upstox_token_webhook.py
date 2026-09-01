"""
upstox_token_webhook.py
------------------------------
🎓 वापरकर्त्याशी चर्चा करून बांधलेली सुधारणा — Upstox च्या अधिकृत "Access Token Request + Notifier
Webhook" पद्धतीने, रोज एका मोबाईल टॅपवर मिळणारा नवीन token इथेच स्वीकारून Supabase मध्ये साठवणे —
जेणेकरून GitHub Actions आणि Streamlit Dashboard दोन्ही तिथूनच वाचू शकतील, कुठेही मॅन्युअल paste
लागणार नाही.

हे VPS वर सतत (persistently) चालणारं असायला हवं — systemd service म्हणून सेटअप करा (सूचना खाली).

Upstox च्या अधिकृत payload schema नुसार (Notifier Webhook Endpoint दस्तऐवजीकरण):
{
    "client_id": "...", "user_id": "...", "access_token": "...", "token_type": "Bearer",
    "expires_at": "...", "issued_at": "...", "message_type": "access_token"
}
⚠️ Upstox च्या दस्तऐवजीकरणानुसार — हा endpoint authentication शिवाय (No Auth) असायला हवा, आणि
plain string किंवा JSON object ने प्रतिसाद द्यायला हवा (आपण JSON देतो).
"""
from flask import Flask, request, jsonify

import cloud_db

app = Flask(__name__)


@app.route("/upstox-webhook", methods=["POST"])
def receive_upstox_token():
    """
    Upstox कडून (वापरकर्त्याने मोबाईलवर Approve केल्यावर) येणारा POST स्वीकारणे, त्यातला access_token
    काढून Supabase मध्ये साठवणे.
    """
    try:
        payload = request.get_json(force=True, silent=True) or {}
    except Exception:
        payload = {}

    access_token = payload.get("access_token")
    message_type = payload.get("message_type")

    if not access_token:
        return jsonify({"status": "error", "message": "access_token सापडला नाही payload मध्ये"}), 400

    saved = cloud_db.save_upstox_token(access_token)
    if saved:
        return jsonify({"status": "success", "message": "Token यशस्वीरित्या साठवला", "message_type": message_type}), 200
    else:
        return jsonify({"status": "error", "message": "Token साठवता आला नाही (Supabase जोडणी तपासा)"}), 500


@app.route("/health", methods=["GET"])
def health_check():
    """VPS वरून सतत चालू आहे का हे तपासण्यासाठी (उदा. curl http://localhost:8080/health)."""
    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
