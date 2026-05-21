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


@app.route("/groups", methods=["GET"])
@login_required
def browse_groups():
    q = request.args.get("q", "").strip()
    raw_course_id = request.args.get("course_id", "").strip()
    course_id = None
    if raw_course_id:
        try:
            course_id = int(raw_course_id)
        except ValueError:
            course_id = None

    conn = get_db()
    user_id = session["user_id"]

    conditions = []
    params = []

    if q:
        pattern = f"%{q}%"
        conditions.append(
            """
            (
                sg.title LIKE ? COLLATE NOCASE
                OR sg.description LIKE ? COLLATE NOCASE
                OR sg.location LIKE ? COLLATE NOCASE
                OR sg.study_style LIKE ? COLLATE NOCASE
            )
            """
        )
        params.extend([pattern, pattern, pattern, pattern])

    if course_id is not None:
        conditions.append(
            """
            EXISTS (
                SELECT 1 FROM group_courses gc
                WHERE gc.group_id = sg.id AND gc.course_id = ?
            )
            """
        )
        params.append(course_id)

    where_clause = ""
    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)

    groups = conn.execute(
        f"""
        SELECT sg.id, sg.title, sg.description, sg.meeting_time, sg.location,
               sg.study_style, sg.max_members,
               (SELECT COUNT(*) FROM group_members gm WHERE gm.group_id = sg.id) AS member_count,
               (
                   SELECT GROUP_CONCAT(c.code, ', ')
                   FROM group_courses gc
                   JOIN courses c ON c.id = gc.course_id
                   WHERE gc.group_id = sg.id
               ) AS course_codes,
               EXISTS (
                   SELECT 1 FROM group_members gm
                   WHERE gm.group_id = sg.id AND gm.user_id = ?
               ) AS is_member
        FROM study_groups sg
        {where_clause}
        ORDER BY sg.title COLLATE NOCASE
        """,
        params + [user_id],
    ).fetchall()

    courses = conn.execute("SELECT * FROM courses ORDER BY code").fetchall()
    conn.close()

    return render_template(
        "browse_groups.html",
        groups=groups,
        courses=courses,
        q=q,
        course_id=course_id,
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


@app.route("/groups/<int:group_id>/messages", methods=["POST"])
@login_required
def post_group_message(group_id):
    body = request.form.get("body", "").strip()
    if not body:
        flash("Message cannot be empty.")
        return redirect(url_for("group_detail", group_id=group_id))

    if len(body) > 2000:
        flash("Message is too long (max 2000 characters).")
        return redirect(url_for("group_detail", group_id=group_id))

    conn = get_db()
    user_id = session["user_id"]

    group = conn.execute(
        "SELECT id FROM study_groups WHERE id = ?",
        (group_id,),
    ).fetchone()
    if group is None:
        conn.close()
        flash("That study group does not exist.")
        return redirect(url_for("dashboard"))

    if not user_is_group_member(conn, group_id, user_id):
        conn.close()
        flash("Only group members can post messages.")
        return redirect(url_for("dashboard"))

    try:
        conn.execute(
            "INSERT INTO messages (group_id, user_id, body) VALUES (?, ?, ?)",
            (group_id, user_id, body),
        )
        conn.commit()
    except sqlite3.Error:
        conn.rollback()
        flash("Could not send message. Please try again.")
    finally:
        conn.close()

    return redirect(url_for("group_detail", group_id=group_id))


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

    members = conn.execute(
        """
        SELECT u.name, gm.role, gm.joined_at
        FROM group_members gm
        JOIN users u ON gm.user_id = u.id
        WHERE gm.group_id = ?
        ORDER BY gm.role DESC, u.name COLLATE NOCASE
        """,
        (group_id,),
    ).fetchall()

    messages = conn.execute(
        """
        SELECT m.body, m.created_at, u.name AS author_name
        FROM messages m
        JOIN users u ON m.user_id = u.id
        WHERE m.group_id = ?
        ORDER BY m.created_at ASC
        """,
        (group_id,),
    ).fetchall()

    conn.close()

    return render_template(
        "group_detail.html",
        group=group,
        courses=courses,
        members=members,
        messages=messages,
        membership=member,
    )

@app.route("/study-groups/new", methods=["GET", "POST"])
@login_required
def create_study_group():
    user_id = session["user_id"]
    conn = get_db()

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip() or None
        meeting_time = request.form.get("meeting_time", "").strip() or None
        location = request.form.get("location", "").strip() or None
        study_style = request.form.get("study_style", "").strip() or None
        raw_max = request.form.get("max_members", "").strip()
        member_count = 1
        selected_course_ids = request.form.getlist("course_ids")

        if not title:
            conn.close()
            flash("Group title is required.")
            return redirect(url_for("create_study_group"))

        try:
            max_members = int(raw_max)
        except ValueError:
            conn.close()
            flash("Maximum members must be a whole number.")
            return redirect(url_for("create_study_group"))

        if max_members < 1:
            conn.close()
            flash("Maximum members must be at least 1.")
            return redirect(url_for("create_study_group"))

        try:
            cursor = conn.execute(
                """
                INSERT INTO study_groups (
                    title, description, max_members, member_count, meeting_time,
                    location, study_style, admin_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    title,
                    description,
                    max_members,
                    member_count,
                    meeting_time,
                    location,
                    study_style,
                    user_id,
                ),
            )
            group_id = cursor.lastrowid

            conn.execute(
                """
                INSERT INTO group_members (group_id, user_id, role)
                VALUES (?, ?, 'admin')
                """,
                (group_id, user_id),
            )

            for course_id in selected_course_ids:
                try:
                    cid = int(course_id)
                except ValueError:
                    continue
                exists = conn.execute(
                    "SELECT 1 FROM courses WHERE id = ?",
                    (cid,),
                ).fetchone()
                if exists:
                    conn.execute(
                        """
                        INSERT INTO group_courses (group_id, course_id)
                        VALUES (?, ?)
                        """,
                        (group_id, cid),
                    )

            conn.commit()
            flash("Study group created. You are the group admin.")
            return redirect(url_for("home"))
        except sqlite3.Error:
            conn.rollback()
            flash("Could not create the study group. Please try again.")
            return redirect(url_for("create_study_group"))
        finally:
            conn.close()

    courses = conn.execute("SELECT * FROM courses ORDER BY code").fetchall()
    conn.close()
    return render_template("create_study_group.html", courses=courses)

@login_required
def join_group(group_id):
    conn = get_db()
    user_id = session["user_id"]
    try:
        # check if user is already in group, go to except statement if so
        usergroups = conn.execute(
            "SELECT user_id FROM group_members WHERE user_id = ? AND group_id = ?",
            user_id,
            group_id,
        )
        if not usergroups.fetchone() is None:
            raise sqlite3.IntegrityError
        # check if group is full
        member_count = conn.execute(
            "SELECT member_count FROM study_groups WHERE id = ?",
            group_id,
        ).fetchone()["member_count"]
        max_members = conn.execute(
            "SELECT max_members FROM study_groups WHERE id = ?",
            group_id,
        ).fetchone()["max_members"]
        if member_count == max_members:
            raise AssertionError
        # put user in group's members list
        cursor = conn.execute(
            "INSERT INTO group_members (group_id, user_id) VALUES (?, ?)",
            (group_id, user_id),
        )
        # increase group member count by 1
        cursor2 = conn.execute("UPDATE study_groups SET member_count = ? WHERE id = ?", member_count + 1, group_id)
        conn.commit()
        flash("Group joined successfully.")
    except sqlite3.IntegrityError:
        flash("You have already joined the group.")
    except AssertionError:
        flash("Cannot join group. The group is already full.")
    except:
        flash("Unknown error joining group.")
    finally:
        conn.close()
    return group_detail(group_id)

@login_required
def leave_group(group_id):
    conn = get_db()
    user_id = session["user_id"]
    try:
        # check if user is not in group (may be unnecessary)
        usergroups = conn.execute(
            "SELECT user_id FROM group_members WHERE user_id = ? AND group_id = ?",
            user_id,
            group_id,
        )
        if usergroups.fetchone() is None:
            raise AssertionError
        # remove user from group's members list
        cursor = conn.execute(
            "DELETE FROM group_members WHERE group_id = ? AND user_id = ?",
            (group_id, user_id),
        )
        # decrease group member count by 1
        member_count = conn.execute(
            "SELECT member_count FROM study_groups WHERE id = ?",
            group_id,
        ).fetchone()["member_count"]
        cursor2 = conn.execute("UPDATE study_groups SET member_count = ? WHERE id = ?", member_count - 1, group_id)
        conn.commit()
        flash("Group left successfully.")
    except AssertionError:
        flash("You are not in that group.")
    except:
        flash("Unknown error leaving group.")
    finally:
        conn.close()
    return group_detail(group_id)

if __name__ == "__main__":
    app.run(debug=True)
