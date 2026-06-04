def find_user_review(conn, group_id, user_id):
    return conn.execute(
        """
        SELECT id FROM group_reviews
        WHERE group_id = ? AND user_id = ?
        """,
        (group_id, user_id),
    ).fetchone()


def update(conn, group_id, user_id, rating, body):
    conn.execute(
        """
        UPDATE group_reviews
        SET rating = ?, body = ?, updated_at = CURRENT_TIMESTAMP
        WHERE group_id = ? AND user_id = ?
        """,
        (rating, body, group_id, user_id),
    )


def insert(conn, group_id, user_id, rating, body):
    conn.execute(
        """
        INSERT INTO group_reviews (group_id, user_id, rating, body)
        VALUES (?, ?, ?, ?)
        """,
        (group_id, user_id, rating, body),
    )


def list_for_group(conn, group_id):
    return conn.execute(
        """
        SELECT r.rating, r.body, r.created_at, r.updated_at, u.name AS author_name
        FROM group_reviews r
        JOIN users u ON u.id = r.user_id
        WHERE r.group_id = ?
        ORDER BY r.created_at DESC
        """,
        (group_id,),
    ).fetchall()


def summary_for_group(conn, group_id):
    return conn.execute(
        """
        SELECT ROUND(AVG(rating), 1) AS avg_rating, COUNT(*) AS review_count
        FROM group_reviews
        WHERE group_id = ?
        """,
        (group_id,),
    ).fetchone()


def user_review_body(conn, group_id, user_id):
    return conn.execute(
        """
        SELECT rating, body
        FROM group_reviews
        WHERE group_id = ? AND user_id = ?
        """,
        (group_id, user_id),
    ).fetchone()
