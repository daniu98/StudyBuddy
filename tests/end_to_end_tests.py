from studybuddy.db import get_db

from tests.helpers import check_redirect, create_group, signup_user


def test_create_group_and_find_by_course(client):
    signup_user(client, "Creator", "creator@example.com")
    create_group(client, "CS31 Midterm Crew", course_ids=["1"])

    browse = client.get("/groups?course_id=1")
    html = browse.get_data(as_text=True)
    assert browse.status_code == 200
    assert "CS31 Midterm Crew" in html
    assert "You are a member" in html
    assert "Join group" not in html


def test_join_search_and_message_flow(client):
    signup_user(client, "Owner", "owner@example.com")
    create_group(client, "Shared Notes Group", course_ids=["1"])

    conn = get_db()
    group = conn.execute(
        "SELECT id FROM study_groups WHERE title = 'Shared Notes Group'"
    ).fetchone()
    group_id = group["id"]
    conn.close()

    client.get("/logout", follow_redirects=True)
    signup_user(client, "Member", "member@example.com")

    join = client.post(f"/groups/{group_id}/join", follow_redirects=True)
    assert check_redirect(join, f"/groups/{group_id}")

    searched = client.get("/groups?q=Shared")
    html = searched.get_data(as_text=True)
    assert "Shared Notes Group" in html
    assert "You are a member" in html
    assert "Join group" not in html

    post = client.post(
        f"/groups/{group_id}/messages",
        data={"body": "First study session this week."},
        follow_redirects=True,
    )
    assert post.status_code == 200
    assert "First study session this week." in post.get_data(as_text=True)

    dashboard = client.get("/dashboard")
    dashboard_html = dashboard.get_data(as_text=True)
    assert dashboard.status_code == 200
    assert "Your Activity Snapshot" in dashboard_html
    assert "Shared Notes Group" in dashboard_html


def test_group_review_flow(client):
    signup_user(client, "Reviewer", "reviewer@example.com")
    create_group(client, "Review Target Group", course_ids=["2"])

    conn = get_db()
    group = conn.execute(
        "SELECT id FROM study_groups WHERE title = 'Review Target Group'"
    ).fetchone()
    group_id = group["id"]
    conn.close()

    submit = client.post(
        f"/groups/{group_id}/reviews",
        data={"rating": "5", "body": "Very helpful group."},
        follow_redirects=True,
    )
    assert submit.status_code == 200
    assert "Very helpful group." in submit.get_data(as_text=True)

    browse = client.get("/groups")
    browse_html = browse.get_data(as_text=True)
    assert "Review Target Group" in browse_html
    assert "View reviews" in browse_html
    assert "5.0" in browse_html


def test_join_via_invite_link(client):
    signup_user(client, "Host", "host@example.com")
    create_group(client, "Invite Only Group", course_ids=["1"])

    conn = get_db()
    group = conn.execute(
        "SELECT id, invite_code FROM study_groups WHERE title = 'Invite Only Group'"
    ).fetchone()
    group_id = group["id"]
    invite_code = group["invite_code"]
    conn.close()
    assert invite_code

    detail = client.get(f"/groups/{group_id}")
    detail_html = detail.get_data(as_text=True)
    assert f"/invite/{invite_code}" in detail_html

    client.get("/logout", follow_redirects=True)
    signup_user(client, "Guest", "guest@example.com")

    join = client.get(f"/invite/{invite_code}", follow_redirects=True)
    assert join.status_code == 200
    assert check_redirect(join, f"/groups/{group_id}")
    assert "Invite Only Group" in join.get_data(as_text=True)
