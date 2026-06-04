def create(conn, name, email, password_hash):
    cursor = conn.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        (name, email, password_hash),
    )
    return cursor.lastrowid


def find_by_email(conn, email):
    return conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()


def find_by_id(conn, user_id):
    return conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()


def update_password_hash(conn, user_id, password_hash):
    conn.execute(
        "UPDATE users SET password_hash = ? WHERE id = ?",
        (password_hash, user_id),
    )


def replace_user_courses(conn, user_id, course_ids):
    conn.execute("DELETE FROM user_courses WHERE user_id = ?", (user_id,))
    for course_id in course_ids:
        conn.execute(
            "INSERT INTO user_courses (user_id, course_id) VALUES (?, ?)",
            (user_id, course_id),
        )


def selected_course_ids(conn, user_id):
    rows = conn.execute(
        "SELECT course_id FROM user_courses WHERE user_id = ?",
        (user_id,),
    ).fetchall()
    return {row["course_id"] for row in rows}
