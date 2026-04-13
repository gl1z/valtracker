import math
from flask import Blueprint, request
from flask_jwt_extended import jwt_required
from datetime import datetime, timezone
from app.extensions import db
from app.models import (
    Tournament, Team, TeamMember, TournamentMatch,
    Match, Player, TOURNAMENT_FORMATS, TOURNAMENT_STATUSES
)
from app.validators import (
    error_response, success_response, require_fields,
    validate_string, validate_enum, validate_positive_int,
    validate_non_negative_int
)

tournaments_bp = Blueprint("tournaments", __name__, url_prefix="/tournaments")

@tournaments_bp.route("", methods=["GET"])
def list_tournaments():
    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", 20, type=int), 100)
    status = request.args.get("status")

    query = Tournament.query.order_by(Tournament.created_at.desc())
    if status:
        if status not in TOURNAMENT_STATUSES:
            return error_response(f"status must be one of: {', '.join(TOURNAMENT_STATUSES)}")
        query = query.filter(Tournament.status == status)

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    return success_response({
        "tournaments": [t.to_dict() for t in pagination.items],
        "total": pagination.total,
        "page": pagination.page,
        "pages": pagination.pages,
    })

@tournaments_bp.route("", methods=["POST"])
@jwt_required()
def create_tournament():
    data = request.get_json(silent=True)
    if not data:
        return error_response("request body must be JSON")
    try:
        require_fields(data, "name")
        name = validate_string(data["name"], "name", min_len=3, max_len=80)
        fmt = validate_enum(
            data.get("format", "single_elimination"),
            TOURNAMENT_FORMATS, "format"
        )
        max_teams = validate_positive_int(data.get("max_teams", 8), "max_teams")
        if fmt == "single_elimination" and not _is_power_of_two(max_teams):
            raise ValueError("single elimination needs max_teams to be a power of 2 (2, 4, 8, 16...)")
    except ValueError as e:
        return error_response(str(e))

    if Tournament.query.filter_by(name=name).first():
        return error_response(f"tournament name '{name}' already taken", 409)

    t = Tournament(name=name, format=fmt, max_teams=max_teams)
    db.session.add(t)
    db.session.commit()
    return success_response(t.to_dict(), 201)

@tournaments_bp.route("/<int:tid>", methods=["GET"])
def get_tournament(tid):
    t = Tournament.query.get_or_404(tid, description=f"tournament {tid} not found")
    return success_response(t.to_dict(include_teams=True))

@tournaments_bp.route("/<int:tid>", methods=["PUT"])
@jwt_required()
def update_tournament(tid):
    t = Tournament.query.get_or_404(tid, description=f"tournament {tid} not found")
    if t.status != "registration":
        return error_response("can only update tournaments that are still in registration")
    data = request.get_json(silent=True)
    if not data:
        return error_response("request body must be JSON")
    try:
        if "name" in data:
            name = validate_string(data["name"], "name", min_len=3, max_len=80)
            if Tournament.query.filter(Tournament.name == name, Tournament.id != tid).first():
                return error_response(f"tournament name '{name}' already taken", 409)
            t.name = name
        if "max_teams" in data:
            t.max_teams = validate_positive_int(data["max_teams"], "max_teams")
    except ValueError as e:
        return error_response(str(e))

    db.session.commit()
    return success_response(t.to_dict())

@tournaments_bp.route("/<int:tid>", methods=["DELETE"])
@jwt_required()
def delete_tournament(tid):
    t = Tournament.query.get_or_404(tid, description=f"tournament {tid} not found")
    db.session.delete(t)
    db.session.commit()
    return success_response({"message": f"tournament '{t.name}' deleted"})

@tournaments_bp.route("/<int:tid>/teams", methods=["GET"])
def list_teams(tid):
    t = Tournament.query.get_or_404(tid)
    return success_response({
        "tournament_id": tid,
        "teams": [team.to_dict(include_members=True) for team in t.teams],
    })

@tournaments_bp.route("/<int:tid>/teams", methods=["POST"])
@jwt_required()
def add_team(tid):
    t = Tournament.query.get_or_404(tid, description=f"tournament {tid} not found")
    if t.status != "registration":
        return error_response("teams can only be added during registration")
    data = request.get_json(silent=True)
    if not data:
        return error_response("request body must be JSON")
    try:
        require_fields(data, "name")
        name = validate_string(data["name"], "name", min_len=2, max_len=60)
    except ValueError as e:
        return error_response(str(e))

    if t.teams.count() >= t.max_teams:
        return error_response(f"tournament is full ({t.max_teams} teams max)", 409)
    if Team.query.filter_by(tournament_id=tid, name=name).first():
        return error_response(f"team '{name}' already exists in this tournament", 409)

    team = Team(name=name, tournament_id=tid)
    db.session.add(team)
    db.session.commit()
    return success_response(team.to_dict(include_members=True), 201)

@tournaments_bp.route("/<int:tid>/teams/<int:team_id>", methods=["DELETE"])
@jwt_required()
def remove_team(tid, team_id):
    t = Tournament.query.get_or_404(tid)
    team = Team.query.filter_by(id=team_id, tournament_id=tid).first()
    if not team:
        return error_response(f"team {team_id} not found in tournament {tid}", 404)
    if t.status != "registration":
        return error_response("teams can only be removed during registration")
    db.session.delete(team)
    db.session.commit()
    return success_response({"message": f"team '{team.name}' removed"})

@tournaments_bp.route("/<int:tid>/teams/<int:team_id>/members", methods=["POST"])
@jwt_required()
def add_team_member(tid, team_id):
    t = Tournament.query.get_or_404(tid)
    team = Team.query.filter_by(id=team_id, tournament_id=tid).first()
    if not team:
        return error_response(f"team {team_id} not found in tournament {tid}", 404)
    if t.status != "registration":
        return error_response("players can only be added during registration")
    data = request.get_json(silent=True)
    if not data:
        return error_response("request body must be JSON")
    try:
        require_fields(data, "player_id")
        player_id = int(data["player_id"])
    except (ValueError, TypeError):
        return error_response("player_id must be an integer")

    player = Player.query.get(player_id)
    if not player:
        return error_response(f"player {player_id} not found", 404)

    # check player isn't already in another team in this tournament
    existing = (
        TeamMember.query.join(Team)
        .filter(Team.tournament_id == tid, TeamMember.player_id == player_id)
        .first()
    )
    if existing:
        return error_response(
            f"player '{player.username}' is already on team '{existing.team.name}' in this tournament", 409
        )

    member = TeamMember(team_id=team_id, player_id=player_id)
    db.session.add(member)
    db.session.commit()
    return success_response(member.to_dict(), 201)

@tournaments_bp.route("/<int:tid>/teams/<int:team_id>/members/<int:player_id>", methods=["DELETE"])
@jwt_required()
def remove_team_member(tid, team_id, player_id):
    t = Tournament.query.get_or_404(tid)
    team = Team.query.filter_by(id=team_id, tournament_id=tid).first()
    if not team:
        return error_response(f"team {team_id} not found in tournament {tid}", 404)
    if t.status != "registration":
        return error_response("players can only be removed during registration")
    member = TeamMember.query.filter_by(team_id=team_id, player_id=player_id).first()
    if not member:
        return error_response(f"player {player_id} is not in team {team_id}", 404)
    db.session.delete(member)
    db.session.commit()
    return success_response({"message": f"player {player_id} removed from team {team_id}"})

def _is_power_of_two(n):
    return n > 0 and (n & (n - 1)) == 0

def _generate_single_elimination(tournament):
    teams = list(tournament.teams.all())
    n = len(teams)
    if not _is_power_of_two(n):
        raise ValueError(f"single elimination needs a power of 2 team count, got {n}")

    total_rounds = int(math.log2(n))

    for round_num in range(1, total_rounds + 1):
        slots = n // (2 ** round_num)
        for pos in range(1, slots + 1):
            tm = TournamentMatch(
                tournament_id=tournament.id,
                round_number=round_num,
                bracket_position=pos,
            )
            db.session.add(tm)

    db.session.flush()

    round1_slots = (
        TournamentMatch.query
        .filter_by(tournament_id=tournament.id, round_number=1)
        .order_by(TournamentMatch.bracket_position)
        .all()
    )
    for i, slot in enumerate(round1_slots):
        slot.team_a_id = teams[i].id
        slot.team_b_id = teams[n - 1 - i].id
        match = Match(map_name="Ascent", game_mode="competitive", status="pending")
        db.session.add(match)
        db.session.flush()
        slot.match_id = match.id

def _generate_round_robin(tournament):
    teams = list(tournament.teams.all())
    n = len(teams)
    pos = 1
    for i in range(n):
        for j in range(i + 1, n):
            match = Match(map_name="Ascent", game_mode="competitive", status="pending")
            db.session.add(match)
            db.session.flush()
            tm = TournamentMatch(
                tournament_id=tournament.id,
                match_id=match.id,
                team_a_id=teams[i].id,
                team_b_id=teams[j].id,
                round_number=1,
                bracket_position=pos,
            )
            db.session.add(tm)
            pos += 1

@tournaments_bp.route("/<int:tid>/start", methods=["PATCH"])
@jwt_required()
def start_tournament(tid):
    t = Tournament.query.get_or_404(tid, description=f"tournament {tid} not found")
    if t.status != "registration":
        return error_response("tournament has already been started")
    if t.teams.count() < 2:
        return error_response("need at least 2 teams to start")

    try:
        if t.format == "single_elimination":
            _generate_single_elimination(t)
        else:
            _generate_round_robin(t)
    except ValueError as e:
        db.session.rollback()
        return error_response(str(e))

    t.status = "ongoing"
    db.session.commit()
    return success_response({"message": f"tournament '{t.name}' started", "tournament": t.to_dict(include_teams=True)})

@tournaments_bp.route("/<int:tid>/bracket", methods=["GET"])
def get_bracket(tid):
    t = Tournament.query.get_or_404(tid, description=f"tournament {tid} not found")
    if t.status == "registration":
        return error_response("bracket hasn't been generated yet")

    matches = (
        TournamentMatch.query
        .filter_by(tournament_id=tid)
        .order_by(TournamentMatch.round_number, TournamentMatch.bracket_position)
        .all()
    )

    rounds = {}
    for tm in matches:
        rounds.setdefault(tm.round_number, []).append(tm.to_dict())

    return success_response({
        "tournament_id": tid,
        "format": t.format,
        "status": t.status,
        "rounds": [{"round": r, "matches": rounds[r]} for r in sorted(rounds.keys())],
    })

@tournaments_bp.route("/<int:tid>/bracket/<int:tm_id>/result", methods=["PATCH"])
@jwt_required()
def report_result(tid, tm_id):
    t = Tournament.query.get_or_404(tid)
    tm = TournamentMatch.query.filter_by(id=tm_id, tournament_id=tid).first()
    if not tm:
        return error_response(f"bracket match {tm_id} not found in tournament {tid}", 404)
    if t.status != "ongoing":
        return error_response("tournament is not in progress")
    if tm.winner_team_id:
        return error_response("this match already has a result")
    if not tm.team_a_id or not tm.team_b_id:
        return error_response("both teams need to be assigned before reporting a result")

    data = request.get_json(silent=True) or {}
    try:
        require_fields(data, "team_a_score", "team_b_score")
        a_score = validate_non_negative_int(data["team_a_score"], "team_a_score")
        b_score = validate_non_negative_int(data["team_b_score"], "team_b_score")
        if a_score == b_score:
            raise ValueError("draws are not allowed in tournament matches")
    except ValueError as e:
        return error_response(str(e))

    winner_id = tm.team_a_id if a_score > b_score else tm.team_b_id
    tm.winner_team_id = winner_id

    if tm.match:
        tm.match.team_a_score = a_score
        tm.match.team_b_score = b_score
        tm.match.status = "completed"
        tm.match.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)

    # advance winner in single elimination
    if t.format == "single_elimination":
        next_round = tm.round_number + 1
        next_pos = math.ceil(tm.bracket_position / 2)
        next_slot = TournamentMatch.query.filter_by(
            tournament_id=tid, round_number=next_round, bracket_position=next_pos
        ).first()

        if next_slot:
            if tm.bracket_position % 2 == 1:
                next_slot.team_a_id = winner_id
            else:
                next_slot.team_b_id = winner_id

            if next_slot.team_a_id and next_slot.team_b_id and not next_slot.match_id:
                new_match = Match(map_name="Ascent", game_mode="competitive", status="pending")
                db.session.add(new_match)
                db.session.flush()
                next_slot.match_id = new_match.id

    # check if tournament is over
    unresolved = TournamentMatch.query.filter_by(
        tournament_id=tid, winner_team_id=None
    ).filter(
        TournamentMatch.team_a_id.isnot(None),
        TournamentMatch.team_b_id.isnot(None),
    ).count()

    if unresolved == 0:
        t.status = "completed"

    db.session.commit()
    return success_response({
        "tournament_match": tm.to_dict(),
        "winner": {"team_id": tm.winner_team_id, "team_name": tm.winner_team.name if tm.winner_team else None},
        "tournament_status": t.status,
    })
