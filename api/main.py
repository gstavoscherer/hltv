"""
FastAPI backend for HLTV CS2 data.
Exposes SQLite data as a REST API.
"""

import sys
import os

# Ensure project root is on sys.path so src.database imports work
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# Load .env before any module reads os.environ
from dotenv import load_dotenv
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from src.database import session_scope
from src.database.models import (
    Event, Team, Player, EventTeam, TeamPlayer, EventStats,
    Match, MatchMap, MatchPlayerStats, MatchVeto,
)
from sqlalchemy import func

import asyncio
from cartola.api import router as cartola_router
from cartola.bot import start_bot

app = FastAPI(title="HLTV CS2 API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(cartola_router)


@app.on_event("startup")
async def startup_event():
    asyncio.create_task(start_bot())


# ============================================================================
# Helpers
# ============================================================================

def _str_date(d):
    """Convert date/datetime to ISO string or None."""
    return d.isoformat() if d else None


def _team_short(team):
    if not team:
        return None
    return {"id": team.id, "name": team.name, "country": team.country, "world_rank": team.world_rank}


def _player_short(player):
    if not player:
        return None
    return {
        "id": player.id,
        "nickname": player.nickname,
        "real_name": player.real_name,
        "country": player.country,
        "age": player.age,
        "rating_2_0": player.rating_2_0,
        "kd_ratio": player.kd_ratio,
    }


# ============================================================================
# GET /api/stats
# ============================================================================

@app.get("/api/stats")
def get_stats():
    with session_scope() as s:
        return {
            "events": s.query(func.count(Event.id)).scalar(),
            "teams": s.query(func.count(Team.id)).scalar(),
            "players": s.query(func.count(Player.id)).scalar(),
            "matches": s.query(func.count(Match.id)).scalar(),
            "maps": s.query(func.count(MatchMap.id)).scalar(),
            "vetos": s.query(func.count(MatchVeto.id)).scalar(),
            "player_stats": s.query(func.count(MatchPlayerStats.id)).scalar(),
        }


# ============================================================================
# EVENTS
# ============================================================================

@app.get("/api/events")
def list_events():
    with session_scope() as s:
        events = s.query(Event).all()
        result = []
        for e in events:
            team_count = s.query(func.count(EventTeam.id)).filter(EventTeam.event_id == e.id).scalar()
            match_count = s.query(func.count(Match.id)).filter(Match.event_id == e.id).scalar()
            result.append({
                "id": e.id,
                "name": e.name,
                "start_date": _str_date(e.start_date),
                "end_date": _str_date(e.end_date),
                "location": e.location,
                "event_type": e.event_type,
                "prize_pool": e.prize_pool,
                "team_count": team_count,
                "match_count": match_count,
            })
        return result


@app.get("/api/events/{event_id}")
def get_event(event_id: int):
    with session_scope() as s:
        event = s.query(Event).get(event_id)
        if not event:
            raise HTTPException(status_code=404, detail="Event not found")

        teams = []
        for et in event.event_teams:
            teams.append({
                "team": _team_short(et.team),
                "placement": et.placement,
                "prize": et.prize,
            })
        teams.sort(key=lambda t: (t["placement"] or 9999))

        matches = []
        for m in s.query(Match).filter(Match.event_id == event_id).order_by(Match.date.desc().nullslast()).all():
            matches.append({
                "id": m.id,
                "team1": _team_short(m.team1),
                "team2": _team_short(m.team2),
                "score1": m.score1,
                "score2": m.score2,
                "best_of": m.best_of,
                "date": _str_date(m.date),
                "winner": _team_short(m.winner),
                "stars": m.stars,
            })

        return {
            "id": event.id,
            "name": event.name,
            "start_date": _str_date(event.start_date),
            "end_date": _str_date(event.end_date),
            "location": event.location,
            "event_type": event.event_type,
            "prize_pool": event.prize_pool,
            "teams": teams,
            "matches": matches,
        }


# ============================================================================
# TEAMS
# ============================================================================

@app.get("/api/teams")
def list_teams():
    with session_scope() as s:
        teams = s.query(Team).order_by(Team.world_rank.asc().nullslast()).all()
        return [_team_short(t) for t in teams]


@app.get("/api/teams/{team_id}")
def get_team(team_id: int):
    with session_scope() as s:
        team = s.query(Team).get(team_id)
        if not team:
            raise HTTPException(status_code=404, detail="Team not found")

        roster = []
        for tp in team.roster:
            p = tp.player
            roster.append({
                "player": _player_short(p),
                "role": tp.role,
                "is_current": tp.is_current,
                "joined_date": _str_date(tp.joined_date),
                "left_date": _str_date(tp.left_date),
            })

        recent_matches = []
        match_q = (
            s.query(Match)
            .filter((Match.team1_id == team_id) | (Match.team2_id == team_id))
            .order_by(Match.date.desc().nullslast())
            .limit(20)
            .all()
        )
        for m in match_q:
            recent_matches.append({
                "id": m.id,
                "event": {"id": m.event.id, "name": m.event.name} if m.event else None,
                "team1": _team_short(m.team1),
                "team2": _team_short(m.team2),
                "score1": m.score1,
                "score2": m.score2,
                "best_of": m.best_of,
                "date": _str_date(m.date),
                "winner": _team_short(m.winner),
                "stars": m.stars,
            })

        return {
            **_team_short(team),
            "roster": roster,
            "recent_matches": recent_matches,
        }


# ============================================================================
# PLAYERS
# ============================================================================

PLAYER_SORT_FIELDS = {
    "rating_2_0": Player.rating_2_0,
    "kd_ratio": Player.kd_ratio,
    "adr": Player.adr,
    "kpr": Player.kpr,
    "kast": Player.kast,
    "impact": Player.impact,
    "headshot_percentage": Player.headshot_percentage,
    "total_kills": Player.total_kills,
    "total_deaths": Player.total_deaths,
    "total_maps": Player.total_maps,
    "age": Player.age,
    "nickname": Player.nickname,
}


@app.get("/api/players")
def list_players(
    sort_by: str = Query("rating_2_0", description="Field to sort by"),
    order: str = Query("desc", description="asc or desc"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    search: str = Query(None, description="Filter by nickname (case-insensitive)"),
):
    with session_scope() as s:
        q = s.query(Player)

        if search:
            q = q.filter(Player.nickname.ilike(f"%{search}%"))

        sort_col = PLAYER_SORT_FIELDS.get(sort_by, Player.rating_2_0)
        if order == "asc":
            q = q.order_by(sort_col.asc().nullslast())
        else:
            q = q.order_by(sort_col.desc().nullslast())

        total = q.count()
        players = q.offset(offset).limit(limit).all()

        result = []
        for p in players:
            result.append({
                "id": p.id,
                "nickname": p.nickname,
                "real_name": p.real_name,
                "country": p.country,
                "age": p.age,
                "current_team_id": p.current_team_id,
                "rating_2_0": p.rating_2_0,
                "kd_ratio": p.kd_ratio,
                "kpr": p.kpr,
                "kast": p.kast,
                "impact": p.impact,
                "adr": p.adr,
                "headshot_percentage": p.headshot_percentage,
                "total_kills": p.total_kills,
                "total_deaths": p.total_deaths,
                "total_maps": p.total_maps,
                "total_rounds": p.total_rounds,
            })

        return {"total": total, "offset": offset, "limit": limit, "players": result}


@app.get("/api/players/{player_id}")
def get_player(player_id: int):
    with session_scope() as s:
        player = s.query(Player).get(player_id)
        if not player:
            raise HTTPException(status_code=404, detail="Player not found")

        # Per-match stats from match_player_stats
        mps_rows = (
            s.query(MatchPlayerStats)
            .filter(MatchPlayerStats.player_id == player_id)
            .all()
        )
        match_stats = []
        for mps in mps_rows:
            mm = mps.match_map
            match_obj = mm.match if mm else None
            event_obj = match_obj.event if match_obj else None
            match_stats.append({
                "map_id": mps.map_id,
                "map_name": mm.map_name if mm else None,
                "match_id": mm.match_id if mm else None,
                "event_id": match_obj.event_id if match_obj else None,
                "event_name": event_obj.name if event_obj else None,
                "team_id": mps.team_id,
                "kills": mps.kills,
                "deaths": mps.deaths,
                "assists": mps.assists,
                "headshots": mps.headshots,
                "flash_assists": mps.flash_assists,
                "adr": mps.adr,
                "kast": mps.kast,
                "rating": mps.rating,
                "opening_kills": mps.opening_kills,
                "opening_deaths": mps.opening_deaths,
                "multi_kill_rounds": mps.multi_kill_rounds,
                "clutches_won": mps.clutches_won,
            })

        return {
            "id": player.id,
            "nickname": player.nickname,
            "real_name": player.real_name,
            "country": player.country,
            "age": player.age,
            "current_team_id": player.current_team_id,
            "current_team": _team_short(player.current_team) if player.current_team else None,
            "rating_2_0": player.rating_2_0,
            "kd_ratio": player.kd_ratio,
            "kpr": player.kpr,
            "kast": player.kast,
            "impact": player.impact,
            "adr": player.adr,
            "headshot_percentage": player.headshot_percentage,
            "total_kills": player.total_kills,
            "total_deaths": player.total_deaths,
            "total_maps": player.total_maps,
            "total_rounds": player.total_rounds,
            "match_stats": match_stats,
        }


# ============================================================================
# MATCHES
# ============================================================================

@app.get("/api/matches")
def list_matches(
    event_id: int = Query(None, description="Filter by event ID"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    with session_scope() as s:
        q = s.query(Match)
        if event_id is not None:
            q = q.filter(Match.event_id == event_id)

        q = q.order_by(Match.date.desc().nullslast())
        total = q.count()
        matches = q.offset(offset).limit(limit).all()

        result = []
        for m in matches:
            result.append({
                "id": m.id,
                "event": {"id": m.event.id, "name": m.event.name} if m.event else None,
                "team1": _team_short(m.team1),
                "team2": _team_short(m.team2),
                "score1": m.score1,
                "score2": m.score2,
                "best_of": m.best_of,
                "date": _str_date(m.date),
                "winner": _team_short(m.winner),
                "stars": m.stars,
            })

        return {"total": total, "offset": offset, "limit": limit, "matches": result}


@app.get("/api/matches/{match_id}")
def get_match(match_id: int):
    with session_scope() as s:
        match = s.query(Match).get(match_id)
        if not match:
            raise HTTPException(status_code=404, detail="Match not found")

        maps = []
        for mm in sorted(match.maps, key=lambda m: m.map_number):
            player_stats = []
            for ps in mm.player_stats:
                player_stats.append({
                    "player": _player_short(ps.player),
                    "team": _team_short(ps.team),
                    "kills": ps.kills,
                    "deaths": ps.deaths,
                    "assists": ps.assists,
                    "headshots": ps.headshots,
                    "flash_assists": ps.flash_assists,
                    "adr": ps.adr,
                    "kast": ps.kast,
                    "rating": ps.rating,
                    "opening_kills": ps.opening_kills,
                    "opening_deaths": ps.opening_deaths,
                    "multi_kill_rounds": ps.multi_kill_rounds,
                    "clutches_won": ps.clutches_won,
                })

            maps.append({
                "id": mm.id,
                "map_name": mm.map_name,
                "map_number": mm.map_number,
                "team1_score": mm.team1_score,
                "team2_score": mm.team2_score,
                "team1_ct_score": mm.team1_ct_score,
                "team1_t_score": mm.team1_t_score,
                "team2_ct_score": mm.team2_ct_score,
                "team2_t_score": mm.team2_t_score,
                "picked_by": _team_short(mm.picker),
                "winner": _team_short(mm.winner),
                "player_stats": player_stats,
            })

        vetos = []
        for v in sorted(match.vetos, key=lambda v: v.veto_number):
            vetos.append({
                "veto_number": v.veto_number,
                "team": _team_short(v.team),
                "action": v.action,
                "map_name": v.map_name,
            })

        return {
            "id": match.id,
            "event": {"id": match.event.id, "name": match.event.name} if match.event else None,
            "team1": _team_short(match.team1),
            "team2": _team_short(match.team2),
            "score1": match.score1,
            "score2": match.score2,
            "best_of": match.best_of,
            "date": _str_date(match.date),
            "winner": _team_short(match.winner),
            "stars": match.stars,
            "maps": maps,
            "vetos": vetos,
        }
