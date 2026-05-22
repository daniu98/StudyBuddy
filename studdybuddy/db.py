from functools import wraps
import sqlite3

from flask import flash, redirect, session, url_for

DATABASE = "studybuddy.db"
MESSAGE_MAX_LENGTH = 2000


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in first.")
            return redirect(url_for("auth.login"))
        return view(*args, **kwargs)

    return wrapped_view


def user_is_group_member(conn, group_id, user_id):
    row = conn.execute(
        "SELECT 1 FROM group_members WHERE group_id = ? AND user_id = ?",
        (group_id, user_id),
    ).fetchone()
    return row is not None


def current_user():
    if "user_id" not in session:
        return None

    conn = get_db()
    user = conn.execute(
        "SELECT * FROM users WHERE id = ?",
        (session["user_id"],),
    ).fetchone()
    conn.close()
    return user
