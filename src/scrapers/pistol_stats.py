"""Pistol round stats aggregation from MatchMap data."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sqlalchemy import or_

from src.database import session_scope
from src.database.models import Match, MatchMap, Team


def get_team_pistol_stats(team_id, session):
    """Returns pistol round stats for a team from MatchMap data.

    Only counts maps where pistol data exists (at least one team has pistol_wins > 0,
    indicating the data was actually scraped).

    Returns dict: {total_pistols, wins, win_rate, maps_with_data}
    """
    # Get all maps where this team played (as team1 or team2)
    maps_as_team1 = (
        session.query(MatchMap, Match)
        .join(Match, MatchMap.match_id == Match.id)
        .filter(Match.team1_id == team_id)
        .filter(
            or_(
                MatchMap.team1_pistol_wins > 0,
                MatchMap.team2_pistol_wins > 0,
            )
        )
        .all()
    )

    maps_as_team2 = (
        session.query(MatchMap, Match)
        .join(Match, MatchMap.match_id == Match.id)
        .filter(Match.team2_id == team_id)
        .filter(
            or_(
                MatchMap.team1_pistol_wins > 0,
                MatchMap.team2_pistol_wins > 0,
            )
        )
        .all()
    )

    total_pistols = 0
    wins = 0
    maps_with_data = 0

    for match_map, match in maps_as_team1:
        pistol_rounds_in_map = (match_map.team1_pistol_wins or 0) + (match_map.team2_pistol_wins or 0)
        total_pistols += pistol_rounds_in_map
        wins += (match_map.team1_pistol_wins or 0)
        maps_with_data += 1

    for match_map, match in maps_as_team2:
        pistol_rounds_in_map = (match_map.team1_pistol_wins or 0) + (match_map.team2_pistol_wins or 0)
        total_pistols += pistol_rounds_in_map
        wins += (match_map.team2_pistol_wins or 0)
        maps_with_data += 1

    win_rate = round(wins / total_pistols * 100, 1) if total_pistols > 0 else 0.0

    return {
        "total_pistols": total_pistols,
        "wins": wins,
        "win_rate": win_rate,
        "maps_with_data": maps_with_data,
    }


def get_all_pistol_stats():
    """Print pistol round stats summary for all teams that have data."""
    with session_scope() as s:
        teams = s.query(Team).order_by(Team.name).all()

        print(f"{'Team':<25} {'Maps':>5} {'Pistols':>8} {'Wins':>5} {'Win%':>6}")
        print("-" * 55)

        teams_with_data = 0
        for team in teams:
            stats = get_team_pistol_stats(team.id, s)
            if stats["maps_with_data"] == 0:
                continue
            teams_with_data += 1
            print(
                f"{team.name:<25} {stats['maps_with_data']:>5} "
                f"{stats['total_pistols']:>8} {stats['wins']:>5} "
                f"{stats['win_rate']:>5.1f}%"
            )

        if teams_with_data == 0:
            print("\nNenhum time com dados de pistol round ainda.")
            print("Os dados serao populados nos proximos syncs de matches.")
        else:
            print(f"\n{teams_with_data} times com dados de pistol round.")


if __name__ == '__main__':
    get_all_pistol_stats()
