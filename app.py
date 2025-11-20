import os
import sqlite3
import io
import csv
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, send_file, jsonify, flash, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from io import BytesIO

DB = "fitness_web.db"
UPLOAD_FOLDER = "static/uploads"
ALLOWED_EXT = {"png", "jpg", "jpeg", "gif"}

app = Flask(__name__)
app.secret_key = "replace_this_with_a_random_secret_key"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024  # 2MB

os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            name TEXT,
            email TEXT,
            avatar TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS fitness (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            date TEXT,
            steps INTEGER,
            calories INTEGER,
            sleep_hours REAL,
            notes TEXT,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)

    conn.commit()
    conn.close()


init_db()

@app.context_processor
def inject_user():
    return dict(current_user=current_user, session=session)

def current_user():
    uid = session.get("user_id")
    if not uid:
        return None
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    conn.close()
    return user


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXT

@app.route("/")
def home():
    if current_user():
        return redirect(url_for("dashboard"))
    return render_template("home.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]
        name = request.form.get("name", "")
        email = request.form.get("email", "")

        hashed = generate_password_hash(password)
        conn = get_db()

        try:
            conn.execute(
                "INSERT INTO users (username,password,name,email) VALUES (?,?,?,?)",
                (username, hashed, name, email)
            )
            conn.commit()
            flash("Account created!", "success")
            return redirect(url_for("login"))

        except sqlite3.IntegrityError:
            flash("Username is already taken", "danger")

        finally:
            conn.close()

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
        conn.close()

        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            return redirect(url_for("dashboard"))

        flash("Invalid username or password", "danger")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))


@app.route("/profile", methods=["GET", "POST"])
def profile():
    user = current_user()
    if not user:
        return redirect(url_for("login"))

    if request.method == "POST":
        name = request.form.get("name", "")
        email = request.form.get("email", "")
        file = request.files.get("avatar")

        avatar_filename = user["avatar"]

        if file and allowed_file(file.filename):
            fname = secure_filename(file.filename)
            fname = f"user_{user['id']}_{int(datetime.utcnow().timestamp())}_{fname}"
            file.save(os.path.join(app.config["UPLOAD_FOLDER"], fname))
            avatar_filename = fname

        conn = get_db()
        conn.execute("UPDATE users SET name=?, email=?, avatar=? WHERE id=?",
                     (name, email, avatar_filename, user["id"]))
        conn.commit()
        conn.close()

        flash("Profile updated!", "success")
        return redirect(url_for("profile"))

    return render_template("profile.html", user=user)


@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)


@app.route("/dashboard")
def dashboard():
    user = current_user()
    if not user:
        return redirect(url_for("login"))

    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM fitness WHERE user_id=? ORDER BY date ASC",
        (user["id"],)
    ).fetchall()
    conn.close()

    total_steps = sum(r["steps"] or 0 for r in rows)
    total_cal = sum(r["calories"] or 0 for r in rows)
    avg_sleep = round(
        sum(r["sleep_hours"] or 0 for r in rows) / len(rows), 2
    ) if rows else 0

    return render_template(
        "dashboard.html",
        records=rows,
        total_steps=total_steps,
        total_cal=total_cal,
        avg_sleep=avg_sleep
    )


@app.route("/add", methods=["GET", "POST"])
def add_entry():
    user = current_user()
    if not user:
        return redirect(url_for("login"))

    if request.method == "POST":
        date = request.form["date"]
        steps = int(request.form.get("steps") or 0)
        calories = int(request.form.get("calories") or 0)
        sleep = float(request.form.get("sleep") or 0)
        notes = request.form.get("notes", "")

        conn = get_db()
        conn.execute(
            "INSERT INTO fitness (user_id,date,steps,calories,sleep_hours,notes) VALUES (?,?,?,?,?,?)",
            (user["id"], date, steps, calories, sleep, notes)
        )
        conn.commit()
        conn.close()

        return redirect(url_for("dashboard"))

    return render_template("add.html", today=datetime.today().strftime("%Y-%m-%d"))


@app.route("/edit/<int:fid>", methods=["GET", "POST"])
def edit_entry(fid):
    user = current_user()
    if not user:
        return redirect(url_for("login"))

    conn = get_db()
    row = conn.execute(
        "SELECT * FROM fitness WHERE id=? AND user_id=?",
        (fid, user["id"])
    ).fetchone()

    if not row:
        flash("Entry not found", "danger")
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        date = request.form["date"]
        steps = int(request.form.get("steps") or 0)
        calories = int(request.form.get("calories") or 0)
        sleep = float(request.form.get("sleep") or 0)
        notes = request.form.get("notes", "")

        conn.execute(
            "UPDATE fitness SET date=?,steps=?,calories=?,sleep_hours=?,notes=? WHERE id=?",
            (date, steps, calories, sleep, notes, fid)
        )
        conn.commit()
        conn.close()

        return redirect(url_for("dashboard"))

    return render_template("edit.html", row=row)


@app.route("/delete/<int:fid>")
def delete_entry(fid):
    user = current_user()
    if not user:
        return redirect(url_for("login"))

    conn = get_db()
    conn.execute(
        "DELETE FROM fitness WHERE id=? AND user_id=?",
        (fid, user["id"])
    )
    conn.commit()
    conn.close()

    return redirect(url_for("dashboard"))


@app.route("/export/csv")
def export_csv():
    user = current_user()
    if not user:
        return redirect(url_for("login"))

    conn = get_db()
    rows = conn.execute(
        "SELECT date,steps,calories,sleep_hours,notes FROM fitness WHERE user_id=? ORDER BY date ASC",
        (user["id"],)
    ).fetchall()
    conn.close()

    si = io.StringIO()
    cw = csv.writer(si)
    cw.writerow(["date", "steps", "calories", "sleep_hours", "notes"])

    for r in rows:
        cw.writerow([r["date"], r["steps"], r["calories"], r["sleep_hours"], r["notes"]])

    mem = io.BytesIO(si.getvalue().encode("utf-8"))
    mem.seek(0)

    return send_file(mem, download_name="fitness_export.csv", as_attachment=True)

@app.route("/plot.png")
def plot_png():
    user = current_user()
    if not user:
        return redirect(url_for("login"))

    conn = get_db()
    rows = conn.execute(
        "SELECT date, steps, calories, sleep_hours FROM fitness WHERE user_id=? ORDER BY date ASC",
        (user["id"],)
    ).fetchall()
    conn.close()

    dates = [r["date"] for r in rows]
    steps = [r["steps"] for r in rows]
    calories = [r["calories"] for r in rows]
    sleep = [r["sleep_hours"] for r in rows]

    plt.figure(figsize=(10, 4))
    plt.plot(dates, steps, label="Steps", linewidth=2)
    plt.plot(dates, calories, label="Calories", linewidth=2)
    plt.plot(dates, sleep, label="Sleep (hrs)", linewidth=2)
    plt.xticks(rotation=45)
    plt.legend()
    plt.tight_layout()

    img = BytesIO()
    plt.savefig(img, format="png", dpi=150)
    img.seek(0)
    plt.close()

    return send_file(img, mimetype="image/png")


if __name__ == "__main__":
    app.run(debug=True)