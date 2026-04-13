from flask import Blueprint, request
from app.models import Player, REGIONS
from app.validators import success_response, error_response

leaderboard_bp = Blueprint("leaderboard", __name__, url_prefix="/leaderboard")

@leaderboard_bp.route("", methods=["GET"])
def get_leaderboard():
    region = request.args.get("region")
    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", 20, type=int), 100)

    if region:
        region = region.upper()
        if region not in REGIONS:
            return error_response(f"region must be one of: {', '.join(sorted(REGIONS))}")

    # pull all players first, then sort by win rate after aggregating stats
    # couldn't figure out how to do this purely in SQL with the computed stats
    query = Player.query
    if region:
        query = query.filter(Player.region == region)

    all_players = query.all()

    ranked = []
    for p in all_players:
        stats = p.aggregate_stats()
        if stats["matches_played"] == 0:
            continue
        ranked.append({"player": p.to_dict(), "stats": stats})

    ranked.sort(key=lambda x: (
        x["stats"]["win_rate"],
        x["stats"]["kda_ratio"],
        x["stats"]["avg_combat_score"]
    ), reverse=True)

    # manual pagination since we sorted in python
    total = len(ranked)
    start = (page - 1) * per_page
    end = start + per_page
    page_items = ranked[start:end]

    return success_response({
        "leaderboard": page_items,
        "total": total,
        "page": page,
        "pages": -(-total // per_page),  # ceiling division
    })
