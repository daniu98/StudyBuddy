import sqlite3
from datetime import datetime

from flask import Blueprint, abort, flash, redirect, render_template, request, session, url_for

from .db import MESSAGE_MAX_LENGTH, get_db, login_required, user_is_group_member

bp = Blueprint("groups", __name__)

TITLE_MAX_LENGTH = 200
DESCRIPTION_MAX_LENGTH = 1000
LOCATION_MAX_LENGTH = 200
MAX_MEMBERS_LIMIT = 100
REVIEW_BODY_MAX_LENGTH = 1000

STUDY_STYLE_OPTIONS = [
    "Exam prep",
    "Problem sets",
    "Homework review",
    "Lecture review",
    "Project work",
    "General study",
]


def datetime_local_value(value):
    if not value:
        return ""

    value = value.strip()
    for fmt in ("%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(value, fmt).strftime("%Y-%m-%dT%H:%M")
        except ValueError:
            pass

    return ""


def meeting_time_storage_value(value):
    if not value:
        return None, None

    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M")
    except ValueError:
        return None, "Use the date and time picker to choose a valid meeting time."

    return parsed.strftime("%Y-%m-%d %H:%M"), None


def validate_group_form(form_data, min_members=1, max_members_limit=MAX_MEMBERS_LIMIT):
    errors = {}
    max_members = None
    meeting_time = None

    if not form_data["title"]:
        errors["title"] = "Group title is required."
    elif len(form_data["title"]) > TITLE_MAX_LENGTH:
        errors["title"] = f"Group title must be {TITLE_MAX_LENGTH} characters or fewer."

    if len(form_data["description"]) > DESCRIPTION_MAX_LENGTH:
        errors["description"] = (
            f"Description must be {DESCRIPTION_MAX_LENGTH} characters or fewer."
        )

    if len(form_data["location"]) > LOCATION_MAX_LENGTH:
        errors["location"] = f"Location must be {LOCATION_MAX_LENGTH} characters or fewer."

    try:
        max_members = int(form_data["max_members"])
    except ValueError:
        errors["max_members"] = "Maximum members must be a whole number."
        max_members = None

    if max_members is not None:
        if max_members < min_members:
            if min_members > 1:
                errors["max_members"] = (
                    f"Maximum members cannot be less than the current {min_members} members."
                )
            else:
                errors["max_members"] = "Maximum members must be at least 1."
        elif max_members > max_members_limit:
            errors["max_members"] = (
                f"Maximum members cannot be more than {max_members_limit}."
            )

    meeting_time, meeting_time_error = meeting_time_storage_value(form_data["meeting_time"])
    if meeting_time_error:
        errors["meeting_time"] = meeting_time_error

    if (
        form_data["study_style"]
        and form_data["study_style"] not in STUDY_STYLE_OPTIONS
    ):
        errors["study_style"] = "Choose one of the available study styles."

    return errors, max_members, meeting_time


def edit_group_form_data(group):
    return {
        "title": group["title"],
        "description": group["description"] or "",
        "location": group["location"] or "",
        "max_members": group["max_members"],
        "meeting_time": datetime_local_value(group["meeting_time"]),
        "study_style": group["study_style"] or "",
    }


def parse_calendar_datetime(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d %H:%M")
    except (TypeError, ValueError):
        return None


def calendar_date_label(parsed):
    return f"{parsed.strftime('%A, %B')} {parsed.day}, {parsed.year}"


def calendar_time_label(parsed):
    return parsed.strftime("%I:%M %p").lstrip("0")


@bp.route("/groups", methods=["GET"])
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
               ) AS is_member,
               (
                   SELECT ROUND(AVG(r.rating), 1)
                   FROM group_reviews r
                   WHERE r.group_id = sg.id
               ) AS avg_rating,
               (
                   SELECT COUNT(*)
                   FROM group_reviews r
                   WHERE r.group_id = sg.id
               ) AS review_count
        FROM study_groups sg
        {where_clause}
        ORDER BY sg.title COLLATE NOCASE
        """,
        [user_id] + params,
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


@bp.route("/dashboard")
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

    summary = {
        "group_count": len(groups),
        "messages_last_7_days": 0,
        "active_group_title": None,
        "active_group_count": 0,
        "engagement_badge": "Getting Started",
        "engagement_note": "Post your first group message this week.",
        "best_day_name": None,
        "best_day_count": 0,
    }

    message_stats = conn.execute(
        """
        SELECT COUNT(*) AS messages_last_7_days
        FROM messages m
        JOIN group_members gm ON gm.group_id = m.group_id
        WHERE gm.user_id = ?
          AND gm.user_id = m.user_id
          AND datetime(m.created_at) >= datetime('now', '-7 days')
        """,
        (user_id,),
    ).fetchone()
    summary["messages_last_7_days"] = message_stats["messages_last_7_days"]

    top_group = conn.execute(
        """
        SELECT sg.title, COUNT(*) AS message_count
        FROM messages m
        JOIN study_groups sg ON sg.id = m.group_id
        JOIN group_members gm ON gm.group_id = m.group_id
        WHERE gm.user_id = ?
          AND m.user_id = ?
          AND datetime(m.created_at) >= datetime('now', '-7 days')
        GROUP BY sg.id, sg.title
        ORDER BY message_count DESC, sg.title COLLATE NOCASE
        LIMIT 1
        """,
        (user_id, user_id),
    ).fetchone()
    if top_group is not None:
        summary["active_group_title"] = top_group["title"]
        summary["active_group_count"] = top_group["message_count"]

    best_day = conn.execute(
        """
        SELECT strftime('%w', m.created_at) AS weekday_number, COUNT(*) AS message_count
        FROM messages m
        JOIN group_members gm ON gm.group_id = m.group_id
        WHERE gm.user_id = ?
          AND m.user_id = ?
          AND datetime(m.created_at) >= datetime('now', '-7 days')
        GROUP BY weekday_number
        ORDER BY message_count DESC, weekday_number ASC
        LIMIT 1
        """,
        (user_id, user_id),
    ).fetchone()
    if best_day is not None:
        weekday_names = [
            "Sunday",
            "Monday",
            "Tuesday",
            "Wednesday",
            "Thursday",
            "Friday",
            "Saturday",
        ]
        summary["best_day_name"] = weekday_names[int(best_day["weekday_number"])]
        summary["best_day_count"] = best_day["message_count"]

    weekly_messages = summary["messages_last_7_days"]
    if weekly_messages >= 15:
        summary["engagement_badge"] = "Campus Connector"
        summary["engagement_note"] = "You are driving group collaboration this week."
    elif weekly_messages >= 8:
        summary["engagement_badge"] = "Discussion Leader"
        summary["engagement_note"] = "Great momentum. Keep your groups active."
    elif weekly_messages >= 3:
        summary["engagement_badge"] = "Consistent Collaborator"
        summary["engagement_note"] = "Nice consistency. You are building study habits."

    conn.close()
    return render_template("dashboard.html", groups=groups, summary=summary)


@bp.route("/calendar")
@login_required
def calendar():
    conn = get_db()
    user_id = session["user_id"]
    rows = conn.execute(
        """
        SELECT sg.id, sg.title, sg.meeting_time, sg.location, sg.study_style,
               (
                   SELECT GROUP_CONCAT(c.code, ', ')
                   FROM group_courses gc
                   JOIN courses c ON c.id = gc.course_id
                   WHERE gc.group_id = sg.id
               ) AS course_codes
        FROM study_groups sg
        JOIN group_members gm ON gm.group_id = sg.id
        WHERE gm.user_id = ?
          AND sg.meeting_time IS NOT NULL
        ORDER BY sg.title COLLATE NOCASE
        """,
        (user_id,),
    ).fetchall()
    conn.close()

    upcoming = []
    now = datetime.now()
    for row in rows:
        meeting_time = parse_calendar_datetime(row["meeting_time"])
        if meeting_time is not None and meeting_time >= now:
            upcoming.append((meeting_time, row))
    upcoming.sort(key=lambda item: (item[0], item[1]["title"].lower()))

    meetings_by_date = []
    for meeting_time, row in upcoming:
        date_label = calendar_date_label(meeting_time)
        meeting = {
            "id": row["id"],
            "title": row["title"],
            "time_label": calendar_time_label(meeting_time),
            "location": row["location"],
            "study_style": row["study_style"],
            "course_codes": row["course_codes"],
        }
        if not meetings_by_date or meetings_by_date[-1]["date_label"] != date_label:
            meetings_by_date.append({"date_label": date_label, "meetings": []})
        meetings_by_date[-1]["meetings"].append(meeting)

    return render_template("calendar.html", meetings_by_date=meetings_by_date)


@bp.route("/groups/<int:group_id>/messages", methods=["POST"])
@login_required
def post_group_message(group_id):
    body = request.form.get("body", "").strip()
    if not body:
        flash("Message cannot be empty.")
        return redirect(url_for("groups.group_detail", group_id=group_id))

    if len(body) > MESSAGE_MAX_LENGTH:
        flash(f"Message is too long (max {MESSAGE_MAX_LENGTH} characters).")
        return redirect(url_for("groups.group_detail", group_id=group_id))

    conn = get_db()
    user_id = session["user_id"]

    group = conn.execute(
        "SELECT id FROM study_groups WHERE id = ?",
        (group_id,),
    ).fetchone()
    if group is None:
        conn.close()
        abort(404, description="That study group does not exist.")

    if not user_is_group_member(conn, group_id, user_id):
        conn.close()
        flash("Only group members can post messages.")
        return redirect(url_for("groups.dashboard"))

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

    return redirect(url_for("groups.group_detail", group_id=group_id))


@bp.route("/groups/<int:group_id>")
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
        abort(404, description="That study group does not exist.")

    if member is None:
        conn.close()
        flash("You can only open groups you belong to.")
        return redirect(url_for("groups.dashboard"))

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
        ORDER BY m.created_at DESC
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


@bp.route("/groups/<int:group_id>/reviews", methods=["GET", "POST"])
@login_required
def group_reviews(group_id):
    conn = get_db()
    user_id = session["user_id"]

    group = conn.execute(
        """
        SELECT sg.id, sg.title
        FROM study_groups sg
        WHERE sg.id = ?
        """,
        (group_id,),
    ).fetchone()

    if group is None:
        conn.close()
        abort(404, description="That study group does not exist.")

    is_member = user_is_group_member(conn, group_id, user_id)

    if request.method == "POST":
        if not is_member:
            conn.close()
            flash("You must join this group before leaving a review.", "error")
            return redirect(url_for("groups.group_reviews", group_id=group_id))

        raw_rating = request.form.get("rating", "").strip()
        body = request.form.get("body", "").strip() or None

        try:
            rating = int(raw_rating)
        except ValueError:
            rating = None

        if rating is None or rating < 1 or rating > 5:
            conn.close()
            flash("Please choose a rating from 1 to 5 stars.", "error")
            return redirect(url_for("groups.group_reviews", group_id=group_id))

        if body and len(body) > REVIEW_BODY_MAX_LENGTH:
            conn.close()
            flash(
                f"Review text must be {REVIEW_BODY_MAX_LENGTH} characters or fewer.",
                "error",
            )
            return redirect(url_for("groups.group_reviews", group_id=group_id))

        existing = conn.execute(
            """
            SELECT id FROM group_reviews
            WHERE group_id = ? AND user_id = ?
            """,
            (group_id, user_id),
        ).fetchone()

        try:
            if existing:
                conn.execute(
                    """
                    UPDATE group_reviews
                    SET rating = ?, body = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE group_id = ? AND user_id = ?
                    """,
                    (rating, body, group_id, user_id),
                )
                flash("Your review has been updated.", "success")
            else:
                conn.execute(
                    """
                    INSERT INTO group_reviews (group_id, user_id, rating, body)
                    VALUES (?, ?, ?, ?)
                    """,
                    (group_id, user_id, rating, body),
                )
                flash("Your review has been saved.", "success")
            conn.commit()
        except sqlite3.Error:
            conn.rollback()
            flash("Could not save your review. Please try again.", "error")
        finally:
            conn.close()

        return redirect(url_for("groups.group_reviews", group_id=group_id))

    reviews = conn.execute(
        """
        SELECT r.rating, r.body, r.created_at, r.updated_at, u.name AS author_name
        FROM group_reviews r
        JOIN users u ON u.id = r.user_id
        WHERE r.group_id = ?
        ORDER BY r.created_at DESC
        """,
        (group_id,),
    ).fetchall()

    summary = conn.execute(
        """
        SELECT ROUND(AVG(rating), 1) AS avg_rating, COUNT(*) AS review_count
        FROM group_reviews
        WHERE group_id = ?
        """,
        (group_id,),
    ).fetchone()

    user_review = None
    if is_member:
        user_review = conn.execute(
            """
            SELECT rating, body
            FROM group_reviews
            WHERE group_id = ? AND user_id = ?
            """,
            (group_id, user_id),
        ).fetchone()

    conn.close()

    return render_template(
        "group_reviews.html",
        group=group,
        reviews=reviews,
        summary=summary,
        is_member=is_member,
        user_review=user_review,
        review_body_max_length=REVIEW_BODY_MAX_LENGTH,
    )


@bp.route("/groups/<int:group_id>/edit", methods=["GET", "POST"])
@login_required
def edit_group(group_id):
    conn = get_db()
    user_id = session["user_id"]

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
        abort(404, description="That study group does not exist.")

    membership = conn.execute(
        """
        SELECT role
        FROM group_members
        WHERE group_id = ? AND user_id = ?
        """,
        (group_id, user_id),
    ).fetchone()

    if membership is None or membership["role"] != "admin":
        conn.close()
        flash("You no longer have permission to edit this study group.", "error")
        return redirect(url_for("groups.dashboard"))

    member_count = conn.execute(
        "SELECT COUNT(*) AS n FROM group_members WHERE group_id = ?",
        (group_id,),
    ).fetchone()["n"]
    min_members = max(1, member_count)
    max_members_limit = max(MAX_MEMBERS_LIMIT, member_count)

    errors = {}
    form_data = edit_group_form_data(group)

    if request.method == "POST":
        form_data = {
            "title": request.form.get("title", "").strip(),
            "description": request.form.get("description", "").strip(),
            "location": request.form.get("location", "").strip(),
            "max_members": request.form.get("max_members", "").strip(),
            "meeting_time": request.form.get("meeting_time", "").strip(),
            "study_style": request.form.get("study_style", "").strip(),
        }

        errors, max_members, meeting_time = validate_group_form(
            form_data,
            min_members=min_members,
            max_members_limit=max_members_limit,
        )

        if not errors:
            try:
                conn.execute(
                    """
                    UPDATE study_groups
                    SET title = ?, description = ?, location = ?, max_members = ?,
                        meeting_time = ?, study_style = ?
                    WHERE id = ?
                    """,
                    (
                        form_data["title"],
                        form_data["description"] or None,
                        form_data["location"] or None,
                        max_members,
                        meeting_time,
                        form_data["study_style"] or None,
                        group_id,
                    ),
                )
                conn.commit()
                flash("Study group updated.", "success")
                conn.close()
                return redirect(url_for("groups.group_detail", group_id=group_id))
            except sqlite3.Error:
                conn.rollback()
                errors["form"] = "Could not update the study group. Please try again."

    conn.close()

    return render_template(
        "edit_group.html",
        group=group,
        errors=errors,
        form_data=form_data,
        meeting_time_value=form_data["meeting_time"],
        study_style_options=STUDY_STYLE_OPTIONS,
        title_max_length=TITLE_MAX_LENGTH,
        description_max_length=DESCRIPTION_MAX_LENGTH,
        location_max_length=LOCATION_MAX_LENGTH,
        max_members_limit=max_members_limit,
        min_members=min_members,
    )


@bp.route("/study-groups/new", methods=["GET", "POST"])
@login_required
def create_study_group():
    user_id = session["user_id"]
    conn = get_db()
    courses = conn.execute("SELECT * FROM courses ORDER BY code").fetchall()

    errors = {}
    form_data = {
        "title": "",
        "description": "",
        "location": "",
        "max_members": "6",
        "meeting_time": "",
        "study_style": "",
    }
    selected_course_ids = []

    if request.method == "POST":
        form_data = {
            "title": request.form.get("title", "").strip(),
            "description": request.form.get("description", "").strip(),
            "location": request.form.get("location", "").strip(),
            "max_members": request.form.get("max_members", "").strip(),
            "meeting_time": request.form.get("meeting_time", "").strip(),
            "study_style": request.form.get("study_style", "").strip(),
        }
        selected_course_ids = request.form.getlist("course_ids")

        errors, max_members, meeting_time = validate_group_form(form_data)

        if not errors:
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
                        form_data["title"],
                        form_data["description"] or None,
                        max_members,
                        1,
                        meeting_time,
                        form_data["location"] or None,
                        form_data["study_style"] or None,
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
                conn.close()
                flash("Study group created. You are the group admin.")
                return redirect(url_for("main.home"))
            except sqlite3.Error:
                conn.rollback()
                errors["form"] = "Could not create the study group. Please try again."

    conn.close()
    return render_template(
        "create_study_group.html",
        courses=courses,
        errors=errors,
        form_data=form_data,
        selected_course_ids=selected_course_ids,
        study_style_options=STUDY_STYLE_OPTIONS,
        title_max_length=TITLE_MAX_LENGTH,
        description_max_length=DESCRIPTION_MAX_LENGTH,
        location_max_length=LOCATION_MAX_LENGTH,
        max_members_limit=MAX_MEMBERS_LIMIT,
    )


@bp.route("/groups/<int:group_id>/join", methods=["POST"])
@login_required
def join_group(group_id):
    conn = get_db()
    user_id = session["user_id"]
    try:
        group = conn.execute(
            "SELECT max_members FROM study_groups WHERE id = ?",
            (group_id,),
        ).fetchone()
        if group is None:
            flash("That study group does not exist.")
            return redirect(url_for("groups.browse_groups"))

        if conn.execute(
            "SELECT 1 FROM group_members WHERE user_id = ? AND group_id = ?",
            (user_id, group_id),
        ).fetchone():
            flash("You have already joined the group.")
            return redirect(url_for("groups.group_detail", group_id=group_id))

        member_count = conn.execute(
            "SELECT COUNT(*) AS n FROM group_members WHERE group_id = ?",
            (group_id,),
        ).fetchone()["n"]
        if member_count >= group["max_members"]:
            flash("Cannot join group. The group is already full.")
            return redirect(url_for("groups.browse_groups"))

        conn.execute(
            "INSERT INTO group_members (group_id, user_id) VALUES (?, ?)",
            (group_id, user_id),
        )
        conn.execute(
            """
            UPDATE study_groups
            SET member_count = (
                SELECT COUNT(*) FROM group_members WHERE group_id = ?
            )
            WHERE id = ?
            """,
            (group_id, group_id),
        )
        conn.commit()
        flash("Group joined successfully.")
        return redirect(url_for("groups.group_detail", group_id=group_id))
    except sqlite3.Error:
        conn.rollback()
        flash("Could not join the group. Please try again.")
        return redirect(url_for("groups.browse_groups"))
    finally:
        conn.close()


@bp.route("/groups/<int:group_id>/leave", methods=["POST"])
@login_required
def leave_group(group_id):
    conn = get_db()
    user_id = session["user_id"]
    try:
        member = conn.execute("SELECT role FROM group_members WHERE user_id = ? AND group_id = ?", (user_id, group_id)).fetchone()
        if member is None:
            flash("You are not in that group.")
            return redirect(url_for("groups.browse_groups"))
        elif member["role"] == "admin":
            flash("Group admins cannot leave their own group yet. Edit the group instead.")
            return redirect(url_for("groups.group_detail", group_id=group_id))

        conn.execute(
            "DELETE FROM group_members WHERE group_id = ? AND user_id = ?",
            (group_id, user_id),
        )
        conn.execute(
            """
            UPDATE study_groups
            SET member_count = (
                SELECT COUNT(*) FROM group_members WHERE group_id = ?
            )
            WHERE id = ?
            """,
            (group_id, group_id),
        )
        conn.commit()
        flash("Group left successfully.")
        return redirect(url_for("groups.browse_groups"))
    except sqlite3.Error:
        conn.rollback()
        flash("Could not leave the group. Please try again.")
        return redirect(url_for("groups.group_detail", group_id=group_id))
    finally:
        conn.close()
