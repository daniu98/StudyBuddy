from flask import session, url_for

from studybuddy.db import get_db

from tests.helpers import check_redirect, signup_user, create_group


def test_signup(client):
    with client:
        client.get("/")
        failed_signup = client.post(
            url_for("auth.signup"),
            data={
                "name": "Placeholder5",
                "email": "5newplaceholder@placeholder",
                "password": "short",
            },
            follow_redirects=True,
        )
        assert check_redirect(failed_signup, url_for("auth.signup"))

        failed_signup = client.post(
            url_for("auth.signup"),
            data={"email": "5newplaceholder@placeholder", "password": "short"},
            follow_redirects=True,
        )
        assert check_redirect(failed_signup, url_for("auth.signup"))

        failed_signup = client.post(
            url_for("auth.signup"),
            data={"name": "Placeholder5", "password": "short"},
            follow_redirects=True,
        )
        assert check_redirect(failed_signup, url_for("auth.signup"))

        failed_signup = client.post(
            url_for("auth.signup"),
            data={"name": "Placeholder5", "email": "5newplaceholder@placeholder"},
            follow_redirects=True,
        )
        assert check_redirect(failed_signup, url_for("auth.signup"))

        successful_signup = client.post(
            url_for("auth.signup"),
            data={
                "name": "Placeholder5",
                "email": "5newplaceholder@placeholder",
                "password": "Placeholder",
            },
            follow_redirects=True,
        )
        assert check_redirect(successful_signup, url_for("auth.profile"))

        conn = get_db()
        row = conn.execute(
            "SELECT 1 FROM users WHERE name LIKE 'Placeholder5'",
        ).fetchone()
        assert row is not None
        conn.close()


def test_login_logout(client):
    with client:
        signup_user(client, "Placeholder", "blah@blah")
        exit = client.get(url_for("auth.logout"), follow_redirects=True)
        assert check_redirect(exit, url_for("main.home"))

        response_blocked = client.get(url_for("auth.profile"))
        assert response_blocked.status_code != 200

        failed_login = client.post(
            url_for("auth.login"),
            data={"email": "blah@blah", "password": "PL"},
            follow_redirects=True,
        )
        assert check_redirect(failed_login, url_for("auth.login"))

        failed_login = client.post(
            url_for("auth.login"),
            data={"password": "Placeholder"},
            follow_redirects=True,
        )
        assert check_redirect(failed_login, url_for("auth.login"))

        login = client.post(
            url_for("auth.login"),
            data={"email": "blah@blah", "password": "Placeholder"},
            follow_redirects=True,
        )
        assert check_redirect(login, url_for("main.home"))

        profile_access = client.get(url_for("auth.profile"))
        assert profile_access.status_code == 200
        assert "user_id" in session


def test_profile(client):
    with client:
        signup_user(client, "Placeholder", "blah@blah")
        to_profile = client.get(url_for("auth.profile"))
        assert to_profile.status_code == 200

        update_courses = client.post(
            url_for("auth.profile"),
            data={"course_ids": ["2", "3"]},
            follow_redirects=True,
        )
        assert check_redirect(update_courses, url_for("auth.profile"))

        update_courses = client.post(
            url_for("auth.profile"),
            data={"course_ids": ["1", "3"]},
            follow_redirects=True,
        )
        assert check_redirect(update_courses, url_for("auth.profile"))

        conn = get_db()
        user_course = conn.execute(
            "SELECT 1 FROM user_courses WHERE course_id = 1 AND user_id = ?",
            (session["user_id"],),
        ).fetchone()
        assert user_course is not None

        user_course = conn.execute(
            "SELECT 1 FROM user_courses WHERE course_id = 3 AND user_id = ?",
            (session["user_id"],),
        ).fetchone()
        assert user_course is not None
        conn.close()


def test_group_create(client):
    with client:
        client.get("/")
        creation_reject = client.post(
            url_for("groups.create_study_group"),
            data={"title": "LePlaceholder", "max_members": 8},
            follow_redirects=True,
        )
        assert check_redirect(creation_reject, url_for("auth.login"))

        signup_user(client, "Placeholder", "blah@blah")
        create_group = client.post(
            url_for("groups.create_study_group"),
            data={"title": "LePlaceholder", "max_members": 8},
            follow_redirects=True,
        )
        assert check_redirect(create_group, url_for("main.home"))

        conn = get_db()
        row = conn.execute(
            """
            SELECT 1 FROM study_groups
            WHERE title LIKE 'LePlaceholder' AND member_count = 1 AND max_members = 8
            """,
        ).fetchone()
        assert row is not None
        conn.close()


def test_join_leave_group(client):
    with client:
        signup_user(client, "Placeholder", "blah@blah")
        client.post(
            url_for("groups.create_study_group"),
            data={"title": "LePlaceholder2", "max_members": 8},
        )
        client.get(url_for("auth.logout"))
        client.post(
            url_for("auth.signup"),
            data={
                "name": "Placeholder6",
                "email": "6newplaceholder@placeholder",
                "password": "Placeholder",
            },
        )

        conn = get_db()
        row = conn.execute(
            "SELECT * FROM study_groups WHERE title LIKE 'LePlaceholder2'",
        ).fetchone()
        entry = client.post(
            url_for("groups.join_group", group_id=row["id"]),
            follow_redirects=True,
        )
        assert check_redirect(entry, url_for("groups.group_detail", group_id=row["id"]))

        exit = client.post(
            url_for("groups.leave_group", group_id=row["id"]),
            follow_redirects=True,
        )
        assert check_redirect(exit, url_for("groups.browse_groups"))
        conn.close()


def test_edit_group(client):
    with client:
        signup_user(client, "Placeholder", "blah@blah")
        client.post(
            url_for("groups.create_study_group"),
            data={"title": "LePlaceholder2", "max_members": 8},
        )
        conn = get_db()
        row = conn.execute(
            "SELECT * FROM study_groups WHERE title LIKE 'LePlaceholder2'",
        ).fetchone()
        client.post(
            url_for("groups.edit_group", group_id=row["id"]),
            data={
                "title": "LePlaceholder3",
                "description": "Suddenly, one day",
                "location": "Powell",
                "max_members": 2,
            },
        )

        row = conn.execute(
            """
            SELECT 1 FROM study_groups
            WHERE title LIKE 'LePlaceholder3'
              AND max_members = 2
              AND description LIKE 'Suddenly, one day'
              AND location LIKE 'Powell'
            """,
        ).fetchone()
        assert row is not None
        conn.close()

def test_group_search(client):
    signup_user(client, "Creator", "creator@example.com")
    create_group(client, "CS31 Midterm Crew", course_ids=["1"])
    browse = client.get("/groups?course_id=1")
    html = browse.get_data(as_text=True)
    assert browse.status_code == 200
    assert "CS31 Midterm Crew" in html, "search found group"
    assert "You are a member" in html, "user in group"
    assert not "Join group" in html