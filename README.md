# StudyBuddy

StudyBuddy is a Flask web app for finding study groups, joining them, messaging members, leaving reviews, and tracking personal study activity on a dashboard.

## Requirements

- Python 3.9 or newer
- `pip`
- A terminal

## Project structure

```text
StuddyBuddy/
├── app.py                 # Local entry point (starts the dev server)
├── init_db.py             # Creates a fresh SQLite database from schema.sql
├── migrate_db.py          # Applies schema updates to an existing database
├── schema.sql             # Database schema and seed course data
├── requirements.txt       # Python dependencies
├── studybuddy/            # Application package (routes, auth, groups, DB helpers)
├── templates/             # HTML templates
├── static/                # CSS and static assets
└── tests/                 # Automated tests
    ├── conftest.py        # Shared pytest fixtures
    ├── helpers.py         # Shared test helper functions
    ├── database_test.py   # Unit/integration tests for core features
    └── end_to_end_tests.py # Multi-step user flow tests
```

## 1. Clone and open the project

```bash
git clone https://github.com/daniu98/StudyBuddy.git
cd StudyBuddy
```

If you already have the repo locally, make sure you are in the project root (the folder that contains `app.py`).

## 2. Create and activate a virtual environment

### macOS / Linux

```bash
python3 -m venv venv
source venv/bin/activate
```

### Windows (Command Prompt)

```bat
python -m venv venv
venv\Scripts\activate
```

### Windows (PowerShell)

```powershell
python -m venv venv
venv\Scripts\Activate.ps1
```

When the environment is active, your shell prompt usually shows `(venv)`.

## 3. Install dependencies

```bash
pip install -r requirements.txt
```

This installs Flask and pytest.

## 4. Set up the database

Run **one** of the following from the project root.

### Fresh setup (recommended for first run)

Creates `studybuddy.db` from `schema.sql` and seeds default courses:

```bash
python init_db.py
```

Expected output:

```text
Database initialized: studybuddy.db
```

### Existing database (upgrade without wiping data)

If you already have an older `studybuddy.db`, run:

```bash
python migrate_db.py
```

This adds missing tables/columns (for example `group_reviews`, `member_count`, and `invite_code`) without deleting existing users or groups.

Notes:

- The app also runs `migrate_db.py` automatically on startup.
- `studybuddy.db` is local-only and is ignored by git.

## 5. Run the app locally

From the project root:

```bash
python app.py
```

You should see Flask start in debug mode on port **5001**.

Open the app in your browser:

```text
http://127.0.0.1:5001
```

### Stop the server

Press `Ctrl+C` in the terminal where the app is running.

## 6. Basic local workflow

1. Open `http://127.0.0.1:5001`
2. Click **Sign Up** and create an account
3. Save courses on your **Profile**
4. Use **Create Group** to make a study group
5. Use **Find Groups** to browse/search/join groups
6. Open **Dashboard** to see joined groups and activity snapshot

## 7. Run tests

Run all tests from the project root:

```bash
pytest tests/ -v
```

Run only database/unit tests:

```bash
pytest tests/database_test.py -v
```

Run only end-to-end flow tests:

```bash
pytest tests/end_to_end_tests.py -v
```

### What the test suites cover

- `tests/database_test.py`
  - Signup validation and account creation
  - Login/logout and protected routes
  - Profile course updates
  - Group create/join/leave/edit behavior

- `tests/end_to_end_tests.py`
  - Create group + find by course filter
  - Join group + search membership state + post message + dashboard activity
  - Submit group review and verify browse page review display

### Test database behavior

The test suite temporarily moves your local `studybuddy.db` to `tempdb.db` while tests run, then restores it when tests finish. Each test uses a fresh database created by `init_db.py`.

## Troubleshooting

### `ModuleNotFoundError: No module named 'flask'`

Your virtual environment is not active or dependencies are not installed.

```bash
source venv/bin/activate   # macOS/Linux
pip install -r requirements.txt
```

### `Address already in use` on port 5001

Another process is already using port 5001. Stop that process, or change the port in `app.py`.

### Browse page errors after pulling new code

Run migrations:

```bash
python migrate_db.py
```

If your local database is corrupted/outdated and you do not need existing data:

```bash
rm studybuddy.db
python init_db.py
```

### Tests fail immediately with database errors

Make sure you are running pytest from the project root (where `init_db.py` and `schema.sql` live):

```bash
cd /path/to/StudyBuddy
pytest tests/ -v
```

## Development notes

- Default dev secret key is set in `studybuddy/__init__.py` (`dev-secret-key-change-this`).
- Debug mode is enabled in `app.py` for local development only.
- Production deployment should use a production WSGI server and a secure secret key.
