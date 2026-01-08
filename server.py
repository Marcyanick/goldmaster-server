from flask import Flask, request, jsonify
import os, requests

app = Flask(__name__)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID")

def tg_send(text: str):
    if not BOT_TOKEN or not CHAT_ID:
        print("❌ Missing TELEGRAM env vars")
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": CHAT_ID, "text": text}, timeout=10)

@app.post("/signal")
def signal():
    payload = request.get_json(silent=True) or {}
    print("📩 payload:", payload)

    strategy = str(payload.get("strategy", "")).strip()
    event    = str(payload.get("event", "")).strip()
    symbol   = str(payload.get("symbol", payload.get("ticker", ""))).strip()
    tf       = str(payload.get("tf", payload.get("interval", ""))).strip()
    price    = str(payload.get("price", payload.get("close", ""))).strip()
    t        = str(payload.get("time", "")).strip()

    # ✅ BYPASS FILTER for GoldMasterFVG
    if strategy.lower() == "goldmasterfvg":
        msg = f"🟡 GoldMasterFVG\n🔔 {event or 'ALERT'}\n📊 {symbol} ({tf})\n💰 {price}\n🕒 {t}"
        tg_send(msg)
        return jsonify({"ok": True, "mode": "FVG", "sent": True}), 200

    # 👇 Old GoldMaster v6.6 logic (keep it if you still want)
    decision = payload.get("decision")
    if not decision:
        return jsonify({"reason": "no decision", "status": "ignored"}), 200

    # example: send decision-based message
    msg = f"🟦 GoldMaster\n✅ {decision}\n📊 {symbol} ({tf})\n💰 {price}\n🕒 {t}"
    tg_send(msg)
    return jsonify({"ok": True, "mode": "GM", "sent": True}), 200

