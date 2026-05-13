from functools import wraps
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config["SECRET_KEY"] = "dev-secret-key-change-this"
DATABASE = "studybuddy.db"


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in first.")
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped_view


def current_user():
    if "user_id" not in session:
        return None

    conn = get_db()
    user = conn.execute(
        "SELECT * FROM users WHERE id = ?",
        (session["user_id"],)
    ).fetchone()
    conn.close()
    return user


@app.context_processor
def inject_user():
    return {"current_user": current_user()}


@app.route("/")
def home():
    return render_template("home.html")


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not name or not email or not password:
            flash("Name, email, and password are required.")
            return redirect(url_for("signup"))

        if len(password) < 6:
            flash("Password must be at least 6 characters.")
            return redirect(url_for("signup"))

        password_hash = generate_password_hash(password)

        conn = get_db()
        try:
            cursor = conn.execute(
                "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
                (name, email, password_hash),
            )
            conn.commit()
            session["user_id"] = cursor.lastrowid
            flash("Account created successfully.")
            return redirect(url_for("profile"))
        except sqlite3.IntegrityError:
            flash("An account with that email already exists.")
            return redirect(url_for("signup"))
        finally:
            conn.close()

    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        conn = get_db()
        user = conn.execute(
            "SELECT * FROM users WHERE email = ?",
            (email,)
        ).fetchone()
        conn.close()

        if user is None or not check_password_hash(user["password_hash"], password):
            flash("Incorrect email or password.")
            return redirect(url_for("login"))

        session["user_id"] = user["id"]
        flash("Logged in successfully.")
        return redirect(url_for("home"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out.")
    return redirect(url_for("home"))


@app.route("/profile", methods=["GET", "POST"])
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
        return redirect(url_for("profile"))

    courses = conn.execute("SELECT * FROM courses ORDER BY code").fetchall()

    selected = conn.execute(
        "SELECT course_id FROM user_courses WHERE user_id = ?",
        (user_id,)
    ).fetchall()

    selected_ids = {row["course_id"] for row in selected}
    conn.close()

    return render_template(
        "profile.html",
        courses=courses,
        selected_ids=selected_ids
    )


@app.route("/dashboard")
@login_required
def dashboard():
    conn = get_db()
    user_id = session["user_id"]
    groups = conn.execute(
        """
        SELECT sg.id, sg.title, sg.description, sg.meeting_time, sg.location,
               gm.role, gm.joined_at
        FROM study_groups sg
        INNER JOIN group_members gm ON sg.id = gm.group_id
        WHERE gm.user_id = ?
        ORDER BY sg.title COLLATE NOCASE
        """,
        (user_id,),
    ).fetchall()
    conn.close()
    return render_template("dashboard.html", groups=groups)


@app.route("/groups/<int:group_id>")
@login_required
def group_detail(group_id):
    conn = get_db()
    user_id = session["user_id"]

    member = conn.execute(
        "SELECT role, joined_at FROM group_members WHERE group_id = ? AND user_id = ?",
        (group_id, user_id),
    ).fetchone()

    group = conn.execute(
        """
        SELECT sg.*, u.name AS admin_name
        FROM study_groups sg
        JOIN users u ON sg.admin_id = u.id
        WHERE sg.id = ?
        """,
        (group_id,),
    ).fetchone()

    if group is None:
        conn.close()
        flash("That study group does not exist.")
        return redirect(url_for("dashboard"))

    if member is None:
        conn.close()
        flash("You can only open groups you belong to.")
        return redirect(url_for("dashboard"))

    courses = conn.execute(
        """
        SELECT c.code, c.name
        FROM courses c
        JOIN group_courses gc ON c.id = gc.course_id
        WHERE gc.group_id = ?
        ORDER BY c.code
        """,
        (group_id,),
    ).fetchall()

    member_count = conn.execute(
        "SELECT COUNT(*) AS n FROM group_members WHERE group_id = ?",
        (group_id,),
    ).fetchone()["n"]

    conn.close()

    return render_template(
        "group_detail.html",
        group=group,
        courses=courses,
        member_count=member_count,
        membership=member,
    )


if __name__ == "__main__":
    app.run(debug=True)