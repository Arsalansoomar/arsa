import os
from flask import Flask, jsonify

app = Flask(__name__)

@app.route("/", methods=["GET"])
def index():
    return jsonify({"status": "running", "version": "5"})

@app.route("/testwebhook", methods=["GET"])
def testwebhook():
    return jsonify({"status": "testwebhook working", "version": "5"})

@app.route("/test", methods=["GET"])  
def test():
    return jsonify({"status": "test working", "version": "5"})

@app.route("/webhook", methods=["POST"])
def webhook():
    return jsonify({"status": "webhook working", "version": "5"})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
