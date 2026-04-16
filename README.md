# ValTracker

A REST API for tracking Valorant tournaments, teams, players, and match results.

Built with Flask, SQLAlchemy, and PostgreSQL. Runs locally with Docker.

---

## What it does

- Register and manage players with region support (NA, EU, AP, KR, BR, LATAM, CN)
- Create matches, record per-player stats (kills, deaths, assists, headshots, combat score)
- Run tournaments with single elimination or round robin bracket generation
- Leaderboard with win rate, KDA, and combat score rankings
- JWT authentication — write operations require a valid token

---

## Tech stack

| Layer | Technology |
|---|---|
| Framework | Flask 3.x |
| ORM | SQLAlchemy + Flask-SQLAlchemy |
| Database | PostgreSQL |
| Auth | Flask-JWT-Extended |
| Runtime | Python 3.11 |

---

## Running locally with Docker

```bash
docker compose up
```

API runs on `http://localhost:5000`. PostgreSQL on port 5432.

---

## Running without Docker

```bash
python -m venv .venv
.venv\Scripts\activate

pip install -r requirements.txt
python run.py
```

Falls back to SQLite if no `DATABASE_URL` is set.

---

## Auth

Register and log in to get a token. Pass it as a Bearer token on any write request.

POST /auth/register
POST /auth/login
GET  /auth/me

---

## Rate Limiting

Auth endpoints are rate limited to prevent brute force attacks.

| Endpoint | Default Limit |
|---|---|
| POST /auth/login | 10 per minute |
| POST /auth/register | 5 per minute |

Override via environment variables:
- `AUTH_LOGIN_RATE_LIMIT`
- `AUTH_REGISTER_RATE_LIMIT`

Exceeding the limit returns `429 Too Many Requests`.
---

## Endpoints

### Players

GET    /players
POST   /players
GET    /players/<id>
PUT    /players/<id>
DELETE /players/<id>
GET    /players/<id>/stats
GET    /players/<id>/match-history

### Matches

GET    /matches
POST   /matches
GET    /matches/<id>
PUT    /matches/<id>
DELETE /matches/<id>
PATCH  /matches/<id>/status
GET    /matches/<id>/participants
POST   /matches/<id>/participants
PUT    /matches/<id>/participants/<id>
DELETE /matches/<id>/participants/<id>

### Tournaments

GET    /tournaments
POST   /tournaments
GET    /tournaments/<id>
PUT    /tournaments/<id>
DELETE /tournaments/<id>
PATCH  /tournaments/<id>/start
GET    /tournaments/<id>/bracket
GET    /tournaments/<id>/teams
POST   /tournaments/<id>/teams
DELETE /tournaments/<id>/teams/<id>
POST   /tournaments/<id>/teams/<id>/members
DELETE /tournaments/<id>/teams/<id>/members/<id>
PATCH  /tournaments/<id>/bracket/<id>/result

### Leaderboard

GET /leaderboard
GET /leaderboard?region=EU

### Agents

GET /agents
GET /agents?role=duelist

---

## Project structure

valtracker/
├── app/
│   ├── routes/
│   │   ├── auth.py
│   │   ├── players.py
│   │   ├── matches.py
│   │   ├── tournaments.py
│   │   └── leaderboard.py
│   ├── init.py
│   ├── models.py
│   ├── extensions.py
│   └── validators.py
├── config.py
├── run.py
├── Dockerfile
├── docker-compose.yml
└── requirements.txt

---

## Notes

Built this to track custom lobby tournament results for Valorant.
First proper Flask project — feedback welcome.
