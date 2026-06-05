import sqlite3
from pathlib import Path

import migrate_db

LEGACY_SCHEMA = """
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL
);
CREATE TABLE courses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL
);
CREATE TABLE study_groups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    max_members INTEGER NOT NULL,
    admin_id INTEGER NOT NULL
);
CREATE TABLE group_members (
    group_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    role TEXT DEFAULT 'member',
    PRIMARY KEY (group_id, user_id)
);
"""


def _create_legacy_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.executescript(LEGACY_SCHEMA)
    conn.execute(
        "INSERT INTO users (name, email, password_hash) VALUES ('A', 'a@test', 'h')"
    )
    conn.execute(
        "INSERT INTO users (name, email, password_hash) VALUES ('B', 'b@test', 'h')"
    )
    conn.execute(
        "INSERT INTO study_groups (title, max_members, admin_id) VALUES ('G', 5, 1)"
    )
    conn.execute(
        "INSERT INTO group_members (group_id, user_id, role) VALUES (1, 1, 'admin')"
    )
    conn.execute("INSERT INTO group_members (group_id, user_id) VALUES (1, 2)")
    conn.commit()
    conn.close()


def test_legacy_database_migration(tmp_path, monkeypatch):
    db_path = tmp_path / "legacy.db"
    _create_legacy_db(db_path)
    monkeypatch.setattr(migrate_db, "DATABASE", str(db_path))

    migrate_db.main()
    migrate_db.main()

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        cols = migrate_db.column_names(conn, "study_groups")
        assert "member_count" in cols
        assert "invite_code" in cols
        assert conn.execute(
            "SELECT member_count FROM study_groups WHERE id = 1"
        ).fetchone()["member_count"] == 2

        assert conn.execute("SELECT COUNT(*) FROM courses").fetchone()[0] == len(
            migrate_db.COURSE_SEED
        )
        assert conn.execute(
            "SELECT 1 FROM sqlite_master WHERE name = 'group_reviews'"
        ).fetchone() is not None
    finally:
        conn.close()
