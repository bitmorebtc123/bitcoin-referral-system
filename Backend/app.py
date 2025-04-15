from flask import Flask, request, jsonify
from flask_cors import CORS
import sqlite3
import uuid
import requests

app = Flask(__name__)
CORS(app)

# Connect to database
def db():
    return sqlite3.connect("referral_system.db")

# Initialize DB
def init_db():
    conn = db()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        email TEXT,
        password TEXT,
        btc_wallet TEXT,
        referred_by TEXT,
        level INTEGER DEFAULT 0,
        balance REAL DEFAULT 0.0
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS transactions (
        id TEXT PRIMARY KEY,
        user_id TEXT,
        amount REAL,
        type TEXT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')
    conn.commit()
    conn.close()

init_db()

@app.route("/signup", methods=["POST"])
def signup():
    data = request.json
    user_id = str(uuid.uuid4())
    with db() as conn:
        cur = conn.cursor()
        cur.execute("INSERT INTO users (id, email, password, btc_wallet, referred_by) VALUES (?, ?, ?, ?, ?)", 
                    (user_id, data["email"], data["password"], data["btc_wallet"], data.get("referred_by")))
        conn.commit()
    return jsonify({"message": "Signup successful", "user_id": user_id})

@app.route("/login", methods=["POST"])
def login():
    data = request.json
    with db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE email=? AND password=?", (data["email"], data["password"]))
        user = cur.fetchone()
        if user:
            return jsonify({"message": "Login successful", "user_id": user[0]})
        return jsonify({"message": "Invalid credentials"}), 401

@app.route("/invest", methods=["POST"])
def invest():
    data = request.json
    user_id = data["user_id"]
    amount = 0.0003
    company_share = round(amount * 0.10, 8)
    user_share = round(amount * 0.90, 8)

    with db() as conn:
        cur = conn.cursor()
        cur.execute("UPDATE users SET balance = balance + ? WHERE id=?", (user_share, user_id))
        cur.execute("INSERT INTO transactions (id, user_id, amount, type) VALUES (?, ?, ?, ?)", 
                    (str(uuid.uuid4()), user_id, amount, "invest"))
        conn.commit()
    return jsonify({"message": "Investment successful", "user_share": user_share, "company_share": company_share})

@app.route("/btc-price", methods=["GET"])
def btc_price():
    try:
        response = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd")
        price = response.json()["bitcoin"]["usd"]
        return jsonify({"btc_usd": price})
    except:
        return jsonify({"btc_usd": "Unavailable"}), 500

@app.route("/transactions/<user_id>", methods=["GET"])
def transactions(user_id):
    with db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM transactions WHERE user_id=? ORDER BY timestamp DESC", (user_id,))
        rows = cur.fetchall()
    return jsonify([{"id": r[0], "amount": r[2], "type": r[3], "timestamp": r[4]} for r in rows])

@app.route("/invest", methods=["POST"])
def invest():
    data = request.json
    user_id = data["user_id"]
    amount = 0.0003
    company_share = round(amount * 0.10, 8)
    referral_share = round(amount * 0.90, 8)

    conn = db()
    cur = conn.cursor()

    # Update this user's balance (initial 0.90 will go to uplines)
    cur.execute("SELECT referred_by FROM users WHERE id=?", (user_id,))
    referred_by = cur.fetchone()[0]

    # Track who gets referral earnings
    def pay_referral(ref_id, level):
        if ref_id:
            cur.execute("UPDATE users SET balance = balance + ? WHERE id=?", (referral_share, ref_id))
            cur.execute("INSERT INTO transactions (id, user_id, amount, type) VALUES (?, ?, ?, ?)",
                        (str(uuid.uuid4()), ref_id, referral_share, f"referral-level-{level}"))

    # Level 1
    pay_referral(referred_by, 1)

    # Level 2
    if referred_by:
        cur.execute("SELECT referred_by FROM users WHERE id=?", (referred_by,))
        second_level = cur.fetchone()[0]
        pay_referral(second_level, 2)

    # Log this user's investment
    cur.execute("INSERT INTO transactions (id, user_id, amount, type) VALUES (?, ?, ?, ?)",
                (str(uuid.uuid4()), user_id, amount, "invest"))

    conn.commit()
    conn.close()

    return jsonify({
        "message": "Investment successful",
        "company_share": company_share,
        "user_id": user_id,
        "referred_by": referred_by
    })
