def list_all(conn):
    return conn.execute("SELECT * FROM courses ORDER BY code").fetchall()


def exists(conn, course_id):
    row = conn.execute("SELECT 1 FROM courses WHERE id = ?", (course_id,)).fetchone()
    return row is not None
