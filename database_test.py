import pytest
import shutil
from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash
from studybuddy import create_app
from studybuddy.db import get_db

# temporarily move current database until testing complete
# since new database needs to be created for each test to ensure independence
@pytest.fixture(scope="session", autouse=True)
def cache_db():
    shutil.move("studybuddy.db", "tempdb.db")
    yield
    shutil.move("tempdb.db", "studybuddy.db")

@pytest.fixture()
def init_db():
    with open("init_db.py") as file:
        exec(file.read())

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

def test_signup(client, init_db):
    with client:
        init = client.get("/")
        failed_signup = client.post(url_for("auth.signup"), data={
            "name": "Placeholder5",
            "email": "5newplaceholder@placeholder",
            "password": "short",
        }, follow_redirects=True)
        assert check_redirect(failed_signup, url_for("auth.signup")), "Redirect on failed signup (password too short)"
        
        failed_signup = client.post(url_for("auth.signup"), data={
            "email": "5newplaceholder@placeholder",
            "password": "short",
        }, follow_redirects=True)
        assert check_redirect(failed_signup, url_for("auth.signup")), "Redirect on failed signup (no username)"
        
        failed_signup = client.post(url_for("auth.signup"), data={
            "name": "Placeholder5",
            "password": "short",
        }, follow_redirects=True)
        assert check_redirect(failed_signup, url_for("auth.signup")), "Redirect on failed signup (no email)"
        
        failed_signup = client.post(url_for("auth.signup"), data={
            "name": "Placeholder5",
            "email": "5newplaceholder@placeholder",
        }, follow_redirects=True)
        assert check_redirect(failed_signup, url_for("auth.signup")), "Redirect on failed signup (no password)"
        
        successful_signup = client.post(url_for("auth.signup"), data={
            "name": "Placeholder5",
            "email": "5newplaceholder@placeholder",
            "password": "Placeholder",
        }, follow_redirects=True)
        assert check_redirect(successful_signup, url_for("auth.profile")), "Redirect on successful user creation"
        
        conn = get_db()
        row = conn.execute(
            "SELECT 1 FROM users WHERE name LIKE 'Placeholder5'",
        ).fetchone()
        assert row is not None, "Verify new user created successfully"
        conn.close()

def test_login_logout(client, init_db):
    with client:
        login_placeholder(client)
        exit = client.get(url_for("auth.logout"), follow_redirects=True)
        assert check_redirect(exit, url_for("main.home")), "Successful logout and redirect"
        response_blocked = client.get(url_for("auth.profile"))
        assert response_blocked.status_code != 200, "Login required restriction works"
        
        failed_login = client.post(url_for("auth.login"), data={
            "email": "blah@blah",
            "password": "PL",
        }, follow_redirects=True)
        assert check_redirect(failed_login, url_for("auth.login")), "Failed login (wrong password) and redirect"

        failed_login = client.post(url_for("auth.login"), data={
            "password": "Placeholder",
        }, follow_redirects=True)
        assert check_redirect(failed_login, url_for("auth.login")), "Failed login (no email) and redirect"
        
        login = client.post(url_for("auth.login"), data={
            "email": "blah@blah",
            "password": "Placeholder",
        }, follow_redirects=True)
        assert check_redirect(login, url_for("main.home")), "Successful login and redirect"

        profile_access = client.get(url_for("auth.profile"))
        assert profile_access.status_code == 200, "User profile accessible after login"
        assert "user_id" in session, "User session successfully created"

def test_profile(client, init_db):
    with client:
        login_placeholder(client)
        to_profile = client.get(url_for("auth.profile"))
        assert to_profile.status_code == 200
        
        update_courses = client.post(url_for("auth.profile"), data={
            "course_ids": ["2"],
        }, follow_redirects=True)
        assert check_redirect(update_courses, url_for("auth.profile")), "Successful course list update and redirect"
        
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

        conn.commit()
        conn.close()
        
    
def test_group_create(client, init_db):
    with client:
        init = client.get("/")
        creation_reject = client.post(url_for("groups.create_study_group"), data={
            "title": "LePlaceholder",
            "max_members": 8,
            "selected_course_ids": "",
        }, follow_redirects=True)
        assert check_redirect(creation_reject, url_for("auth.login")), "Accessing group creation without login"
        
        login_placeholder(client)
        create_group = client.post(url_for("groups.create_study_group"), data={
            "title": "LePlaceholder",
            "max_members": 8,
            "selected_course_ids": "",
        }, follow_redirects=True)
        assert check_redirect(create_group, url_for("main.home")), "Successful group creation and redirect"
        
        conn = get_db()
        row = conn.execute(
            "SELECT 1 FROM study_groups WHERE title LIKE 'LePlaceholder' AND member_count == 1 AND max_members == 8",
        ).fetchone()
        assert row is not None, "Verifying new group is in database with correct attributes"

        conn.commit()
        conn.close()

def test_join_leave_group(client, init_db):
    with client:
        login_placeholder(client)
        create_group = client.post(url_for("groups.create_study_group"), data={
            "title": "LePlaceholder2",
            "max_members": 8,
            "selected_course_ids": "",
        })
        exit = client.get(url_for("auth.logout"))
        temp_user = client.post(url_for("auth.signup"), data={
            "name": "Placeholder6",
            "email": "6newplaceholder@placeholder",
            "password": "Placeholder",
        })

        conn = get_db()
        row = conn.execute(
            "SELECT * FROM study_groups WHERE title LIKE 'LePlaceholder2'",
        ).fetchone()
        entry = client.post(url_for("groups.join_group", group_id=row["id"]), follow_redirects=True)
        assert check_redirect(entry, url_for("groups.group_detail", group_id=row["id"])), "Successful group joining"

        exit = client.post(url_for("groups.leave_group", group_id=row["id"]), follow_redirects=True)
        assert check_redirect(exit, url_for("groups.browse_groups")), "Successful group leaving"

        conn.commit()
        conn.close()

def test_edit_group(client, init_db):
    with client:
        login_placeholder(client)
        create_group = client.post(url_for("groups.create_study_group"), data={
            "title": "LePlaceholder2",
            "max_members": 8,
            "selected_course_ids": "",
        })
        conn = get_db()
        row = conn.execute(
            "SELECT * FROM study_groups WHERE title LIKE 'LePlaceholder2'",
        ).fetchone()
        editing = client.post(url_for("groups.edit_group", group_id=row["id"]), data={
            "title": "LePlaceholder3",
            "description": "Suddenly, one day",
            "location": "Powell",
            "max_members": 2,
        })

        row = conn.execute(
            "SELECT 1 FROM study_groups WHERE title LIKE 'LePlaceholder3' AND max_members == 2 AND description LIKE 'Suddenly, one day' AND location LIKE 'Powell'",
        ).fetchone()
        assert row is not None, "Verifying edited group is in database with correct attributes"

        conn.commit()
        conn.close()


def login_placeholder(client):
    client.get("/")
    client.post(url_for("auth.signup"), data={
        "name": "blah",
        "email": "blah@blah",
        "password": "Placeholder",
    })

def check_redirect(response, intended_redirect):
    return len(response.history) == 1 and response.request.path == intended_redirect

if __name__ == "__main__":
    pytest.main([__file__, "-v"])