from flask import Flask, request, jsonify
import os
import requests
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

PORT = int(os.getenv("PORT", "5000"))
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()

# Filtre Bible
MIN_RR = float(os.getenv("MIN_RR", "2.25"))

# Si tu veux ignorer les signaux sans entry/sl/tp (Option 1 strict)
STRICT_TV_LEVELS = os.getenv("STRICT_TV_LEVELS", "true").lower() == "true"


def send_telegram_message(text: str) -> tuple[bool, str]:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return False, "TELEGRAM_BOT_TOKEN ou TELEGRAM_CHAT_ID manquant dans .env"

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text}

    try:
        r = requests.post(url, json=payload, timeout=10)
        ok = (r.status_code == 200)
        return ok, r.text
    except Exception as e:
        return False, str(e)


@app.get("/")
def home():
    return "GoldMaster server OK ✅", 200


def _to_float_or_none(x):
    try:
        if x is None:
            return None
        # TradingView peut envoyer des nombres comme string
        return float(x)
    except Exception:
        return None


@app.post("/signal")
def signal():
    data = request.get_json(force=True, silent=True) or {}

    # Champs de base
    decision = (data.get("decision") or "").upper()
    symbol = data.get("symbol") or "UNKNOWN"
    tf = data.get("tf") or "?"
    version = data.get("v") or "GM"
    macro = data.get("macro") or ""  # optionnel

    if decision not in ["BUY", "SELL"]:
        return jsonify({"status": "ignored", "reason": "no decision"}), 200

    # Option 1 : on attend les niveaux DIRECTEMENT de TradingView
    entry = _to_float_or_none(data.get("entry"))
    sl = _to_float_or_none(data.get("sl"))
    tp = _to_float_or_none(data.get("tp"))
    rr = _to_float_or_none(data.get("rr"))

    if STRICT_TV_LEVELS:
        # Si TradingView n'envoie pas les niveaux -> on ignore (Option 1 strict)
        missing = []
        if entry is None: missing.append("entry")
        if sl is None: missing.append("sl")
        if tp is None: missing.append("tp")
        if rr is None: missing.append("rr")
        if missing:
            return jsonify({"status": "ignored", "reason": f"missing fields: {','.join(missing)}"}), 200
    else:
        # Si tu désactives le strict, on accepte mais on n'envoie pas si incomplet
        if entry is None or sl is None or tp is None:
            return jsonify({"status": "ignored", "reason": "missing entry/sl/tp"}), 200

    # Recalcule RR au cas où rr est absent/incorrect (sécurité)
    rr_calc = None
    if entry is not None and sl is not None and tp is not None:
        if decision == "BUY":
            risk = entry - sl
            reward = tp - entry
        else:  # SELL
            risk = sl - entry
            reward = entry - tp

        if risk is not None and risk > 0:
            rr_calc = reward / risk

    # Choix du RR final pour filtrer
    rr_final = rr if (rr is not None and rr > 0) else rr_calc

    if rr_final is None:
        return jsonify({"status": "ignored", "reason": "RR not computable"}), 200

    if rr_final < MIN_RR:
        return jsonify({"status": "ignored", "reason": f"RR<{MIN_RR}", "rr": rr_final}), 200

    # Format Telegram (clair)
    msg = (
        f"🟡 GOLD MASTER {version}\n"
        f"{symbol} — TF {tf}\n"
        f"DECISION: {decision}\n"
        f"{macro}\n\n"
        f"📍 Entry : {entry:.2f}\n"
        f"🛑 SL    : {sl:.2f}\n"
        f"🎯 TP    : {tp:.2f}\n"
        f"📐 RR    : {rr_final:.2f}R"
    )

    ok, info = send_telegram_message(msg)

    return jsonify({
        "status": "sent" if ok else "error",
        "decision": decision,
        "symbol": symbol,
        "tf": tf,
        "entry": entry,
        "sl": sl,
        "tp": tp,
        "rr": rr_final,
        "telegram_info": info
    }), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT, debug=True)
