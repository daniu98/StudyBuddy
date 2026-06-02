import pytest
from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash
from studybuddy import create_app
from studybuddy.db import get_db

@pytest.fixture()
def app():
    app = create_app()
    app.config.update({
        "TESTING": True,
    })
    yield app

@pytest.fixture()
def client(app):
    return app.test_client()

@pytest.fixture()
def runner(app):
    return app.test_cli_runner()

def test_signup(client):
    with client:
        init = client.get("/")
        failed_signup = client.post(url_for("auth.signup"), data={
            "name": "Placeholder5",
            "email": "5newplaceholder@placeholder",
            "password": "short",
        }, follow_redirects=True)
        assert len(failed_signup.history) == 1
        assert failed_signup.request.path == url_for("auth.signup"), "Redirect on failed signup (password too short)"
        
        failed_signup = client.post(url_for("auth.signup"), data={
            "email": "5newplaceholder@placeholder",
            "password": "short",
        }, follow_redirects=True)
        assert len(failed_signup.history) == 1
        assert failed_signup.request.path == url_for("auth.signup"), "Redirect on failed signup (no username)"
        
        failed_signup = client.post(url_for("auth.signup"), data={
            "name": "Placeholder5",
            "password": "short",
        }, follow_redirects=True)
        assert len(failed_signup.history) == 1
        assert failed_signup.request.path == url_for("auth.signup"), "Redirect on failed signup (no email)"
        
        failed_signup = client.post(url_for("auth.signup"), data={
            "name": "Placeholder5",
            "email": "5newplaceholder@placeholder",
        }, follow_redirects=True)
        assert len(failed_signup.history) == 1
        assert failed_signup.request.path == url_for("auth.signup"), "Redirect on failed signup (no password)"
        
        successful_signup = client.post(url_for("auth.signup"), data={
            "name": "Placeholder5",
            "email": "5newplaceholder@placeholder",
            "password": "Placeholder",
        }, follow_redirects=True)
        assert len(successful_signup.history) == 1
        assert successful_signup.request.path == url_for("auth.profile"), "Redirect on successful user creation"
        
        conn = get_db()
        row = conn.execute(
            "SELECT 1 FROM users WHERE name LIKE 'Placeholder5'",
        ).fetchone()
        assert row is not None, "Verify new user created successfully"
        
        clean = conn.execute(
            "DELETE FROM users WHERE name LIKE 'Placeholder5'",
        )
        conn.commit()
        conn.close()

def test_login_logout(client):
    testuser = client.post("/signup", data={
        "name": "blah",
        "email": "blah@blah",
        "password": "Placeholder",
    })
    exit = client.get("/logout", follow_redirects=True)
    assert exit.status_code == 200, "Logging out"
    assert len(exit.history) == 1
    assert exit.request.path == "/", "Successful logout and redirect"
    response_blocked = client.get("/profile")
    assert response_blocked.status_code != 200, "Login required restriction works"
    
    failed_response = client.post("/login", data={
        "email": "blah@blah",
        "password": "PL",
    }, follow_redirects=True)
    assert len(failed_response.history) == 1
    assert failed_response.request.path == "/login", "Failed login and redirect"
    assert failed_response.status_code == 200
    
    response = client.post("/login", data={
        "email": "blah@blah",
        "password": "Placeholder",
    }, follow_redirects=True)
    assert len(response.history) == 1
    assert response.request.path == "/", "Successful login and redirect"
    assert response.status_code == 200

    response2 = client.get("/profile")
    assert response2.status_code == 200, "User profile accessible after login"

def test_profile(client):
    with client:
        login_placeholder(client)
        
        response2 = client.get("/profile")
        assert response2.status_code == 200
        assert "user_id" in session
        
        response3 = client.post("/profile", data={
            "course_ids": ["2"],
        }, follow_redirects=True)
        assert "user_id" in session
        assert len(response3.history) == 1
        assert response3.request.path == "/profile", "Successful course list update and redirect"
        assert response3.status_code == 200
        
        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE email LIKE 'blah@blah'").fetchone()
        #courses2 = conn.execute(
        #    "SELECT * FROM courses"
        #)
        userid:int = user["id"]
        user_course = conn.execute(
            "SELECT 1 FROM user_courses WHERE course_id == 2",
        )
        assert user_course is not None, "Verify courses updated"
        #for x in range (1,2):
        #    row = courses2.fetchone()
        #    user_course = conn.execute(
        #        "SELECT FROM user_courses WHERE user_id == ? AND course_id == ?",
        #        user_id, row["id"],
        #    )
        #    assert user_course is not None, "Verify courses updated"
        
        clean = conn.execute(
            "DELETE FROM user_courses WHERE course_id == 2"
        )
        conn.commit()
        conn.close()
        
    
def test_group_create(client):
    with client:
        response_reject = client.post("/study-groups/new", data={
            "title": "LePlaceholder",
            "max_members": 8,
            "selected_course_ids": "",
        }, follow_redirects=True)
        assert len(response_reject.history) == 1
        assert response_reject.request.path == "/login", "Accessing group creation without login"
        login_placeholder(client)
        response2 = client.post("/study-groups/new", data={
            "title": "LePlaceholder",
            "max_members": 8,
            "selected_course_ids": "",
        }, follow_redirects=True)
        assert len(response2.history) == 1
        assert response2.request.path == "/", "Successful group creation and redirect"
        conn = get_db()
        row = conn.execute(
            "SELECT 1 FROM study_groups WHERE title LIKE 'LePlaceholder' AND member_count == 1 AND max_members == 8",
        ).fetchone()
        assert row is not None, "Verifying new group is in database with correct attributes"
        clean = conn.execute(
            "DELETE FROM study_groups WHERE title LIKE 'LePlaceholder'",
        )
        conn.commit()
        conn.close()

def test_join_leave_group(client):
    with client:
        login_placeholder(client)
        response = client.post("/study-groups/new", data={
            "title": "LePlaceholder2",
            "max_members": 8,
            "selected_course_ids": "",
        })
        exit = client.get("/logout")
        response2 = client.post("/signup", data={
            "name": "Placeholder6",
            "email": "6newplaceholder@placeholder",
            "password": "Placeholder",
        })

        conn = get_db()
        row = conn.execute(
            "SELECT * FROM study_groups WHERE title LIKE 'LePlaceholder2'",
        ).fetchone()
        entry = client.post("/groups/" + str(row["id"]) + "/join", follow_redirects=True)
        assert len(entry.history) == 1
        assert entry.request.path == url_for("groups.group_detail", group_id=row["id"]), "Successful group joining"

        exit = client.post("/groups/" + str(row["id"]) + "/leave", follow_redirects=True)
        assert len(exit.history) == 1
        assert exit.request.path == url_for("groups.browse_groups"), "Successful group leaving"

        clean = conn.execute(
            "DELETE FROM users WHERE name LIKE 'Placeholder6'",
        )
        clean = conn.execute(
            "DELETE FROM study_groups WHERE title LIKE 'LePlaceholder2'",
        )
        conn.commit()
        conn.close()

def test_edit_group(client):
    with client:
        login_placeholder(client)
        response = client.post("/study-groups/new", data={
            "title": "LePlaceholder2",
            "max_members": 8,
            "selected_course_ids": "",
        })
        conn = get_db()
        row = conn.execute(
            "SELECT * FROM study_groups WHERE title LIKE 'LePlaceholder2'",
        ).fetchone()
        response2 = client.get(url_for('groups.edit_group', group_id=row["id"]))
        editing = client.post(url_for('groups.edit_group', group_id=row["id"]), data={
            "title": "LePlaceholder3",
            "description": "Suddenly, one day",
            "location": "Powell",
            "max_members": 2,
        })

        row = conn.execute(
            "SELECT 1 FROM study_groups WHERE title LIKE 'LePlaceholder3' AND max_members == 2 AND description LIKE 'Suddenly, one day' AND location LIKE 'Powell'",
        ).fetchone()
        assert row is not None, "Verifying edited group is in database with correct attributes"

        clean = conn.execute(
            "DELETE FROM study_groups WHERE title LIKE 'LePlaceholder3'",
        )
        conn.commit()
        conn.close()


def login_placeholder(client):
    response = client.post("/login", data={
        "email": "blah@blah",
        "password": "Placeholder",
    })


if __name__ == "__main__":
    pytest.main([__file__, "-v"])