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
        _seed_agents()

    @app.route("/health")
    def health():
        return jsonify({"status": "ok", "app": "valtracker"})

    return app

_AGENTS = [
    ("Jett", "duelist"), ("Reyna", "duelist"), ("Raze", "duelist"),
    ("Phoenix", "duelist"), ("Neon", "duelist"), ("Iso", "duelist"),
    ("Waylay", "duelist"), ("Yoru", "duelist"),
    ("Brimstone", "controller"), ("Viper", "controller"), ("Omen", "controller"),
    ("Astra", "controller"), ("Harbor", "controller"), ("Clove", "controller"),
    ("Miks", "controller"),
    ("Sage", "sentinel"), ("Cypher", "sentinel"), ("Killjoy", "sentinel"),
    ("Chamber", "sentinel"), ("Deadlock", "sentinel"), ("Vyse", "sentinel"),
    ("Veto", "sentinel"),
    ("Sova", "initiator"), ("Breach", "initiator"), ("Skye", "initiator"),
    ("KAY/O", "initiator"), ("Fade", "initiator"), ("Gekko", "initiator"),
    ("Tejo", "initiator"),
]

def _seed_agents():
    from app.models import Agent
    for name, role in _AGENTS:
        if not Agent.query.filter_by(name=name).first():
            db.session.add(Agent(name=name, role=role))
    db.session.commit()
