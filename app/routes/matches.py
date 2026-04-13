from flask import Blueprint, request
from flask_jwt_extended import jwt_required
from datetime import datetime, timezone
from app.extensions import db
from app.models import Match, MatchParticipant, Player, Agent, GAME_MODES, TEAM_SIDES
from app.validators import (
    error_response, success_response, require_fields,
    validate_enum, validate_non_negative_int
)

matches_bp = Blueprint("matches", __name__, url_prefix="/matches")
agents_bp = Blueprint("agents", __name__, url_prefix="/agents")

VALORANT_MAPS = [
    "Abyss", "Ascent", "Bind", "Breeze", "Fracture",
    "Haven", "Icebox", "Lotus", "Pearl", "Split", "Sunset"
]

def validate_map(value):
    value = value.strip().title()
    if value not in VALORANT_MAPS:
        raise ValueError(f"unknown map '{value}'. valid maps: {', '.join(VALORANT_MAPS)}")
    return value

def check_match_editable(match):
    if match.status == "completed":
        raise ValueError("match is completed, stats are locked")

def resolve_winner_flags(match):
    winning_side = match.winning_side()
    for p in match.participants:
        p.is_winner = (p.team_side == winning_side) if winning_side else False

@matches_bp.route("", methods=["GET"])
def list_matches():
    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", 20, type=int), 100)
    status = request.args.get("status")
    map_name = request.args.get("map")
    mode = request.args.get("mode")

    query = Match.query.order_by(Match.created_at.desc())
    if status:
        query = query.filter(Match.status == status)
    if map_name:
        query = query.filter(Match.map_name.ilike(f"%{map_name}%"))
    if mode:
        query = query.filter(Match.game_mode == mode)

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    return success_response({
        "matches": [m.to_dict() for m in pagination.items],
        "total": pagination.total,
        "page": pagination.page,
        "pages": pagination.pages,
    })

@matches_bp.route("", methods=["POST"])
@jwt_required()
def create_match():
    data = request.get_json(silent=True)
    if not data:
        return error_response("request body must be JSON")
    try:
        require_fields(data, "map_name")
        map_name = validate_map(data["map_name"])
        game_mode = validate_enum(data.get("game_mode", "unrated"), GAME_MODES, "game_mode")
    except ValueError as e:
        return error_response(str(e))

    match = Match(map_name=map_name, game_mode=game_mode)
    db.session.add(match)
    db.session.commit()
    return success_response(match.to_dict(), 201)

@matches_bp.route("/<int:match_id>", methods=["GET"])
def get_match(match_id):
    match = Match.query.get_or_404(match_id, description=f"match {match_id} not found")
    return success_response(match.to_dict(include_participants=True))

@matches_bp.route("/<int:match_id>", methods=["PUT"])
@jwt_required()
def update_match(match_id):
    match = Match.query.get_or_404(match_id, description=f"match {match_id} not found")
    data = request.get_json(silent=True)
    if not data:
        return error_response("request body must be JSON")
    try:
        check_match_editable(match)
        if "map_name" in data:
            match.map_name = validate_map(data["map_name"])
        if "game_mode" in data:
            match.game_mode = validate_enum(data["game_mode"], GAME_MODES, "game_mode")
    except ValueError as e:
        return error_response(str(e))

    db.session.commit()
    return success_response(match.to_dict())

@matches_bp.route("/<int:match_id>", methods=["DELETE"])
@jwt_required()
def delete_match(match_id):
    match = Match.query.get_or_404(match_id, description=f"match {match_id} not found")
    db.session.delete(match)
    db.session.commit()
    return success_response({"message": f"match {match_id} deleted"})

# pending -> ongoing -> completed
STATUS_TRANSITIONS = {"pending": "ongoing", "ongoing": "completed"}

# order matters here, can't skip from pending straight to completed

@matches_bp.route("/<int:match_id>/status", methods=["PATCH"])
@jwt_required()
def advance_status(match_id):
    match = Match.query.get_or_404(match_id, description=f"match {match_id} not found")
    data = request.get_json(silent=True) or {}

    if match.status == "completed":
        return error_response("match is already completed")

    next_status = STATUS_TRANSITIONS.get(match.status)
    if not next_status:
        return error_response("no valid status transition available")

    if next_status == "completed":
        a_score = data.get("team_a_score")
        b_score = data.get("team_b_score")
        if a_score is None or b_score is None:
            return error_response("team_a_score and team_b_score are required to complete a match")
        try:
            a_score = validate_non_negative_int(a_score, "team_a_score")
            b_score = validate_non_negative_int(b_score, "team_b_score")
        except ValueError as e:
            return error_response(str(e))

        sides = {p.team_side for p in match.participants}
        if "team_a" not in sides or "team_b" not in sides:
            return error_response("both teams need at least one participant before completing")

        match.team_a_score = a_score
        match.team_b_score = b_score
        match.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
        resolve_winner_flags(match)

    if next_status == "ongoing":
        match.started_at = datetime.now(timezone.utc).replace(tzinfo=None)

    match.status = next_status
    db.session.commit()
    return success_response(match.to_dict(include_participants=True))

@matches_bp.route("/<int:match_id>/participants", methods=["GET"])
def list_participants(match_id):
    match = Match.query.get_or_404(match_id, description=f"match {match_id} not found")
    team = request.args.get("team")
    participants = match.participants
    if team:
        participants = participants.filter(MatchParticipant.team_side == team)
    return success_response({
        "match_id": match_id,
        "participants": [p.to_dict() for p in participants],
    })

def parse_stat_fields(data):
    # only validates fields that are actually present, so partial updates work fine
    stats = {}
    for field in ["kills", "deaths", "assists", "headshots", "spike_plants", "spike_defuses", "combat_score"]:
        if field in data:
            stats[field] = validate_non_negative_int(data[field], field)
    # headshots can't be more than kills
    if stats.get("headshots", 0) > stats.get("kills", 0) and "kills" in stats:
        raise ValueError("headshots can't be more than kills")
    return stats

@matches_bp.route("/<int:match_id>/participants", methods=["POST"])
@jwt_required()
def add_participant(match_id):
    match = Match.query.get_or_404(match_id, description=f"match {match_id} not found")
    data = request.get_json(silent=True)
    if not data:
        return error_response("request body must be JSON")

    try:
        check_match_editable(match)
        require_fields(data, "player_id", "team_side")
        player_id = int(data["player_id"])
        team_side = validate_enum(data["team_side"], TEAM_SIDES, "team_side")
        stats = parse_stat_fields(data)
    except (ValueError, TypeError) as e:
        return error_response(str(e))

    player = Player.query.get(player_id)
    if not player:
        return error_response(f"player {player_id} not found", 404)

    if MatchParticipant.query.filter_by(match_id=match_id, player_id=player_id).first():
        return error_response(f"player {player_id} is already in this match", 409)

    agent_id = data.get("agent_id")
    if agent_id:
        agent = Agent.query.get(int(agent_id))
        if not agent:
            return error_response(f"agent {agent_id} not found", 404)

    participant = MatchParticipant(
        match_id=match_id, player_id=player_id,
        agent_id=agent_id, team_side=team_side, **stats
    )
    db.session.add(participant)
    db.session.commit()
    return success_response(participant.to_dict(), 201)

@matches_bp.route("/<int:match_id>/participants/<int:participant_id>", methods=["PUT"])
@jwt_required()
def update_participant(match_id, participant_id):
    match = Match.query.get_or_404(match_id, description=f"match {match_id} not found")
    p = MatchParticipant.query.filter_by(id=participant_id, match_id=match_id).first()
    if not p:
        return error_response(f"participant {participant_id} not found in match {match_id}", 404)
    data = request.get_json(silent=True)
    if not data:
        return error_response("request body must be JSON")

    try:
        check_match_editable(match)
        stats = parse_stat_fields(data)
        if "team_side" in data:
            p.team_side = validate_enum(data["team_side"], TEAM_SIDES, "team_side")
        if "agent_id" in data:
            p.agent_id = int(data["agent_id"]) if data["agent_id"] else None
    except ValueError as e:
        return error_response(str(e))

    for field, value in stats.items():
        setattr(p, field, value)

    db.session.commit()
    return success_response(p.to_dict())

@matches_bp.route("/<int:match_id>/participants/<int:participant_id>", methods=["DELETE"])
@jwt_required()
def remove_participant(match_id, participant_id):
    match = Match.query.get_or_404(match_id, description=f"match {match_id} not found")
    p = MatchParticipant.query.filter_by(id=participant_id, match_id=match_id).first()
    if not p:
        return error_response(f"participant {participant_id} not found in match {match_id}", 404)
    try:
        check_match_editable(match)
    except ValueError as e:
        return error_response(str(e))

    db.session.delete(p)
    db.session.commit()
    return success_response({"message": f"participant {participant_id} removed"})

@agents_bp.route("", methods=["GET"])
def list_agents():
    role = request.args.get("role")
    query = Agent.query.order_by(Agent.name)
    if role:
        query = query.filter(Agent.role == role)
    return success_response({"agents": [a.to_dict() for a in query.all()]})