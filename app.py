"""サブスク棚卸しメモ subscheck

契約中のサブスクリプションを登録して、月額合計と年間換算を自動で
計算する棚卸しメモ。請求日と見直し日も記録できる。
データは SQLite に保存する。単一ファイル Flask + SQLite。
"""
import os
import sqlite3

from flask import Flask, g, jsonify, redirect, render_template_string, request, url_for

app = Flask(__name__)
DB_PATH = os.environ.get("SUBSCHECK_DB", os.path.join(os.path.dirname(__file__), "subscheck.db"))


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = sqlite3.connect(DB_PATH)
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS subs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            amount INTEGER NOT NULL DEFAULT 0,
            billing_day INTEGER NOT NULL DEFAULT 1,
            review_date TEXT NOT NULL DEFAULT '',
            memo TEXT NOT NULL DEFAULT ''
        );
        """
    )
    db.commit()
    db.close()


def monthly_total(db):
    row = db.execute("SELECT COALESCE(SUM(amount), 0) AS total FROM subs").fetchone()
    return row["total"]


PAGE = """<!doctype html>
<html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>サブスク棚卸しメモ</title>
<style>body{font-family:sans-serif;max-width:680px;margin:2em auto;padding:0 1em}
.total{background:#fdf6e3;border:1px solid #d9b84a;border-radius:8px;padding:1em;font-size:1.1em}
table{border-collapse:collapse}td,th{border-bottom:1px solid #ccc;padding:.3em .6em}
input{margin:.2em 0}</style>
</head><body>
<h1>サブスク棚卸しメモ</h1>
<p>契約中のサブスクを登録して、合計いくら払っているかを一目で確認するためのメモです。</p>

<div class="total">
  月額合計：<strong>{{ total }} 円</strong> ／ 年間換算：<strong>{{ total * 12 }} 円</strong>（{{ count }} 件）
</div>

<h2>サブスクを登録</h2>
<form method="post" action="{{ url_for('add') }}">
  <div><label>名前 <input type="text" name="name" placeholder="例：音楽配信サービス" required></label></div>
  <div><label>月額（円） <input type="number" name="amount" min="0" step="1" placeholder="980" required></label></div>
  <div><label>請求日（毎月） <input type="number" name="billing_day" min="1" max="31" value="1" required> 日</label></div>
  <div><label>見直し日（任意） <input type="date" name="review_date"></label></div>
  <div><label>メモ <input type="text" name="memo" placeholder="例：年払いの方が安いか確認"></label></div>
  <button type="submit">登録する</button>
</form>

<h2>登録済みサブスク</h2>
<table>
<tr><th>名前</th><th>月額</th><th>請求日</th><th>見直し日</th><th>メモ</th><th>操作</th></tr>
{% for s in subs %}
<tr><td>{{ s.name }}</td><td>{{ s.amount }} 円</td><td>毎月{{ s.billing_day }}日</td><td>{{ s.review_date }}</td><td>{{ s.memo }}</td>
<td><form method="post" action="{{ url_for('delete', sid=s.id) }}" onsubmit="return confirm('このサブスクを削除しますか？')"><button type="submit">削除</button></form></td></tr>
{% else %}<tr><td colspan="6">まだ登録されていません</td></tr>{% endfor %}
</table>
</body></html>"""


@app.route("/healthz")
def healthz():
    return jsonify({"status": "ok"})


@app.route("/")
def index():
    db = get_db()
    subs = db.execute("SELECT * FROM subs ORDER BY billing_day, id").fetchall()
    return render_template_string(
        PAGE, subs=subs, total=monthly_total(db), count=len(subs)
    )


@app.route("/add", methods=["POST"])
def add():
    name = (request.form.get("name") or "").strip()
    try:
        amount = int(request.form.get("amount") or 0)
        billing_day = int(request.form.get("billing_day") or 1)
    except ValueError:
        return redirect(url_for("index"))
    if name and amount >= 0 and 1 <= billing_day <= 31:
        db = get_db()
        db.execute(
            "INSERT INTO subs(name, amount, billing_day, review_date, memo) VALUES(?, ?, ?, ?, ?)",
            (
                name,
                amount,
                billing_day,
                (request.form.get("review_date") or "").strip(),
                (request.form.get("memo") or "").strip(),
            ),
        )
        db.commit()
    return redirect(url_for("index"))


@app.route("/delete/<int:sid>", methods=["POST"])
def delete(sid):
    db = get_db()
    db.execute("DELETE FROM subs WHERE id = ?", (sid,))
    db.commit()
    return redirect(url_for("index"))


init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")))
