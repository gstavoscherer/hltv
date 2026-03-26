"""
Analytics queries for CartolaCS — H2H and roster stability.
Zero-effort features: no new scraping, just SQL queries.
"""

from datetime import date, timedelta

from sqlalchemy import or_, and_

from src.database.models import Match, MatchMap, TeamPlayer, TeamRankingHistory


def get_h2h(team1_id, team2_id, session):
    """Returns H2H stats between two teams from match data.

    Returns dict with: total_matches, team1_wins, team2_wins,
    team1_map_wins, team2_map_wins, maps_played,
    team1_round_wins, team2_round_wins, last_match_date
    """
    # Find all matches between these two teams (in either order)
    matches = (
        session.query(Match)
        .filter(
            or_(
                and_(Match.team1_id == team1_id, Match.team2_id == team2_id),
                and_(Match.team1_id == team2_id, Match.team2_id == team1_id),
            )
        )
        .order_by(Match.date.desc())
        .all()
    )

    total_matches = len(matches)
    team1_wins = 0
    team2_wins = 0
    last_match_date = None

    if matches and matches[0].date:
        last_match_date = matches[0].date.isoformat()

    for m in matches:
        if m.winner_id == team1_id:
            team1_wins += 1
        elif m.winner_id == team2_id:
            team2_wins += 1

    # Map-level stats
    match_ids = [m.id for m in matches]
    team1_map_wins = 0
    team2_map_wins = 0
    maps_played = 0
    team1_round_wins = 0
    team2_round_wins = 0

    if match_ids:
        map_rows = (
            session.query(MatchMap)
            .filter(MatchMap.match_id.in_(match_ids))
            .all()
        )
        maps_played = len(map_rows)

        for mm in map_rows:
            # Find parent match to know team orientation
            parent = next(m for m in matches if m.id == mm.match_id)

            if parent.team1_id == team1_id:
                # team1 is match.team1, team2 is match.team2
                t1_score = mm.team1_score or 0
                t2_score = mm.team2_score or 0
            else:
                # team1 is match.team2, team2 is match.team1
                t1_score = mm.team2_score or 0
                t2_score = mm.team1_score or 0

            team1_round_wins += t1_score
            team2_round_wins += t2_score

            if mm.winner_id == team1_id:
                team1_map_wins += 1
            elif mm.winner_id == team2_id:
                team2_map_wins += 1

    return {
        "total_matches": total_matches,
        "team1_wins": team1_wins,
        "team2_wins": team2_wins,
        "team1_map_wins": team1_map_wins,
        "team2_map_wins": team2_map_wins,
        "maps_played": maps_played,
        "team1_round_wins": team1_round_wins,
        "team2_round_wins": team2_round_wins,
        "last_match_date": last_match_date,
    }


def get_roster_stability(team_id, session):
    """Returns roster stability metrics.

    Returns dict with: current_roster_size, avg_days_together,
    oldest_member_days, newest_member_days, changes_last_6_months
    """
    today = date.today()

    # Current roster members
    current_members = (
        session.query(TeamPlayer)
        .filter(TeamPlayer.team_id == team_id, TeamPlayer.is_current == True)
        .all()
    )

    current_roster_size = len(current_members)
    days_list = []

    for member in current_members:
        if member.joined_date:
            days = (today - member.joined_date).days
            days_list.append(days)

    avg_days_together = round(sum(days_list) / len(days_list), 1) if days_list else None
    oldest_member_days = max(days_list) if days_list else None
    newest_member_days = min(days_list) if days_list else None

    # Roster changes in last 6 months (players who joined or left)
    six_months_ago = today - timedelta(days=180)

    joined_recently = (
        session.query(TeamPlayer)
        .filter(
            TeamPlayer.team_id == team_id,
            TeamPlayer.joined_date >= six_months_ago,
        )
        .count()
    )

    left_recently = (
        session.query(TeamPlayer)
        .filter(
            TeamPlayer.team_id == team_id,
            TeamPlayer.is_current == False,
            TeamPlayer.left_date >= six_months_ago,
        )
        .count()
    )

    changes_last_6_months = joined_recently + left_recently

    return {
        "current_roster_size": current_roster_size,
        "avg_days_together": avg_days_together,
        "oldest_member_days": oldest_member_days,
        "newest_member_days": newest_member_days,
        "changes_last_6_months": changes_last_6_months,
    }


def get_ranking_trend(team_id, session, weeks=8):
    """Returns ranking history for a team over last N weeks.

    Returns list of {'date': date, 'rank': int, 'points': int}
    ordered by date ascending.
    Also returns trend: 'rising', 'falling', or 'stable'
    based on comparing first half avg vs second half avg rank.
    """
    cutoff = date.today() - timedelta(weeks=weeks)

    history = (
        session.query(TeamRankingHistory)
        .filter(
            TeamRankingHistory.team_id == team_id,
            TeamRankingHistory.date >= cutoff,
        )
        .order_by(TeamRankingHistory.date.asc())
        .all()
    )

    entries = [
        {
            "date": h.date.isoformat(),
            "rank": h.rank,
            "points": h.points,
        }
        for h in history
    ]

    # Determine trend by comparing first half avg rank vs second half avg rank
    trend = "stable"
    if len(entries) >= 2:
        mid = len(entries) // 2
        first_half_avg = sum(e["rank"] for e in entries[:mid]) / mid
        second_half_avg = sum(e["rank"] for e in entries[mid:]) / (len(entries) - mid)
        # Lower rank number = better position, so if second half avg is lower, team is rising
        diff = first_half_avg - second_half_avg
        if diff >= 1:
            trend = "rising"
        elif diff <= -1:
            trend = "falling"

    return {
        "history": entries,
        "trend": trend,
    }
