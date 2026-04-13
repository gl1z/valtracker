from flask import Blueprint, request
from flask_jwt_extended import jwt_required
from app.extensions import db
from app.models import Player, Match, MatchParticipant
from app.validators import (
    error_response, success_response, require_fields,
    validate_username, validate_email_address, validate_region,
    validate_positive_int
)

players_bp = Blueprint("players", __name__, url_prefix="/players")

@players_bp.route("", methods=["GET"])
def list_players():
    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", 20, type=int), 100)
    region = request.args.get("region")
    search = request.args.get("search")

    query = Player.query.order_by(Player.created_at.desc())

    if region:
        query = query.filter(Player.region == region.upper())
    if search:
        query = query.filter(Player.username.ilike(f"%{search}%"))

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return success_response({
        "players": [p.to_dict() for p in pagination.items],
        "total": pagination.total,
        "page": pagination.page,
        "pages": pagination.pages,
    })

@players_bp.route("", methods=["POST"])
@jwt_required()
def create_player():
    data = request.get_json(silent=True)
    if not data:
        return error_response("request body must be JSON")
    try:
        require_fields(data, "username", "email")
        username = validate_username(data["username"])
        email = validate_email_address(data["email"])
        region = validate_region(data.get("region", "NA"))
    except ValueError as e:
        return error_response(str(e))

    if Player.query.filter_by(username=username).first():
        return error_response(f"username '{username}' is already taken", 409)
    if Player.query.filter_by(email=email).first():
        return error_response(f"email '{email}' is already registered", 409)

    player = Player(username=username, email=email, region=region)
    db.session.add(player)
    db.session.commit()
    return success_response(player.to_dict(), 201)

@players_bp.route("/<int:player_id>", methods=["GET"])
def get_player(player_id):
    player = Player.query.get_or_404(player_id, description=f"player {player_id} not found")
    return success_response(player.to_dict())

@players_bp.route("/<int:player_id>", methods=["PUT"])
@jwt_required()
def update_player(player_id):
    player = Player.query.get_or_404(player_id, description=f"player {player_id} not found")
    data = request.get_json(silent=True)
    if not data:
        return error_response("request body must be JSON")

    try:
        if "username" in data:
            username = validate_username(data["username"])
            if Player.query.filter(Player.username == username, Player.id != player_id).first():
                return error_response(f"username '{username}' is already taken", 409)
            player.username = username

        if "email" in data:
            email = validate_email_address(data["email"])
            if Player.query.filter(Player.email == email, Player.id != player_id).first():
                return error_response(f"email '{email}' is already registered", 409)
            player.email = email

        if "region" in data:
            player.region = validate_region(data["region"])

    except ValueError as e:
        return error_response(str(e))

    db.session.commit()
    return success_response(player.to_dict())

@players_bp.route("/<int:player_id>", methods=["DELETE"])
@jwt_required()
def delete_player(player_id):
    player = Player.query.get_or_404(player_id, description=f"player {player_id} not found")
    db.session.delete(player)
    db.session.commit()
    return success_response({"message": f"player '{player.username}' deleted"})

@players_bp.route("/<int:player_id>/stats", methods=["GET"])
def player_stats(player_id):
    player = Player.query.get_or_404(player_id, description=f"player {player_id} not found")
    return success_response({
        "player_id": player.id,
        "username": player.username,
        "region": player.region,
        "stats": player.aggregate_stats(),
    })

@players_bp.route("/<int:player_id>/match-history", methods=["GET"])
def match_history(player_id):
    player = Player.query.get_or_404(player_id, description=f"player {player_id} not found")
    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", 10, type=int), 50)

    pagination = (
        MatchParticipant.query
        .filter_by(player_id=player_id)
        .join(Match)
        .order_by(Match.created_at.desc())
        .paginate(page=page, per_page=per_page, error_out=False)
    )

    return success_response({
        "player_id": player_id,
        "username": player.username,
        "history": [p.to_dict() for p in pagination.items],
        "total": pagination.total,
        "page": pagination.page,
        "pages": pagination.pages,
    })
