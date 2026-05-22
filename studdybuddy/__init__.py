from pathlib import Path

from flask import Flask

from .auth import bp as auth_bp
from .db import current_user
from .groups import bp as groups_bp
from .main import bp as main_bp


def create_app():
    project_root = Path(__file__).resolve().parent.parent
    app = Flask(
        __name__,
        template_folder=str(project_root / "templates"),
        static_folder=str(project_root / "static"),
    )
    app.config["SECRET_KEY"] = "dev-secret-key-change-this"

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(groups_bp)

    @app.context_processor
    def inject_user():
        return {"current_user": current_user()}

    return app
