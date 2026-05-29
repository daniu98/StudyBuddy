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

    

    count = conn.execute("SELECT COUNT(*) FROM courses").fetchone()[0]
    if count == 0:
        conn.executemany(
            "INSERT INTO courses (code, name) VALUES (?, ?)",
            COURSE_SEED,
        )
        print(f"Seeded {len(COURSE_SEED)} courses.")

    conn.commit()
    conn.close()
    print("Migration complete.")


if __name__ == "__main__":
    main()
