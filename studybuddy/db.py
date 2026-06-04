from functools import wraps

from flask import flash, redirect, session, url_for

from .db_connection import DATABASE, get_db
from .repositories import study_groups as groups_repo
from .repositories import users as users_repo

MESSAGE_MAX_LENGTH = 2000


def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in first.")
            return redirect(url_for("auth.login"))
        return view(*args, **kwargs)

    return wrapped_view


def user_is_group_member(conn, group_id, user_id):
    return groups_repo.is_member(conn, group_id, user_id)


def current_user():
    if "user_id" not in session:
        return None

    conn = get_db()
    try:
        return users_repo.find_by_id(conn, session["user_id"])
    finally:
        conn.close()
