"""
trigger_upstox_token_request.py
--------------------------------------
🎓 वापरकर्त्याशी चर्चा करून बांधलेली सुधारणा — रोज सकाळी (VPS वरच्या cron ने) Upstox ला "आजचा token हवा"
अशी विनंती पाठवणे — यामुळे वापरकर्त्याच्या मोबाईलवर Upstox app मध्ये notification येते, जिथे एका
टॅपने Approve केलं की token आपोआप upstox_token_webhook.py कडे (आणि तिथून Supabase मध्ये) पोहोचतो.

⚠️ यासाठी Upstox Developer Console मध्ये App बनवताना मिळालेले CLIENT_ID (API Key) आणि CLIENT_SECRET
(API Secret) लागतात — access_token नाही (तो रोज बदलणारा असतो, हे कायम राहणारे असतात).
"""
import os
import sys

import requests


def trigger_token_request(client_id, client_secret):
    """
    Upstox च्या अधिकृत Access Token Request API ला कॉल करून, वापरकर्त्याच्या मोबाईलवर approval-request
    पाठवणे. रिटर्न: (यशस्वी_का, संदेश).
    """
    url = f"https://api.upstox.com/v3/login/auth/token/request/{client_id}"
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    body = {"client_secret": client_secret}
    try:
        response = requests.post(url, headers=headers, json=body, timeout=15)
        data = response.json()
        if response.status_code == 200 and data.get("status") == "success":
            expiry = data.get("data", {}).get("authorization_expiry")
            return True, f"विनंती यशस्वीरित्या पाठवली — मोबाईलवर Upstox app मध्ये Approve करा (मुदत: {expiry})"
        else:
            error_msg = data.get("errors", [{}])[0].get("message", "अज्ञात चूक")
            return False, f"अयशस्वी — {error_msg}"
    except Exception as exc:
        return False, f"विनंती पाठवताना चूक: {exc}"


if __name__ == "__main__":
    client_id = os.environ.get("UPSTOX_CLIENT_ID")
    client_secret = os.environ.get("UPSTOX_CLIENT_SECRET")
    if not client_id or not client_secret:
        print("❌ UPSTOX_CLIENT_ID आणि UPSTOX_CLIENT_SECRET environment variables हव्यात (.env मध्ये जोडा)")
        sys.exit(1)

    success, message = trigger_token_request(client_id, client_secret)
    print(("✅ " if success else "❌ ") + message)
    sys.exit(0 if success else 1)
