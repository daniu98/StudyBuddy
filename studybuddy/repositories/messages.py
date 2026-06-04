def insert(conn, group_id, user_id, body):
    conn.execute(
        "INSERT INTO messages (group_id, user_id, body) VALUES (?, ?, ?)",
        (group_id, user_id, body),
    )


def list_for_group(conn, group_id):
    return conn.execute(
        """
        SELECT m.body, m.created_at, u.name AS author_name
        FROM messages m
        JOIN users u ON m.user_id = u.id
        WHERE m.group_id = ?
        ORDER BY m.created_at DESC
        """,
        (group_id,),
    ).fetchall()


def count_last_7_days_for_user(conn, user_id):
    row = conn.execute(
        """
        SELECT COUNT(*) AS messages_last_7_days
        FROM messages m
        JOIN group_members gm ON gm.group_id = m.group_id
        WHERE gm.user_id = ?
          AND gm.user_id = m.user_id
          AND datetime(m.created_at) >= datetime('now', '-7 days')
        """,
        (user_id,),
    ).fetchone()
    return row["messages_last_7_days"]


def top_group_last_7_days(conn, user_id):
    return conn.execute(
        """
        SELECT sg.title, COUNT(*) AS message_count
        FROM messages m
        JOIN study_groups sg ON sg.id = m.group_id
        JOIN group_members gm ON gm.group_id = m.group_id
        WHERE gm.user_id = ?
          AND m.user_id = ?
          AND datetime(m.created_at) >= datetime('now', '-7 days')
        GROUP BY sg.id, sg.title
        ORDER BY message_count DESC, sg.title COLLATE NOCASE
        LIMIT 1
        """,
        (user_id, user_id),
    ).fetchone()


def best_day_last_7_days(conn, user_id):
    return conn.execute(
        """
        SELECT strftime('%w', m.created_at) AS weekday_number, COUNT(*) AS message_count
        FROM messages m
        JOIN group_members gm ON gm.group_id = m.group_id
        WHERE gm.user_id = ?
          AND m.user_id = ?
          AND datetime(m.created_at) >= datetime('now', '-7 days')
        GROUP BY weekday_number
        ORDER BY message_count DESC, weekday_number ASC
        LIMIT 1
        """,
        (user_id, user_id),
    ).fetchone()
