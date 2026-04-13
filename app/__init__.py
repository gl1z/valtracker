from flask import Flask, jsonify
from config import config_map
from app.extensions import db, jwt

def create_app(config_name="default"):
    app = Flask(__name__)
    app.config.from_object(config_map[config_name])

    db.init_app(app)
    jwt.init_app(app)

    from app.routes.auth import bp as auth_bp
    app.register_blueprint(auth_bp)

    from app.routes.players import players_bp
    app.register_blueprint(players_bp)

    from app.routes.matches import matches_bp, agents_bp
    app.register_blueprint(matches_bp)
    app.register_blueprint(agents_bp)

    from app.routes.tournaments import tournaments_bp
    app.register_blueprint(tournaments_bp)

    from app.routes.leaderboard import leaderboard_bp
    app.register_blueprint(leaderboard_bp)

    with app.app_context():
        db.create_all()

    @app.route("/health")
    def health():
        return jsonify({"status": "ok", "app": "valtracker"})

    return app