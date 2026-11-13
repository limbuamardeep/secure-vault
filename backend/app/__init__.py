from config import Config
from flask import Flask, jsonify

from .extensions import db, migrate
from .routes.auth import bp as auth_bp


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)
    migrate.init_app(app, db)
    app.register_blueprint(auth_bp)
    from . import models

    @app.get("/")
    def health():
        return jsonify({"status": "ok"})

    return app
