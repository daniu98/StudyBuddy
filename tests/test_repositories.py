import sqlite3
from pathlib import Path

import pytest

from studybuddy.db import user_is_group_member
from studybuddy.repositories import reviews as reviews_repo
from studybuddy.repositories import study_groups as groups_repo
from studybuddy.repositories import users as users_repo

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "schema.sql"


@pytest.fixture()
def conn():
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    connection.commit()
    yield connection
    connection.close()


def test_repository_layer_groups_and_reviews(conn):
    admin_id = users_repo.create(conn, "Admin", "admin@repo", "hash")
    member_id = users_repo.create(conn, "Member", "member@repo", "hash")
    conn.commit()

    group_id = groups_repo.create(
        conn,
        title="Repo Group",
        description=None,
        max_members=4,
        meeting_time=None,
        location=None,
        study_style=None,
        admin_id=admin_id,
        invite_code="code-1",
    )
    groups_repo.add_admin_member(conn, group_id, admin_id)
    groups_repo.add_member(conn, group_id, member_id)
    groups_repo.refresh_member_count(conn, group_id)
    conn.commit()

    assert groups_repo.search(conn, q="Repo")[0]["title"] == "Repo Group"
    assert user_is_group_member(conn, group_id, member_id)
    assert groups_repo.member_count(conn, group_id) == 2

    reviews_repo.insert(conn, group_id, member_id, 4, "Good")
    conn.commit()
    summary = reviews_repo.summary_for_group(conn, group_id)
    assert summary["avg_rating"] == 4.0
    assert summary["review_count"] == 1
