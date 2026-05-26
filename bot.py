import os
import hmac
import hashlib
import time
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# ═══ CONFIG ═══
BYBIT_API_KEY    = os.environ.get("BYBIT_API_KEY", "")
BYBIT_API_SECRET = os.environ.get("BYBIT_API_SECRET", "")
TELEGRAM_TOKEN   = os.environ.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
ACCOUNT_SIZE     = 500
RISK_PERCENT     = 1.5
USE_TESTNET      = True
BASE_URL         = "https://api-testnet.bybit.com" if USE_TESTNET else "https://api.bybit.com"

# ═══ Telegram ═══
def send_telegram(message):
    try:
        if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
            requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                json={"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
            )
    except Exception as e:
        print(f"Telegram error: {e}")

# ═══ Signature ═══
def generate_signature(secret, params):
    param_str = "&".join([f"{k}={v}" for k, v in sorted(params.items())])
    return hmac.new(secret.encode(), param_str.encode(), hashlib.sha256).hexdigest()

# ═══ Position Size ═══
def calculate_qty(price, sl_price):
    try:
        risk_amount = ACCOUNT_SIZE * (RISK_PERCENT / 100)
        sl_distance = abs(float(price) - float(sl_price))
        sl_percent  = sl_distance / float(price)
        qty = risk_amount / (float(price) * sl_percent)
        return round(qty, 2)
    except Exception as e:
        print(f"Qty error: {e}")
        return 1.0

# ═══ Place Order ═══
def place_order(symbol, side, price, sl, tp):
    try:
        qty       = calculate_qty(price, sl)
        timestamp = str(int(time.time() * 1000))
        params    = {
            "api_key":       BYBIT_API_KEY,
            "symbol":        symbol,
            "side":          side,
            "order_type":    "Market",
            "qty":           qty,
            "time_in_force": "GoodTillCancel",
            "stop_loss":     sl,
            "take_profit":   tp,
            "timestamp":     timestamp,
            "recv_window":   "5000"
        }
        params["sign"] = generate_signature(BYBIT_API_SECRET, params)
        response       = requests.post(f"{BASE_URL}/v2/private/order/create", data=params)
        result         = response.json()

        if result.get("ret_code") == 0:
            send_telegram(
                f"✅ <b>TRADE EXECUTED</b>\n"
                f"─────────────────\n"
                f"📊 Pair:  <b>{symbol}</b>\n"
                f"📈 Side:  <b>{side}</b>\n"
                f"💰 Price: <b>{price}</b>\n"
                f"🎯 TP:    <b>{tp}</b>\n"
                f"🛑 SL:    <b>{sl}</b>\n"
                f"📦 Qty:   <b>{qty}</b>\n"
                f"💵 Risk:  <b>${round(ACCOUNT_SIZE * RISK_PERCENT / 100, 2)}</b>\n"
                f"─────────────────\n"
                f"{'🧪 TESTNET' if USE_TESTNET else '🔴 LIVE'}"
            )
            return {"status": "success"}
        else:
            send_telegram(f"❌ Order FAILED: {result.get('ret_msg')}")
            return {"status": "error", "message": result.get("ret_msg")}

    except Exception as e:
        send_telegram(f"❌ Bot error: {str(e)}")
        return {"status": "error", "message": str(e)}

# ═══ Routes ═══
@app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "running", "mode": "TESTNET" if USE_TESTNET else "LIVE"})

@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data   = request.get_json(force=True)
        side   = data.get("side")
        symbol = data.get("symbol")
        price  = data.get("price")
        sl     = data.get("sl")
        tp     = data.get("tp")

        if not all([side, symbol, price, sl, tp]):
            return jsonify({"status": "error", "message": "Missing fields"}), 400
        if float(sl) == 0 or float(tp) == 0:
            return jsonify({"status": "error", "message": "Invalid SL/TP"}), 400

        return jsonify(place_order(symbol, side, price, sl, tp)), 200

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
