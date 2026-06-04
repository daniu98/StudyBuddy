import os
import shutil

import pytest
from studybuddy import create_app


@pytest.fixture(scope="session", autouse=True)
def cache_db():
    """Preserve the developer database while the test suite runs."""
    if os.path.exists("studybuddy.db"):
        shutil.move("studybuddy.db", "tempdb.db")
    yield
    if os.path.exists("tempdb.db"):
        if os.path.exists("studybuddy.db"):
            os.remove("studybuddy.db")
        shutil.move("tempdb.db", "studybuddy.db")


@pytest.fixture()
def init_db():
    with open("init_db.py", encoding="utf-8") as file:
        exec(file.read())  # noqa: S102


@pytest.fixture()
def app(init_db):
    app = create_app()
    app.config.update({"TESTING": True})
    yield app


@pytest.fixture()
def client(app):
    return app.test_client()
