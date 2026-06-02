"""Apply schema updates to an existing studybuddy.db without wiping data."""

import sqlite3

DATABASE = "studybuddy.db"

COURSE_SEED = [
    ("CS31", "Introduction to Computer Science"),
    ("MATH31a", "Math 1"),
    ("MATH32a", "Math 3"),
    ("MATH33a", "Math 5"),
    ("MATH31b", "Math 2"),
    ("MATH32b", "Math 4"),
    ("MATH33b", "Math 6"),
]


def column_names(conn, table):
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {row[1] for row in rows}


def main():
    conn = sqlite3.connect(DATABASE)

    cols = column_names(conn, "study_groups")
    if "member_count" not in cols:
        conn.execute(
            "ALTER TABLE study_groups ADD COLUMN member_count INTEGER NOT NULL DEFAULT 1"
        )
        conn.execute(
            """
            UPDATE study_groups
            SET member_count = (
                SELECT COUNT(*) FROM group_members
                WHERE group_members.group_id = study_groups.id
            )
            """
        )
        conn.execute(
            "UPDATE study_groups SET member_count = 1 WHERE member_count = 0"
        )
        print("Added study_groups.member_count and backfilled counts.")

    cols = column_names(conn, "study_groups")
    if "invite_code" not in cols:
        conn.execute("ALTER TABLE study_groups ADD COLUMN invite_code TEXT")
        print("Added study_groups.invite_code.")

    count = conn.execute("SELECT COUNT(*) FROM courses").fetchone()[0]
    if count == 0:
        conn.executemany(
            "INSERT INTO courses (code, name) VALUES (?, ?)",
            COURSE_SEED,
        )
        print(f"Seeded {len(COURSE_SEED)} courses.")

<<<<<<< HEAD
=======
    reviews_table = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='group_reviews'"
    ).fetchone()
    if reviews_table is None:
        conn.execute(
            """
            CREATE TABLE group_reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                rating INTEGER NOT NULL CHECK (rating >= 1 AND rating <= 5),
                body TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (group_id, user_id),
                FOREIGN KEY (group_id) REFERENCES study_groups(id),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
            """
        )
        print("Created group_reviews table.")

>>>>>>> origin
    conn.commit()
    conn.close()
    print("Migration complete.")


if __name__ == "__main__":
    main()
