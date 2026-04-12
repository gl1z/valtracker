from flask import Flask, jsonify
from config import config_map
from app.extensions import db, jwt

def create_app(config_name="default"):
    app = Flask(__name__)
    app.config.from_object(config_map[config_name])

    db.init_app(app)
    jwt.init_app(app)

    @app.route("/health")
    def health():
        return jsonify({"status": "ok", "app": "valtracker"})

    return app
