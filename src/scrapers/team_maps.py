"""Calculate team map stats from existing match data in the database."""

import logging
from collections import defaultdict

from sqlalchemy.orm import Session

from src.database import session_scope
from src.database.models import Team, Match, MatchMap, TeamMapStats

logger = logging.getLogger(__name__)


def calculate_team_map_stats(team_id, session: Session):
    """Calculate map stats for a team from MatchMap + Match data.

    Queries all maps where the team played (as team1 or team2),
    aggregates wins, rounds won/lost, and CT/T side data when available.
    Upserts results into TeamMapStats.

    Returns dict of {map_name: {times_played, wins, win_rate}}.
    """
    # Get all matches where this team played
    matches = (
        session.query(Match)
        .filter((Match.team1_id == team_id) | (Match.team2_id == team_id))
        .all()
    )

    if not matches:
        logger.info("Time %d: nenhum match encontrado", team_id)
        return {}

    match_ids = [m.id for m in matches]
    # Build lookup: match_id -> Match
    match_lookup = {m.id: m for m in matches}

    # Get all maps from those matches
    maps = (
        session.query(MatchMap)
        .filter(MatchMap.match_id.in_(match_ids))
        .all()
    )

    if not maps:
        logger.info("Time %d: nenhum map encontrado", team_id)
        return {}

    # Aggregate stats per map_name
    stats = defaultdict(lambda: {
        "times_played": 0,
        "wins": 0,
        "ct_wins": 0,
        "ct_rounds_won": 0,
        "ct_rounds_played": 0,
        "t_wins": 0,
        "t_rounds_won": 0,
        "t_rounds_played": 0,
    })

    for mm in maps:
        match = match_lookup.get(mm.match_id)
        if not match:
            continue

        map_name = mm.map_name
        if not map_name:
            continue

        s = stats[map_name]
        s["times_played"] += 1

        is_team1 = match.team1_id == team_id

        # Determine if team won this map
        if mm.winner_id is not None:
            if mm.winner_id == team_id:
                s["wins"] += 1
        elif mm.team1_score is not None and mm.team2_score is not None:
            # Fallback: higher score wins
            team_score = mm.team1_score if is_team1 else mm.team2_score
            opp_score = mm.team2_score if is_team1 else mm.team1_score
            if team_score > opp_score:
                s["wins"] += 1

        # CT/T side stats (when available)
        if is_team1:
            ct_won = mm.team1_ct_score
            t_won = mm.team1_t_score
            opp_ct = mm.team2_ct_score
            opp_t = mm.team2_t_score
        else:
            ct_won = mm.team2_ct_score
            t_won = mm.team2_t_score
            opp_ct = mm.team1_ct_score
            opp_t = mm.team1_t_score

        if ct_won is not None and opp_t is not None:
            ct_rounds = ct_won + opp_t  # CT rounds played = team CT rounds + opponent T rounds (same half)
            s["ct_rounds_won"] += ct_won
            s["ct_rounds_played"] += ct_rounds

        if t_won is not None and opp_ct is not None:
            t_rounds = t_won + opp_ct
            s["t_rounds_won"] += t_won
            s["t_rounds_played"] += t_rounds

    # Upsert into TeamMapStats
    result = {}
    for map_name, data in stats.items():
        existing = (
            session.query(TeamMapStats)
            .filter_by(team_id=team_id, map_name=map_name)
            .first()
        )

        win_rate = round(data["wins"] / data["times_played"] * 100, 1) if data["times_played"] > 0 else 0.0

        if existing:
            existing.times_played = data["times_played"]
            existing.wins = data["wins"]
            existing.ct_wins = data["ct_wins"]
            existing.ct_rounds_won = data["ct_rounds_won"]
            existing.ct_rounds_played = data["ct_rounds_played"]
            existing.t_wins = data["t_wins"]
            existing.t_rounds_won = data["t_rounds_won"]
            existing.t_rounds_played = data["t_rounds_played"]
        else:
            new_stat = TeamMapStats(
                team_id=team_id,
                map_name=map_name,
                times_played=data["times_played"],
                wins=data["wins"],
                ct_wins=data["ct_wins"],
                ct_rounds_won=data["ct_rounds_won"],
                ct_rounds_played=data["ct_rounds_played"],
                t_wins=data["t_wins"],
                t_rounds_won=data["t_rounds_won"],
                t_rounds_played=data["t_rounds_played"],
            )
            session.add(new_stat)

        result[map_name] = {
            "times_played": data["times_played"],
            "wins": data["wins"],
            "win_rate": win_rate,
        }

    return result


def update_all_team_map_stats():
    """Calculate map stats for all teams in the database."""
    with session_scope() as session:
        teams = session.query(Team).all()
        total = len(teams)
        print(f"Calculando map stats para {total} times...")

        updated = 0
        for idx, team in enumerate(teams, 1):
            result = calculate_team_map_stats(team.id, session)
            if result:
                updated += 1
                maps_str = ", ".join(
                    f"{m} ({d['wins']}/{d['times_played']} = {d['win_rate']}%)"
                    for m, d in sorted(result.items())
                )
                print(f"  [{idx}/{total}] {team.name}: {maps_str}")
            else:
                print(f"  [{idx}/{total}] {team.name}: sem dados de maps")

        print(f"\nFinalizado - {updated}/{total} times com map stats atualizados")


if __name__ == "__main__":
    update_all_team_map_stats()
