from datetime import datetime
import os
import sqlite3
from flask import Flask, redirect, render_template, request, url_for, jsonify

app = Flask(__name__)

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_NAME = os.path.join(BASE_DIR, "shopping_stock.db")


def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as conn:
        # 1. Inventory Items Table (Empty by default)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS inventory_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_name TEXT UNIQUE NOT NULL,
                unit TEXT NOT NULL,
                current_balance REAL DEFAULT 0.0,
                low_stock_threshold REAL DEFAULT 1.0
            )
        """)

        # 2. Stock Activity Ledger
        conn.execute("""
            CREATE TABLE IF NOT EXISTS stock_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                action_type TEXT CHECK(action_type IN ('RESTOCK', 'CONSUME')),
                item_name TEXT NOT NULL,
                quantity REAL NOT NULL,
                notes TEXT,
                timestamp TEXT NOT NULL
            )
        """)
        conn.commit()


init_db()


@app.route("/")
def index():
    with get_db() as conn:
        items = conn.execute(
            "SELECT * FROM inventory_items ORDER BY item_name ASC"
        ).fetchall()

        logs = conn.execute(
            "SELECT * FROM stock_logs ORDER BY id DESC LIMIT 15"
        ).fetchall()

    return render_template(
        "index.html",
        items=items,
        logs=logs
    )


@app.route("/add_item", methods=["POST"])
def add_item():
    item_name = request.form.get("item_name", "").strip()
    unit = request.form.get("unit", "pieces").strip()
    try:
        initial_qty = float(request.form.get("initial_qty", 0.0))
        threshold = float(request.form.get("threshold", 1.0))
    except (ValueError, TypeError):
        initial_qty, threshold = 0.0, 1.0

    if item_name:
        with get_db() as conn:
            conn.execute(
                """
                INSERT INTO inventory_items (item_name, unit, current_balance, low_stock_threshold)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(item_name) DO UPDATE SET
                    unit=excluded.unit,
                    current_balance=excluded.current_balance,
                    low_stock_threshold=excluded.low_stock_threshold
                """,
                (item_name, unit, initial_qty, threshold),
            )
            conn.commit()
    return redirect(url_for("index"))


@app.route("/quick_adjust/<int:item_id>/<action>", methods=["POST"])
def quick_adjust(item_id, action):
    """Allows one-tap +/- buttons on your phone"""
    with get_db() as conn:
        item = conn.execute("SELECT * FROM inventory_items WHERE id = ?", (item_id,)).fetchone()
        if item:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            if action == "add":
                new_bal = item["current_balance"] + 1.0
                conn.execute("UPDATE inventory_items SET current_balance = ? WHERE id = ?", (new_bal, item_id))
                conn.execute(
                    "INSERT INTO stock_logs (action_type, item_name, quantity, notes, timestamp) VALUES (?, ?, ?, ?, ?)",
                    ("RESTOCK", item["item_name"], 1.0, "Quick +1 adjustment", now)
                )
            elif action == "minus":
                new_bal = max(0.0, item["current_balance"] - 1.0)
                conn.execute("UPDATE inventory_items SET current_balance = ? WHERE id = ?", (new_bal, item_id))
                conn.execute(
                    "INSERT INTO stock_logs (action_type, item_name, quantity, notes, timestamp) VALUES (?, ?, ?, ?, ?)",
                    ("CONSUME", item["item_name"], 1.0, "Quick -1 adjustment", now)
                )
            conn.commit()
    return redirect(url_for("index"))


@app.route("/delete_item/<int:item_id>", methods=["POST"])
def delete_item(item_id):
    with get_db() as conn:
        conn.execute("DELETE FROM inventory_items WHERE id = ?", (item_id,))
        conn.commit()
    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(debug=True, port=5000)