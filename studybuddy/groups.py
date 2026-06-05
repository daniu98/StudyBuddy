import secrets
import sqlite3
from datetime import datetime

from flask import Blueprint, abort, flash, redirect, render_template, request, session, url_for

from .db import MESSAGE_MAX_LENGTH, get_db, login_required
from .repositories import courses as courses_repo
from .repositories import messages as messages_repo
from .repositories import reviews as reviews_repo
from .repositories import study_groups as groups_repo

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


def new_invite_code():
    return secrets.token_urlsafe(6)


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


WEEKDAY_NAMES = [
    "Sunday",
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
]


def build_activity_summary(conn, user_id, joined_group_count):
    summary = {
        "group_count": joined_group_count,
        "messages_last_7_days": 0,
        "active_group_title": None,
        "active_group_count": 0,
        "engagement_badge": "Getting Started",
        "engagement_note": "Post your first group message this week.",
        "best_day_name": None,
        "best_day_count": 0,
    }

    summary["messages_last_7_days"] = messages_repo.count_last_7_days_for_user(
        conn, user_id
    )

    top_group = messages_repo.top_group_last_7_days(conn, user_id)
    if top_group is not None:
        summary["active_group_title"] = top_group["title"]
        summary["active_group_count"] = top_group["message_count"]

    best_day = messages_repo.best_day_last_7_days(conn, user_id)
    if best_day is not None:
        summary["best_day_name"] = WEEKDAY_NAMES[int(best_day["weekday_number"])]
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

    return summary


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
    try:
        user_id = session["user_id"]
        group_rows = groups_repo.search(conn, q=q or None, course_id=course_id)
        member_group_ids = groups_repo.member_group_ids(conn, user_id)

        groups = []
        for row in group_rows:
            group = dict(row)
            group["is_member"] = row["id"] in member_group_ids
            groups.append(group)

        courses = courses_repo.list_all(conn)
    finally:
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
    try:
        user_id = session["user_id"]
        groups = groups_repo.list_for_user_dashboard(conn, user_id)
        summary = build_activity_summary(conn, user_id, len(groups))
    finally:
        conn.close()
    return render_template("dashboard.html", groups=groups, summary=summary)


@bp.route("/calendar")
@login_required
def calendar():
    conn = get_db()
    try:
        rows = groups_repo.calendar_meetings(conn, session["user_id"])
    finally:
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
    try:
        user_id = session["user_id"]

        if not groups_repo.exists(conn, group_id):
            abort(404, description="That study group does not exist.")

        if not groups_repo.is_member(conn, group_id, user_id):
            flash("Only group members can post messages.")
            return redirect(url_for("groups.dashboard"))

        messages_repo.insert(conn, group_id, user_id, body)
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
    try:
        user_id = session["user_id"]
        member = groups_repo.membership(conn, group_id, user_id)
        group = groups_repo.find_with_admin(conn, group_id)

        if group is None:
            abort(404, description="That study group does not exist.")

        if member is None:
            flash("You can only open groups you belong to.")
            return redirect(url_for("groups.dashboard"))

        courses = groups_repo.list_courses(conn, group_id)
        members = groups_repo.list_members(conn, group_id)
        messages = messages_repo.list_for_group(conn, group_id)

        invite_url = None
        if member["role"] == "admin" and group["invite_code"]:
            invite_url = url_for(
                "groups.join_via_invite",
                code=group["invite_code"],
                _external=True,
            )
    finally:
        conn.close()

    return render_template(
        "group_detail.html",
        group=group,
        courses=courses,
        members=members,
        messages=messages,
        membership=member,
        invite_url=invite_url,
    )


@bp.route("/groups/<int:group_id>/reviews", methods=["GET", "POST"])
@login_required
def group_reviews(group_id):
    conn = get_db()
    try:
        user_id = session["user_id"]
        group = groups_repo.find_for_reviews_page(conn, group_id)

        if group is None:
            abort(404, description="That study group does not exist.")

        is_member = groups_repo.is_member(conn, group_id, user_id)

        if request.method == "GET":
            reviews = reviews_repo.list_for_group(conn, group_id)
            summary = reviews_repo.summary_for_group(conn, group_id)
            user_review = (
                reviews_repo.user_review_body(conn, group_id, user_id)
                if is_member
                else None
            )
            return render_template(
                "group_reviews.html",
                group=group,
                reviews=reviews,
                summary=summary,
                is_member=is_member,
                user_review=user_review,
                review_body_max_length=REVIEW_BODY_MAX_LENGTH,
            )

        if request.method == "POST":
            if not is_member:
                flash("You must join this group before leaving a review.", "error")
                return redirect(url_for("groups.group_reviews", group_id=group_id))

            raw_rating = request.form.get("rating", "").strip()
            body = request.form.get("body", "").strip() or None

            try:
                rating = int(raw_rating)
            except ValueError:
                rating = None

            if rating is None or rating < 1 or rating > 5:
                flash("Please choose a rating from 1 to 5 stars.", "error")
                return redirect(url_for("groups.group_reviews", group_id=group_id))

            if body and len(body) > REVIEW_BODY_MAX_LENGTH:
                flash(
                    f"Review text must be {REVIEW_BODY_MAX_LENGTH} characters or fewer.",
                    "error",
                )
                return redirect(url_for("groups.group_reviews", group_id=group_id))

            existing = reviews_repo.find_user_review(conn, group_id, user_id)
            try:
                if existing:
                    reviews_repo.update(conn, group_id, user_id, rating, body)
                    flash("Your review has been updated.", "success")
                else:
                    reviews_repo.insert(conn, group_id, user_id, rating, body)
                    flash("Your review has been saved.", "success")
                conn.commit()
            except sqlite3.Error:
                conn.rollback()
                flash("Could not save your review. Please try again.", "error")

            return redirect(url_for("groups.group_reviews", group_id=group_id))
    finally:
        conn.close()


@bp.route("/groups/<int:group_id>/edit", methods=["GET", "POST"])
@login_required
def edit_group(group_id):
    conn = get_db()
    try:
        user_id = session["user_id"]
        group = groups_repo.find_with_admin(conn, group_id)

        if group is None:
            abort(404, description="That study group does not exist.")

        membership = groups_repo.membership_role(conn, group_id, user_id)

        if membership is None or membership["role"] != "admin":
            flash("You no longer have permission to edit this study group.", "error")
            return redirect(url_for("groups.dashboard"))

        member_count = groups_repo.member_count(conn, group_id)
        min_members = max(1, member_count)
        max_members_limit = max(MAX_MEMBERS_LIMIT, member_count)

        errors = {}
        form_data = edit_group_form_data(group)

        if request.method == "GET":
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
                    groups_repo.update(
                        conn,
                        group_id,
                        form_data["title"],
                        form_data["description"] or None,
                        form_data["location"] or None,
                        max_members,
                        meeting_time,
                        form_data["study_style"] or None,
                    )
                    conn.commit()
                    flash("Study group updated.", "success")
                    return redirect(url_for("groups.group_detail", group_id=group_id))
                except sqlite3.Error:
                    conn.rollback()
                    errors["form"] = "Could not update the study group. Please try again."
    finally:
        conn.close()

    return render_template(
        "edit_group.html",
        group=group,
        errors=errors,
        form_data=form_data,
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
    try:
        courses = courses_repo.list_all(conn)

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

        if request.method == "GET":
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
                invite_code = new_invite_code()
                try:
                    group_id = groups_repo.create(
                        conn,
                        form_data["title"],
                        form_data["description"] or None,
                        max_members,
                        meeting_time,
                        form_data["location"] or None,
                        form_data["study_style"] or None,
                        user_id,
                        invite_code,
                    )
                    groups_repo.add_admin_member(conn, group_id, user_id)

                    for course_id in selected_course_ids:
                        try:
                            cid = int(course_id)
                        except ValueError:
                            continue
                        if courses_repo.exists(conn, cid):
                            groups_repo.link_course(conn, group_id, cid)

                    conn.commit()
                    flash("Study group created. You are the group admin.")
                    return redirect(url_for("main.home"))
                except sqlite3.Error:
                    conn.rollback()
                    errors["form"] = "Could not create the study group. Please try again."
    finally:
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


@bp.route("/invite/<code>")
@login_required
def join_via_invite(code):
    conn = get_db()
    try:
        user_id = session["user_id"]
        group = groups_repo.find_by_invite_code(conn, code)

        if group is None:
            flash("That invite link is invalid or expired.")
            return redirect(url_for("groups.browse_groups"))

        group_id = group["id"]
        if groups_repo.is_member(conn, group_id, user_id):
            flash("You are already in this group.")
            return redirect(url_for("groups.group_detail", group_id=group_id))

        if group["member_count"] >= group["max_members"]:
            flash("This group is full.")
            return redirect(url_for("groups.browse_groups"))

        groups_repo.add_member(conn, group_id, user_id, role="member")
        conn.commit()
        flash("You joined the group via invite link.")
        return redirect(url_for("groups.group_detail", group_id=group_id))
    except sqlite3.Error:
        conn.rollback()
        flash("Could not join the group. Please try again.")
        return redirect(url_for("groups.browse_groups"))
    finally:
        conn.close()


@bp.route("/groups/<int:group_id>/invite", methods=["POST"])
@login_required
def create_group_invite(group_id):
    conn = get_db()
    try:
        user_id = session["user_id"]
        group = groups_repo.admin_and_invite(conn, group_id)
        if group is None:
            flash("That study group does not exist.")
            return redirect(url_for("groups.dashboard"))

        if group["admin_id"] != user_id:
            flash("Only the group admin can create invite links.")
            return redirect(url_for("groups.group_detail", group_id=group_id))

        if not group["invite_code"]:
            groups_repo.set_invite_code(conn, group_id, new_invite_code())
            conn.commit()
            flash("Invite link created.")
        else:
            flash("Invite link is already active.")
    finally:
        conn.close()

    return redirect(url_for("groups.group_detail", group_id=group_id))


@bp.route("/groups/<int:group_id>/join", methods=["POST"])
@login_required
def join_group(group_id):
    conn = get_db()
    try:
        user_id = session["user_id"]
        group = groups_repo.find_max_members(conn, group_id)
        if group is None:
            flash("That study group does not exist.")
            return redirect(url_for("groups.browse_groups"))

        if groups_repo.is_member(conn, group_id, user_id):
            flash("You have already joined the group.")
            return redirect(url_for("groups.group_detail", group_id=group_id))

        member_count = groups_repo.member_count(conn, group_id)
        if member_count >= group["max_members"]:
            flash("Cannot join group. The group is already full.")
            return redirect(url_for("groups.browse_groups"))

        conn.execute(
            "INSERT INTO group_members (group_id, user_id) VALUES (?, ?)",
            (group_id, user_id),
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
    try:
        user_id = session["user_id"]
        member = groups_repo.membership_role(conn, group_id, user_id)
        if member is None:
            flash("You are not in that group.")
            return redirect(url_for("groups.browse_groups"))
        if member["role"] == "admin":
            flash("Group admins cannot leave their own group yet. Edit the group instead.")
            return redirect(url_for("groups.group_detail", group_id=group_id))

        conn.execute(
            "DELETE FROM group_members WHERE group_id = ? AND user_id = ?",
            (group_id, user_id),
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
