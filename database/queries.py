"""
Example queries for HLTV database.
Useful for data analysis and reporting.
"""

from database import get_db_session
from database.models import Event, Team, Player, Match, EventStats
from sqlalchemy import func, desc


def top_players_by_rating(limit=10):
    """Get top players by average rating across all events"""
    with get_db_session() as session:
        results = session.query(
            Player.nickname,
            func.avg(EventStats.rating).label('avg_rating'),
            func.count(EventStats.id).label('events_played')
        ).join(
            EventStats, Player.id == EventStats.player_id
        ).filter(
            EventStats.rating.isnot(None)
        ).group_by(
            Player.id
        ).order_by(
            desc('avg_rating')
        ).limit(limit).all()

        return results


def team_performance(team_name=None):
    """Get team's match statistics"""
    with get_db_session() as session:
        query = session.query(
            Team.name,
            func.count(Match.id).label('matches_played'),
            func.sum(
                func.case((Match.winner_id == Team.id, 1), else_=0)
            ).label('matches_won')
        ).outerjoin(
            Match, (Match.team1_id == Team.id) | (Match.team2_id == Team.id)
        ).group_by(
            Team.id
        )

        if team_name:
            query = query.filter(Team.name.like(f'%{team_name}%'))

        results = query.all()
        return results


def event_summary():
    """Get summary of all events"""
    with get_db_session() as session:
        results = session.query(
            Event.name,
            Event.location,
            Event.prize_pool,
            Event.num_teams,
            func.count(Match.id).label('num_matches')
        ).outerjoin(
            Match, Event.id == Match.event_id
        ).group_by(
            Event.id
        ).all()

        return results


def matches_by_team(team_id):
    """Get all matches for a specific team"""
    with get_db_session() as session:
        matches = session.query(Match).filter(
            (Match.team1_id == team_id) | (Match.team2_id == team_id)
        ).all()

        return matches


def player_event_history(player_id):
    """Get player's performance across events"""
    with get_db_session() as session:
        results = session.query(
            Event.name,
            EventStats.rating,
            EventStats.maps_played,
            EventStats.rank
        ).join(
            EventStats, Event.id == EventStats.event_id
        ).filter(
            EventStats.player_id == player_id
        ).order_by(
            Event.start_date.desc()
        ).all()

        return results


if __name__ == "__main__":
    # Example usage
    print("\n🏆 Top 10 Players by Rating:")
    print("="*60)
    for player, rating, events in top_players_by_rating(10):
        print(f"{player:20} | Rating: {rating:.2f} | Events: {events}")

    print("\n\n📊 Event Summary:")
    print("="*60)
    for event in event_summary():
        print(f"{event.name:40} | {event.location:20} | Matches: {event.num_matches}")

    print("\n\n👥 Team Performance:")
    print("="*60)
    for team, played, won in team_performance():
        if played > 0:
            win_rate = (won / played) * 100
            print(f"{team:30} | Played: {played:3} | Won: {won:3} | Win Rate: {win_rate:.1f}%")
