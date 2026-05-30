DROP TABLE IF EXISTS messages;
DROP TABLE IF EXISTS group_reviews;
DROP TABLE IF EXISTS group_members;
DROP TABLE IF EXISTS group_courses;
DROP TABLE IF EXISTS study_groups;
DROP TABLE IF EXISTS user_courses;
DROP TABLE IF EXISTS courses;
DROP TABLE IF EXISTS users;

CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE courses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL
);

CREATE TABLE user_courses (
    user_id INTEGER NOT NULL,
    course_id INTEGER NOT NULL,
    PRIMARY KEY (user_id, course_id),
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (course_id) REFERENCES courses(id)
);

CREATE TABLE study_groups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT,
    max_members INTEGER NOT NULL,
    member_count INTEGER NOT NULL,
    meeting_time TEXT,
    location TEXT,
    study_style TEXT,
    admin_id INTEGER NOT NULL,
    invite_code TEXT UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (admin_id) REFERENCES users(id)
);

CREATE TABLE group_courses (
    group_id INTEGER NOT NULL,
    course_id INTEGER NOT NULL,
    PRIMARY KEY (group_id, course_id),
    FOREIGN KEY (group_id) REFERENCES study_groups(id),
    FOREIGN KEY (course_id) REFERENCES courses(id)
);

CREATE TABLE group_members (
    group_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    role TEXT DEFAULT 'member',
    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (group_id, user_id),
    FOREIGN KEY (group_id) REFERENCES study_groups(id),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    group_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    body TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (group_id) REFERENCES study_groups(id),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

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
);

INSERT INTO courses (code, name) VALUES
('CS31', 'Introduction to Computer Science'),
('MATH31a', 'Math 1'),
('MATH32a', 'Math 3'),
('MATH33a', 'Math 5'),
('MATH31b', 'Math 2'),
('MATH32b', 'Math 4'),
('MATH33b', 'Math 6');
