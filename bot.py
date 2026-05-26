import os
import hmac
import hashlib
import time
import json  # v5
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

BYBIT_API_KEY    = os.environ.get("BYBIT_API_KEY", "")
BYBIT_API_SECRET = os.environ.get("BYBIT_API_SECRET", "")
TELEGRAM_TOKEN   = os.environ.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
ACCOUNT_SIZE     = 500
RISK_PERCENT     = 1.5
USE_TESTNET      = True
BASE_URL         = "https://api-testnet.bybit.com" if USE_TESTNET else "https://api.bybit.com"

def send_telegram(msg):
    try:
        if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
            requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "HTML"},
                timeout=5
            )
    except Exception as e:
        print(f"Telegram error: {e}")

def calculate_qty(price, sl):
    try:
        risk = ACCOUNT_SIZE * (RISK_PERCENT / 100)
        dist = abs(float(price) - float(sl)) / float(price)
        if dist == 0:
            return 1.0
        return round(risk / (float(price) * dist), 2)
    except Exception as e:
        print(f"Qty error: {e}")
        return 1.0

def place_order(symbol, side, price, sl, tp):
    try:
        qty = calculate_qty(price, sl)
        ts  = str(int(time.time() * 1000))
        p   = {
            "api_key":       BYBIT_API_KEY,
            "symbol":        symbol,
            "side":          side,
            "order_type":    "Market",
            "qty":           str(qty),
            "time_in_force": "GoodTillCancel",
            "stop_loss":     str(sl),
            "take_profit":   str(tp),
            "timestamp":     ts,
            "recv_window":   "5000"
        }
        param_str = "&".join(f"{k}={v}" for k, v in sorted(p.items()))
        sig = hmac.new(BYBIT_API_SECRET.encode(), param_str.encode(), hashlib.sha256).hexdigest()
        p["sign"] = sig

        r = requests.post(f"{BASE_URL}/v2/private/order/create", data=p, timeout=10).json()
        print(f"Bybit response: {r}")

        if r.get("ret_code") == 0:
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
            return {"status": "success", "qty": qty}
        else:
            msg = f"❌ Order FAILED: {r.get('ret_msg')}"
            send_telegram(msg)
            return {"status": "error", "message": r.get("ret_msg")}

    except Exception as e:
        send_telegram(f"❌ Bot error: {str(e)}")
        print(f"Place order error: {e}")
        return {"status": "error", "message": str(e)}

@app.route("/", methods=["GET"])
def index():
    return jsonify({"status": "running", "mode": "TESTNET" if USE_TESTNET else "LIVE"})

@app.route("/test", methods=["GET"])
def test():
    send_telegram("🧪 Test message from Arsalan Scalper Bot! Bot is working ✅")
    return jsonify({"status": "test sent to telegram"})

@app.route("/testwebhook", methods=["GET"])
def testwebhook():
    result = place_order("BTCUSDT", "Buy", "50000", "49000", "51000")
    return jsonify(result)

@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        raw_bytes = request.data
        raw_str   = raw_bytes.decode("utf-8").strip()
        print(f"Raw received: {repr(raw_str)}")

        data = json.loads(raw_str)
        print(f"Parsed data: {data}")

        side   = str(data.get("side",   "")).strip()
        symbol = str(data.get("symbol", "")).strip()
        price  = str(data.get("price",  "")).strip()
        sl     = str(data.get("sl",     "")).strip()
        tp     = str(data.get("tp",     "")).strip()

        print(f"side={side} symbol={symbol} price={price} sl={sl} tp={tp}")

        if not all([side, symbol, price, sl, tp]):
            return jsonify({"status": "error", "message": "Missing fields"}), 400
        if float(sl) == 0 or float(tp) == 0:
            return jsonify({"status": "error", "message": "Invalid SL/TP"}), 400

        result = place_order(symbol, side, price, sl, tp)
        return jsonify(result)

    except json.JSONDecodeError as e:
        print(f"JSON error: {e} | raw: {repr(request.data)}")
        return jsonify({"status": "error", "message": f"JSON parse error: {str(e)}"}), 400

    except Exception as e:
        print(f"Webhook error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
