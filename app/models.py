from datetime import datetime, timezone
from app.extensions import db

# these just group the valid string values so i don't typo them in routes
REGIONS = {"EU", "NA", "CN", "KR", "BR", "LATAM", "AP"}
AGENT_ROLES = ["duelist", "controller", "sentinel", "initiator"]
MATCH_STATUSES = ["pending", "ongoing", "completed"]
GAME_MODES = ["unrated", "competitive", "spike_rush", "deathmatch",
              "swiftplay", "team_deathmatch","escalation",
              "skirmish" , "knockout", "premier"]
TEAM_SIDES = ["team_a", "team_b"]
TOURNAMENT_STATUSES = ["registration", "ongoing", "completed"]
TOURNAMENT_FORMATS = ["single_elimination", "round_robin"]

def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)

class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    def set_password(self, password):
        from werkzeug.security import generate_password_hash
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        from werkzeug.security import check_password_hash
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {"id": self.id, "username": self.username, "email": self.email}

class Player(db.Model):
    __tablename__ = "players"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(32), nullable=False, unique=True, index=True)
    email = db.Column(db.String(120), nullable=False, unique=True, index=True)
    region = db.Column(db.String(16), nullable=False, default="NA")
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    participations = db.relationship(
        "MatchParticipant", back_populates="player", lazy="dynamic", cascade="all, delete-orphan"
    )
    team_memberships = db.relationship(
        "TeamMember", back_populates="player", lazy="dynamic", cascade="all, delete-orphan"
    )

    def aggregate_stats(self):
        rows = (
            self.participations.join(Match)
            .filter(Match.status == "completed")
            .all()
        )
        if not rows:
            return {
                "matches_played": 0, "wins": 0, "losses": 0,
                "win_rate": 0.0, "total_kills": 0, "total_deaths": 0,
                "total_assists": 0, "kda_ratio": 0.0,
                "headshot_pct": 0.0, "avg_combat_score": 0.0,
            }

        played = len(rows)
        wins = sum(1 for r in rows if r.is_winner)
        kills = sum(r.kills for r in rows)
        deaths = sum(r.deaths for r in rows)
        assists = sum(r.assists for r in rows)
        headshots = sum(r.headshots for r in rows)
        score = sum(r.combat_score for r in rows)

        return {
            "matches_played": played,
            "wins": wins,
            "losses": played - wins,
            "win_rate": round(wins / played * 100, 2),
            "total_kills": kills,
            "total_deaths": deaths,
            "total_assists": assists,
            "kda_ratio": round((kills + assists) / max(deaths, 1), 3),
            "headshot_pct": round(headshots / max(kills, 1) * 100, 2),
            "avg_combat_score": round(score / played, 2),
        }

    def to_dict(self, include_stats=False):
        data = {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "region": self.region,
            "created_at": self.created_at.isoformat(),
        }
        if include_stats:
            data["stats"] = self.aggregate_stats()
        return data

class Agent(db.Model):
    __tablename__ = "agents"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(32), nullable=False, unique=True)
    role = db.Column(db.String(16), nullable=False)

    participations = db.relationship("MatchParticipant", back_populates="agent", lazy="dynamic")

    def to_dict(self):
        return {"id": self.id, "name": self.name, "role": self.role}

class Match(db.Model):
    __tablename__ = "matches"

    id = db.Column(db.Integer, primary_key=True)
    map_name = db.Column(db.String(32), nullable=False)
    game_mode = db.Column(db.String(20), nullable=False, default="unrated")
    status = db.Column(db.String(12), nullable=False, default="pending")
    team_a_score = db.Column(db.Integer, nullable=True)
    team_b_score = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    started_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)

    participants = db.relationship(
        "MatchParticipant", back_populates="match", lazy="dynamic", cascade="all, delete-orphan"
    )
    tournament_match = db.relationship("TournamentMatch", back_populates="match", uselist=False)

    def winning_side(self):
        if self.team_a_score is None or self.team_b_score is None:
            return None
        if self.team_a_score > self.team_b_score:
            return "team_a"
        if self.team_b_score > self.team_a_score:
            return "team_b"
        return None

    def to_dict(self, include_participants=False):
        data = {
            "id": self.id,
            "map_name": self.map_name,
            "game_mode": self.game_mode,
            "status": self.status,
            "team_a_score": self.team_a_score,
            "team_b_score": self.team_b_score,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }
        if include_participants:
            data["participants"] = [p.to_dict() for p in self.participants]
        return data

class MatchParticipant(db.Model):
    __tablename__ = "match_participants"

    id = db.Column(db.Integer, primary_key=True)
    match_id = db.Column(db.Integer, db.ForeignKey("matches.id", ondelete="CASCADE"), nullable=False)
    player_id = db.Column(db.Integer, db.ForeignKey("players.id", ondelete="CASCADE"), nullable=False)
    agent_id = db.Column(db.Integer, db.ForeignKey("agents.id", ondelete="SET NULL"), nullable=True)
    team_side = db.Column(db.String(8), nullable=False)
    kills = db.Column(db.Integer, nullable=False, default=0)
    deaths = db.Column(db.Integer, nullable=False, default=0)
    assists = db.Column(db.Integer, nullable=False, default=0)
    headshots = db.Column(db.Integer, nullable=False, default=0)
    spike_plants = db.Column(db.Integer, nullable=False, default=0)
    spike_defuses = db.Column(db.Integer, nullable=False, default=0)
    combat_score = db.Column(db.Integer, nullable=False, default=0)
    is_winner = db.Column(db.Boolean, nullable=False, default=False)

    __table_args__ = (
        db.UniqueConstraint("match_id", "player_id", name="uq_participant_match_player"),
    )

    match = db.relationship("Match", back_populates="participants")
    player = db.relationship("Player", back_populates="participations")
    agent = db.relationship("Agent", back_populates="participations")

    @property
    def kda(self):
        return round((self.kills + self.assists) / max(self.deaths, 1), 3)

    @property
    def headshot_pct(self):
        return round(self.headshots / max(self.kills, 1) * 100, 2)

    def to_dict(self):
        return {
            "id": self.id,
            "match_id": self.match_id,
            "player_id": self.player_id,
            "player_username": self.player.username if self.player else None,
            "agent": self.agent.name if self.agent else None,
            "team_side": self.team_side,
            "kills": self.kills,
            "deaths": self.deaths,
            "assists": self.assists,
            "headshots": self.headshots,
            "headshot_pct": self.headshot_pct,
            "spike_plants": self.spike_plants,
            "spike_defuses": self.spike_defuses,
            "combat_score": self.combat_score,
            "kda": self.kda,
            "is_winner": self.is_winner,
        }

class Tournament(db.Model):
    __tablename__ = "tournaments"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False, unique=True)
    format = db.Column(db.String(24), nullable=False, default="single_elimination")
    status = db.Column(db.String(16), nullable=False, default="registration")
    max_teams = db.Column(db.Integer, nullable=False, default=8)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    teams = db.relationship("Team", back_populates="tournament", lazy="dynamic", cascade="all, delete-orphan")
    tournament_matches = db.relationship("TournamentMatch", back_populates="tournament", lazy="dynamic", cascade="all, delete-orphan")

    def to_dict(self, include_teams=False):
        data = {
            "id": self.id,
            "name": self.name,
            "format": self.format,
            "status": self.status,
            "max_teams": self.max_teams,
            "team_count": self.teams.count(),
            "created_at": self.created_at.isoformat(),
        }
        if include_teams:
            data["teams"] = [t.to_dict() for t in self.teams]
        return data

class Team(db.Model):
    __tablename__ = "teams"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(60), nullable=False)
    tournament_id = db.Column(db.Integer, db.ForeignKey("tournaments.id", ondelete="CASCADE"), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    __table_args__ = (
        db.UniqueConstraint("tournament_id", "name", name="uq_team_name_per_tournament"),
    )

    tournament = db.relationship("Tournament", back_populates="teams")
    members = db.relationship("TeamMember", back_populates="team", lazy="dynamic", cascade="all, delete-orphan")
    home_matches = db.relationship("TournamentMatch", foreign_keys="TournamentMatch.team_a_id", back_populates="team_a")
    away_matches = db.relationship("TournamentMatch", foreign_keys="TournamentMatch.team_b_id", back_populates="team_b")
    wins = db.relationship("TournamentMatch", foreign_keys="TournamentMatch.winner_team_id", back_populates="winner_team")

    def to_dict(self, include_members=False):
        data = {
            "id": self.id,
            "name": self.name,
            "tournament_id": self.tournament_id,
            "member_count": self.members.count(),
            "created_at": self.created_at.isoformat(),
        }
        if include_members:
            data["members"] = [m.to_dict() for m in self.members]
        return data

class TeamMember(db.Model):
    __tablename__ = "team_members"

    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey("teams.id", ondelete="CASCADE"), nullable=False)
    player_id = db.Column(db.Integer, db.ForeignKey("players.id", ondelete="CASCADE"), nullable=False)
    joined_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    __table_args__ = (
        db.UniqueConstraint("team_id", "player_id", name="uq_team_member"),
    )

    team = db.relationship("Team", back_populates="members")
    player = db.relationship("Player", back_populates="team_memberships")

    def to_dict(self):
        return {
            "player_id": self.player_id,
            "player_username": self.player.username if self.player else None,
            "team_id": self.team_id,
            "joined_at": self.joined_at.isoformat(),
        }

class TournamentMatch(db.Model):
    __tablename__ = "tournament_matches"

    id = db.Column(db.Integer, primary_key=True)
    tournament_id = db.Column(db.Integer, db.ForeignKey("tournaments.id", ondelete="CASCADE"), nullable=False)
    match_id = db.Column(db.Integer, db.ForeignKey("matches.id", ondelete="SET NULL"), nullable=True)
    team_a_id = db.Column(db.Integer, db.ForeignKey("teams.id", ondelete="SET NULL"), nullable=True)
    team_b_id = db.Column(db.Integer, db.ForeignKey("teams.id", ondelete="SET NULL"), nullable=True)
    winner_team_id = db.Column(db.Integer, db.ForeignKey("teams.id", ondelete="SET NULL"), nullable=True)
    round_number = db.Column(db.Integer, nullable=False)
    bracket_position = db.Column(db.Integer, nullable=False)
    best_of = db.Column(db.Integer, nullable=False, default=3)

    __table_args__ = (
        db.UniqueConstraint("tournament_id", "round_number", "bracket_position", name="uq_bracket_slot"),
    )

    tournament = db.relationship("Tournament", back_populates="tournament_matches")
    match = db.relationship("Match", back_populates="tournament_match")
    team_a = db.relationship("Team", foreign_keys=[team_a_id], back_populates="home_matches")
    team_b = db.relationship("Team", foreign_keys=[team_b_id], back_populates="away_matches")
    winner_team = db.relationship("Team", foreign_keys=[winner_team_id], back_populates="wins")

    def to_dict(self):
        return {
            "id": self.id,
            "tournament_id": self.tournament_id,
            "match_id": self.match_id,
            "round_number": self.round_number,
            "bracket_position": self.bracket_position,
            "best_of": self.best_of,
            "team_a": {"id": self.team_a_id, "name": self.team_a.name} if self.team_a else None,
            "team_b": {"id": self.team_b_id, "name": self.team_b.name} if self.team_b else None,
            "winner_team": {"id": self.winner_team_id, "name": self.winner_team.name} if self.winner_team else None,
            "score": {
                "team_a": self.match.team_a_score,
                "team_b": self.match.team_b_score,
            } if self.match else None,
        }