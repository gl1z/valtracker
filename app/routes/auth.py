from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from app.models import User
from flask import Blueprint, request, jsonify, current_app
from app.extensions import db, limiter

bp = Blueprint("auth", __name__, url_prefix="/auth")

@bp.route("/register", methods=["POST"])
@limiter.limit(lambda: current_app.config["AUTH_REGISTER_RATE_LIMIT"])
def register():
    data = request.get_json()
    if not data or not data.get("username") or not data.get("email") or not data.get("password"):
        return jsonify({"error": "username, email and password are required"}), 400

    if User.query.filter_by(username=data["username"]).first():
        return jsonify({"error": "username already taken"}), 409

    if User.query.filter_by(email=data["email"]).first():
        return jsonify({"error": "email already registered"}), 409

    user = User(username=data["username"], email=data["email"])
    user.set_password(data["password"])
    db.session.add(user)
    db.session.commit()

    return jsonify({"message": "registered", "user": user.to_dict()}), 201

@bp.route("/login", methods=["POST"])
@limiter.limit(lambda: current_app.config["AUTH_LOGIN_RATE_LIMIT"])
def login():
    data = request.get_json()
    if not data or not data.get("username") or not data.get("password"):
        return jsonify({"error": "username and password are required"}), 400

    user = User.query.filter_by(username=data["username"]).first()
    if not user or not user.check_password(data["password"]):
        return jsonify({"error": "invalid credentials"}), 401

    token = create_access_token(identity=str(user.id))
    return jsonify({"access_token": token}), 200

# useful for checking if a token is still valid
@bp.route("/me", methods=["GET"])
@jwt_required()
def me():
    user_id = get_jwt_identity()
    user = User.query.get(int(user_id))
    if not user:
        return jsonify({"error": "user not found"}), 404
    return jsonify(user.to_dict()), 200