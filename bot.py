import os
import hmac
import hashlib
import time
import requests
import json
from flask import Flask, request, jsonify

app = Flask(__name__)

# ═══ CONFIG — fill these in ═══
BYBIT_API_KEY    = "YOUR_BYBIT_API_KEY"
BYBIT_API_SECRET = "YOUR_BYBIT_API_SECRET"
TELEGRAM_TOKEN   = "YOUR_TELEGRAM_BOT_TOKEN"
TELEGRAM_CHAT_ID = "YOUR_TELEGRAM_CHAT_ID"
ACCOUNT_SIZE     = 500       # your account in USDT
RISK_PERCENT     = 1.5       # risk 1.5% per trade = $7.50 on $500
USE_TESTNET      = True      # True = testnet, False = real account

# ═══ Bybit URLs ═══
BASE_URL = "https://api-testnet.bybit.com" if USE_TESTNET else "https://api.bybit.com"

# ═══ Telegram Notification ═══
def send_telegram(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"})
    except Exception as e:
        print(f"Telegram error: {e}")

# ═══ Bybit Signature ═══
def generate_signature(secret, params):
    param_str = "&".join([f"{k}={v}" for k, v in sorted(params.items())])
    return hmac.new(secret.encode(), param_str.encode(), hashlib.sha256).hexdigest()

# ═══ Calculate Position Size ═══
def calculate_qty(price, sl_price):
    try:
        risk_amount = ACCOUNT_SIZE * (RISK_PERCENT / 100)  # $7.50
        sl_distance = abs(price - sl_price)
        sl_percent  = sl_distance / price
        qty = risk_amount / (price * sl_percent)
        return round(qty, 2)
    except Exception as e:
        print(f"Qty calc error: {e}")
        return 1.0

# ═══ Place Order on Bybit ═══
def place_order(symbol, side, price, sl, tp):
    try:
        qty = calculate_qty(float(price), float(sl))

        timestamp = str(int(time.time() * 1000))
        params = {
            "api_key":     BYBIT_API_KEY,
            "symbol":      symbol.replace("USDT", "") + "USDT",
            "side":        side,
            "order_type":  "Market",
            "qty":         qty,
            "time_in_force": "GoodTillCancel",
            "stop_loss":   sl,
            "take_profit": tp,
            "timestamp":   timestamp,
            "recv_window": "5000"
        }
        params["sign"] = generate_signature(BYBIT_API_SECRET, params)

        response = requests.post(f"{BASE_URL}/v2/private/order/create", data=params)
        result   = response.json()

        if result.get("ret_code") == 0:
            msg = (
                f"✅ <b>TRADE EXECUTED</b>\n"
                f"─────────────────\n"
                f"📊 Pair:   <b>{symbol}</b>\n"
                f"📈 Side:   <b>{side.upper()}</b>\n"
                f"💰 Price:  <b>{price}</b>\n"
                f"🎯 TP:     <b>{tp}</b>\n"
                f"🛑 SL:     <b>{sl}</b>\n"
                f"📦 Qty:    <b>{qty}</b>\n"
                f"💵 Risk:   <b>${round(ACCOUNT_SIZE * RISK_PERCENT / 100, 2)}</b>\n"
                f"─────────────────\n"
                f"{'🧪 TESTNET' if USE_TESTNET else '🔴 LIVE ACCOUNT'}"
            )
            send_telegram(msg)
            print(f"Order placed: {result}")
            return {"status": "success", "order": result}
        else:
            error_msg = f"❌ Order FAILED: {result.get('ret_msg')}\nSymbol: {symbol} Side: {side}"
            send_telegram(error_msg)
            print(f"Order failed: {result}")
            return {"status": "error", "message": result.get("ret_msg")}

    except Exception as e:
        send_telegram(f"❌ Bot error: {str(e)}")
        print(f"Exception: {e}")
        return {"status": "error", "message": str(e)}

# ═══ Webhook Receiver ═══
@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.get_json()
        print(f"Signal received: {data}")

        side   = data.get("side")    # Buy or Sell
        symbol = data.get("symbol")  # e.g. BRETTUSDT
        price  = data.get("price")
        sl     = data.get("sl")
        tp     = data.get("tp")

        # Safety checks
        if not all([side, symbol, price, sl, tp]):
            return jsonify({"status": "error", "message": "Missing fields"}), 400

        if float(sl) == 0 or float(tp) == 0:
            return jsonify({"status": "error", "message": "Invalid SL/TP"}), 400

        result = place_order(symbol, side, price, sl, tp)
        return jsonify(result), 200

    except Exception as e:
        print(f"Webhook error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# ═══ Health Check ═══
@app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "running", "mode": "TESTNET" if USE_TESTNET else "LIVE"}), 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    send_telegram("🤖 Arsalan Scalper Bot started!\nMode: " + ("TESTNET" if USE_TESTNET else "LIVE"))
    app.run(host="0.0.0.0", port=port)