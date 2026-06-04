def search(conn, q=None, course_id=None):
    conditions = []
    params = []

    if q:
        pattern = f"%{q}%"
        conditions.append(
            """
            (
                sg.title LIKE ? COLLATE NOCASE
                OR sg.description LIKE ? COLLATE NOCASE
                OR sg.location LIKE ? COLLATE NOCASE
                OR sg.study_style LIKE ? COLLATE NOCASE
                OR EXISTS (
                    SELECT 1
                    FROM group_courses gc
                    JOIN courses c ON c.id = gc.course_id
                    WHERE gc.group_id = sg.id
                      AND (
                          c.code LIKE ? COLLATE NOCASE
                          OR c.name LIKE ? COLLATE NOCASE
                      )
                )
            )
            """
        )
        params.extend([pattern, pattern, pattern, pattern, pattern, pattern])

    if course_id is not None:
        conditions.append(
            """
            EXISTS (
                SELECT 1 FROM group_courses gc
                WHERE gc.group_id = sg.id AND gc.course_id = ?
            )
            """
        )
        params.append(course_id)

    where_clause = ""
    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)

    return conn.execute(
        f"""
        SELECT sg.id, sg.title, sg.description, sg.meeting_time, sg.location,
               sg.study_style, sg.max_members,
               (SELECT COUNT(*) FROM group_members gm WHERE gm.group_id = sg.id) AS member_count,
               (
                   SELECT GROUP_CONCAT(c.code, ', ')
                   FROM group_courses gc
                   JOIN courses c ON c.id = gc.course_id
                   WHERE gc.group_id = sg.id
               ) AS course_codes,
               (
                   SELECT ROUND(AVG(r.rating), 1)
                   FROM group_reviews r
                   WHERE r.group_id = sg.id
               ) AS avg_rating,
               (
                   SELECT COUNT(*)
                   FROM group_reviews r
                   WHERE r.group_id = sg.id
               ) AS review_count
        FROM study_groups sg
        {where_clause}
        ORDER BY sg.title COLLATE NOCASE
        """,
        params,
    ).fetchall()


def member_group_ids(conn, user_id):
    rows = conn.execute(
        "SELECT group_id FROM group_members WHERE user_id = ?",
        (user_id,),
    ).fetchall()
    return {row["group_id"] for row in rows}


def list_for_user_dashboard(conn, user_id):
    return conn.execute(
        """
        SELECT sg.id, sg.title, sg.description, sg.meeting_time, sg.location,
               gm.role, gm.joined_at
        FROM study_groups sg
        INNER JOIN group_members gm ON sg.id = gm.group_id
        WHERE gm.user_id = ?
        ORDER BY sg.title COLLATE NOCASE
        """,
        (user_id,),
    ).fetchall()


def calendar_meetings(conn, user_id):
    return conn.execute(
        """
        SELECT sg.id, sg.title, sg.meeting_time, sg.location, sg.study_style,
               (
                   SELECT GROUP_CONCAT(c.code, ', ')
                   FROM group_courses gc
                   JOIN courses c ON c.id = gc.course_id
                   WHERE gc.group_id = sg.id
               ) AS course_codes
        FROM study_groups sg
        JOIN group_members gm ON gm.group_id = sg.id
        WHERE gm.user_id = ?
          AND sg.meeting_time IS NOT NULL
        ORDER BY sg.title COLLATE NOCASE
        """,
        (user_id,),
    ).fetchall()


def exists(conn, group_id):
    return find_id(conn, group_id) is not None


def find_id(conn, group_id):
    return conn.execute(
        "SELECT id FROM study_groups WHERE id = ?",
        (group_id,),
    ).fetchone()


def find_for_reviews_page(conn, group_id):
    return conn.execute(
        """
        SELECT sg.id, sg.title
        FROM study_groups sg
        WHERE sg.id = ?
        """,
        (group_id,),
    ).fetchone()


def find_with_admin(conn, group_id):
    return conn.execute(
        """
        SELECT sg.*, u.name AS admin_name
        FROM study_groups sg
        JOIN users u ON sg.admin_id = u.id
        WHERE sg.id = ?
        """,
        (group_id,),
    ).fetchone()


def find_max_members(conn, group_id):
    return conn.execute(
        "SELECT max_members FROM study_groups WHERE id = ?",
        (group_id,),
    ).fetchone()


def find_by_invite_code(conn, code):
    return conn.execute(
        """
        SELECT id, max_members,
               (SELECT COUNT(*) FROM group_members gm WHERE gm.group_id = study_groups.id) AS member_count
        FROM study_groups
        WHERE invite_code = ?
        """,
        (code,),
    ).fetchone()


def admin_and_invite(conn, group_id):
    return conn.execute(
        "SELECT admin_id, invite_code FROM study_groups WHERE id = ?",
        (group_id,),
    ).fetchone()


def set_invite_code(conn, group_id, invite_code):
    conn.execute(
        "UPDATE study_groups SET invite_code = ? WHERE id = ?",
        (invite_code, group_id),
    )


def membership(conn, group_id, user_id):
    return conn.execute(
        "SELECT role, joined_at FROM group_members WHERE group_id = ? AND user_id = ?",
        (group_id, user_id),
    ).fetchone()


def membership_role(conn, group_id, user_id):
    return conn.execute(
        """
        SELECT role
        FROM group_members
        WHERE group_id = ? AND user_id = ?
        """,
        (group_id, user_id),
    ).fetchone()


def is_member(conn, group_id, user_id):
    row = conn.execute(
        "SELECT 1 FROM group_members WHERE group_id = ? AND user_id = ?",
        (group_id, user_id),
    ).fetchone()
    return row is not None


def list_courses(conn, group_id):
    return conn.execute(
        """
        SELECT c.code, c.name
        FROM courses c
        JOIN group_courses gc ON c.id = gc.course_id
        WHERE gc.group_id = ?
        ORDER BY c.code
        """,
        (group_id,),
    ).fetchall()


def list_members(conn, group_id):
    return conn.execute(
        """
        SELECT u.name, gm.role, gm.joined_at
        FROM group_members gm
        JOIN users u ON gm.user_id = u.id
        WHERE gm.group_id = ?
        ORDER BY gm.role DESC, u.name COLLATE NOCASE
        """,
        (group_id,),
    ).fetchall()


def member_count(conn, group_id):
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM group_members WHERE group_id = ?",
        (group_id,),
    ).fetchone()
    return row["n"]


def update(conn, group_id, title, description, location, max_members, meeting_time, study_style):
    conn.execute(
        """
        UPDATE study_groups
        SET title = ?, description = ?, location = ?, max_members = ?,
            meeting_time = ?, study_style = ?
        WHERE id = ?
        """,
        (
            title,
            description,
            location,
            max_members,
            meeting_time,
            study_style,
            group_id,
        ),
    )


def create(
    conn,
    title,
    description,
    max_members,
    meeting_time,
    location,
    study_style,
    admin_id,
    invite_code,
):
    cursor = conn.execute(
        """
        INSERT INTO study_groups (
            title, description, max_members, member_count, meeting_time,
            location, study_style, admin_id, invite_code
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            title,
            description,
            max_members,
            1,
            meeting_time,
            location,
            study_style,
            admin_id,
            invite_code,
        ),
    )
    return cursor.lastrowid


def add_admin_member(conn, group_id, user_id):
    conn.execute(
        """
        INSERT INTO group_members (group_id, user_id, role)
        VALUES (?, ?, 'admin')
        """,
        (group_id, user_id),
    )


def link_course(conn, group_id, course_id):
    conn.execute(
        """
        INSERT INTO group_courses (group_id, course_id)
        VALUES (?, ?)
        """,
        (group_id, course_id),
    )


def add_member(conn, group_id, user_id, role=None):
    if role:
        conn.execute(
            "INSERT INTO group_members (group_id, user_id, role) VALUES (?, ?, ?)",
            (group_id, user_id, role),
        )
    else:
        conn.execute(
            "INSERT INTO group_members (group_id, user_id) VALUES (?, ?)",
            (group_id, user_id),
        )


def remove_member(conn, group_id, user_id):
    conn.execute(
        "DELETE FROM group_members WHERE group_id = ? AND user_id = ?",
        (group_id, user_id),
    )


def refresh_member_count(conn, group_id):
    conn.execute(
        """
        UPDATE study_groups
        SET member_count = (
            SELECT COUNT(*) FROM group_members WHERE group_id = ?
        )
        WHERE id = ?
        """,
        (group_id, group_id),
    )
