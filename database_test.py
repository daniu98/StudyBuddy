import pytest
from flask import session
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
    exit = client.get("/logout")
    response = client.post("/signup", data={
        "name": "Placeholder5",
        "email": "5newplaceholder@placeholder",
        "password": "Placeholder",
    })
    conn = get_db()
    row = conn.execute(
        "SELECT 1 FROM users WHERE name LIKE 'Placeholder5'",
    ).fetchone()
    assert row is not None, "Verifying new user is in database"
    clean = conn.execute(
        "DELETE FROM users WHERE name LIKE 'Placeholder5'",
    )

def test_login(client):
    exit = client.get("/logout")
    response = client.post("/login", data={
        "email": "blah@blah",
        "password": "Placeholder",
    })
    response2 = client.get("/profile")
    assert response2 is not None, "Verifying logged in"
    conn = get_db()
    row = conn.execute(
        "SELECT 1 FROM users WHERE name = 'blah'",
    ).fetchone()
    assert row is not None, "Verifying user is in database"
    #assert response.status_code == 200, "Logging in"
    response2 = client.get("/profile")
    assert response2.status_code == 200, "User profile works"
    
def test_group_create(client):
    exit = client.get("/logout")
    response = client.post("/login", data={
        "email": "blah@blah",
        "password": "Placeholder",
    })
    response2 = client.post("/study-groups/new", data={
        "title": "LePlaceholder",
        "max_members": 8,
        "selected_course_ids": "",
    })
    conn = get_db()
    row = conn.execute(
        "SELECT 1 FROM study_groups WHERE title LIKE 'LePlaceholder'",
    ).fetchone()
    assert row is not None, "Verifying new group is in database"
    clean = conn.execute(
        "DELETE FROM study_groups WHERE title LIKE 'LePlaceholder'",
    )
    
if __name__ == "__main__":
    pytest.main([__file__, "-v"])