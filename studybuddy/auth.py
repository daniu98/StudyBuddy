import sqlite3

from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from .db import get_db, login_required
from .repositories import courses as courses_repo
from .repositories import users as users_repo

bp = Blueprint("auth", __name__)


@bp.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "GET":
        return render_template("signup.html")

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
        user_id = users_repo.create(conn, name, email, password_hash)
        conn.commit()
        session["user_id"] = user_id
        flash("Account created successfully.")
        return redirect(url_for("auth.profile"))
    except sqlite3.IntegrityError:
        flash("An account with that email already exists.")
        return redirect(url_for("auth.signup"))
    finally:
        conn.close()


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")

    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    conn = get_db()
    try:
        user = users_repo.find_by_email(conn, email)
    finally:
        conn.close()

    if user is None or not check_password_hash(user["password_hash"], password):
        flash("Incorrect email or password.")
        return redirect(url_for("auth.login"))

    session["user_id"] = user["id"]
    flash("Logged in successfully.")
    return redirect(url_for("main.home"))


@bp.route("/logout")
def logout():
    session.clear()
    flash("Logged out.")
    return redirect(url_for("main.home"))


@bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    user_id = session["user_id"]
    conn = get_db()
    try:
        if request.method == "GET":
            courses = courses_repo.list_all(conn)
            selected_ids = users_repo.selected_course_ids(conn, user_id)
            return render_template(
                "profile.html",
                courses=courses,
                selected_ids=selected_ids,
            )

        selected_course_ids = request.form.getlist("course_ids")
        users_repo.replace_user_courses(conn, user_id, selected_course_ids)
        conn.commit()
        flash("Profile courses saved.")
        return redirect(url_for("auth.profile"))
    finally:
        conn.close()


@bp.route("/change_password", methods=["GET", "POST"])
@login_required
def change_password():
    if request.method == "GET":
        return render_template("change_password.html")

    old_password = request.form.get("old_password", "")
    new_password = request.form.get("new_password", "")

    user_id = session["user_id"]
    conn = get_db()
    try:
        user = users_repo.find_by_id(conn, user_id)

        if not check_password_hash(user["password_hash"], old_password):
            flash("Incorrect password.")
            return redirect(url_for("auth.change_password"))
        if len(new_password) < 6:
            flash("New password must be at least 6 characters.")
            return redirect(url_for("auth.change_password"))
        if new_password == old_password:
            flash("New password cannot be identical to old password.")
            return redirect(url_for("auth.change_password"))

        password_hash = generate_password_hash(new_password, method="pbkdf2:sha256")
        users_repo.update_password_hash(conn, user_id, password_hash)
        conn.commit()
    except sqlite3.Error:
        conn.rollback()
        flash("Unknown error changing password. Please try again.")
        return redirect(url_for("auth.profile"))
    finally:
        conn.close()

    flash("Password successfully changed.")
    return redirect(url_for("auth.profile"))
