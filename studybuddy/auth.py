import sqlite3

from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from .db import get_db, login_required

bp = Blueprint("auth", __name__)


@bp.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not name or not email or not password:
            flash("Name, email, and password are required.")
            return redirect(url_for("auth.signup"))

        if len(password) < 6:
            flash("Password must be at least 6 characters.")
            return redirect(url_for("auth.signup"))

        password_hash = generate_password_hash(password, method="pbkdf2:sha256")

        conn = get_db()
        try:
            cursor = conn.execute(
                "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
                (name, email, password_hash),
            )
            conn.commit()
            session["user_id"] = cursor.lastrowid
            flash("Account created successfully.")
            return redirect(url_for("auth.profile"))
        except sqlite3.IntegrityError:
            flash("An account with that email already exists.")
            return redirect(url_for("auth.signup"))
        finally:
            conn.close()

    return render_template("signup.html")


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        conn = get_db()
        user = conn.execute(
            "SELECT * FROM users WHERE email = ?",
            (email,),
        ).fetchone()
        conn.close()

        if user is None or not check_password_hash(user["password_hash"], password):
            flash("Incorrect email or password.")
            return redirect(url_for("auth.login"))

        session["user_id"] = user["id"]
        flash("Logged in successfully.")
        return redirect(url_for("main.home"))

    return render_template("login.html")


@bp.route("/logout")
def logout():
    session.clear()
    flash("Logged out.")
    return redirect(url_for("main.home"))


@bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    conn = get_db()
    user_id = session["user_id"]

    if request.method == "POST":
        selected_course_ids = request.form.getlist("course_ids")

        conn.execute("DELETE FROM user_courses WHERE user_id = ?", (user_id,))

        for course_id in selected_course_ids:
            conn.execute(
                "INSERT INTO user_courses (user_id, course_id) VALUES (?, ?)",
                (user_id, course_id),
            )

        conn.commit()
        flash("Profile courses saved.")
        return redirect(url_for("auth.profile"))

    courses = conn.execute("SELECT * FROM courses ORDER BY code").fetchall()

    selected = conn.execute(
        "SELECT course_id FROM user_courses WHERE user_id = ?",
        (user_id,),
    ).fetchall()

    selected_ids = {row["course_id"] for row in selected}
    conn.close()

    return render_template(
        "profile.html",
        courses=courses,
        selected_ids=selected_ids,
    )

@bp.route("/change_password", methods=["GET", "POST"])
@login_required
def change_password():
    if request.method == "POST":
        old_password = request.form.get("old_password", "")
        new_password = request.form.get("new_password", "")
        
        user_id = session["user_id"]
        conn = get_db()
        user = conn.execute(
            "SELECT * FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()

        if not check_password_hash(user["password_hash"], old_password):
            flash("Incorrect password.")
            return redirect(url_for("auth.change_password"))
        if len(new_password) < 6:
            flash("New password must be at least 6 characters.")
            return redirect(url_for("auth.change_password"))
        if new_password == old_password:
            flash("New password cannot be identical to old password.")
            return redirect(url_for("auth.change_password"))
        
        try:
            password_hash = generate_password_hash(new_password, method="pbkdf2:sha256")
            cursor = conn.execute(
                "UPDATE users SET password_hash = ? WHERE id = ?",
                (password_hash, user_id,),
            )
            conn.commit()
        except sqlite3.Error:
            conn.rollback()
            flash("Unknown error changing password. Please try again.")
            return redirect(url_for("auth.profile"))
        finally:
            conn.close()
        flash("Password successfully changed.")
        return redirect(url_for("auth.profile"))
    
    return render_template("change_password.html")