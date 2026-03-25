"""Tests for database models and relationships."""

import pytest
from datetime import date
from sqlalchemy.exc import IntegrityError

from src.database.models import Event, Team, Player, EventTeam, TeamPlayer, EventStats


class TestEventModel:
    def test_create_event(self, db_session):
        event = Event(id=1, name="PGL Major", start_date=date(2024, 3, 17), end_date=date(2024, 3, 31))
        db_session.add(event)
        db_session.commit()

        result = db_session.query(Event).filter_by(id=1).first()
        assert result is not None
        assert result.name == "PGL Major"
        assert result.start_date == date(2024, 3, 17)

    def test_event_requires_name(self, db_session):
        event = Event(id=2, name=None)
        db_session.add(event)
        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_event_repr(self):
        event = Event(id=1, name="Test Event")
        assert "id=1" in repr(event)
        assert "Test Event" in repr(event)


class TestTeamModel:
    def test_create_team(self, db_session):
        team = Team(id=100, name="Natus Vincere", country="Ukraine", world_rank=1)
        db_session.add(team)
        db_session.commit()

        result = db_session.query(Team).filter_by(id=100).first()
        assert result.name == "Natus Vincere"
        assert result.country == "Ukraine"
        assert result.world_rank == 1

    def test_team_requires_name(self, db_session):
        team = Team(id=101, name=None)
        db_session.add(team)
        with pytest.raises(IntegrityError):
            db_session.commit()


class TestPlayerModel:
    def test_create_player(self, db_session):
        team = Team(id=100, name="Natus Vincere")
        db_session.add(team)
        db_session.commit()

        player = Player(
            id=7998, nickname="s1mple", real_name="Oleksandr Kostyliev",
            country="Ukraine", age=26, current_team_id=100,
            rating_2_0=1.28, kd_ratio=1.35, adr=85.2
        )
        db_session.add(player)
        db_session.commit()

        result = db_session.query(Player).filter_by(id=7998).first()
        assert result.nickname == "s1mple"
        assert result.current_team_id == 100
        assert result.rating_2_0 == 1.28
        assert result.kd_ratio == 1.35

    def test_player_without_team(self, db_session):
        player = Player(id=1, nickname="TestPlayer")
        db_session.add(player)
        db_session.commit()

        result = db_session.query(Player).filter_by(id=1).first()
        assert result.current_team_id is None


class TestEventTeamModel:
    def test_create_event_team(self, db_session):
        event = Event(id=1, name="Major")
        team = Team(id=100, name="NAVI")
        db_session.add_all([event, team])
        db_session.commit()

        et = EventTeam(event_id=1, team_id=100, placement=1, prize="$500,000")
        db_session.add(et)
        db_session.commit()

        result = db_session.query(EventTeam).first()
        assert result.event_id == 1
        assert result.team_id == 100
        assert result.placement == 1
        assert result.prize == "$500,000"

    def test_unique_constraint(self, db_session):
        event = Event(id=1, name="Major")
        team = Team(id=100, name="NAVI")
        db_session.add_all([event, team])
        db_session.commit()

        et1 = EventTeam(event_id=1, team_id=100)
        db_session.add(et1)
        db_session.commit()

        et2 = EventTeam(event_id=1, team_id=100)
        db_session.add(et2)
        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_event_relationship(self, db_session):
        event = Event(id=1, name="Major")
        team = Team(id=100, name="NAVI")
        db_session.add_all([event, team])
        db_session.commit()

        et = EventTeam(event_id=1, team_id=100)
        db_session.add(et)
        db_session.commit()

        result = db_session.query(Event).filter_by(id=1).first()
        assert len(result.event_teams) == 1
        assert result.event_teams[0].team_id == 100


class TestTeamPlayerModel:
    def test_create_team_player(self, db_session):
        team = Team(id=100, name="NAVI")
        player = Player(id=7998, nickname="s1mple")
        db_session.add_all([team, player])
        db_session.commit()

        tp = TeamPlayer(team_id=100, player_id=7998, role="player", is_current=True)
        db_session.add(tp)
        db_session.commit()

        result = db_session.query(TeamPlayer).first()
        assert result.team_id == 100
        assert result.player_id == 7998
        assert result.is_current is True

    def test_unique_constraint(self, db_session):
        team = Team(id=100, name="NAVI")
        player = Player(id=7998, nickname="s1mple")
        db_session.add_all([team, player])
        db_session.commit()

        tp1 = TeamPlayer(team_id=100, player_id=7998)
        db_session.add(tp1)
        db_session.commit()

        tp2 = TeamPlayer(team_id=100, player_id=7998)
        db_session.add(tp2)
        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_roster_relationship(self, db_session):
        team = Team(id=100, name="NAVI")
        player = Player(id=7998, nickname="s1mple")
        db_session.add_all([team, player])
        db_session.commit()

        tp = TeamPlayer(team_id=100, player_id=7998, is_current=True)
        db_session.add(tp)
        db_session.commit()

        result = db_session.query(Team).filter_by(id=100).first()
        assert len(result.roster) == 1
        assert result.roster[0].player_id == 7998


class TestEventStatsModel:
    def test_create_event_stats(self, db_session):
        event = Event(id=1, name="Major")
        player = Player(id=7998, nickname="s1mple")
        db_session.add_all([event, player])
        db_session.commit()

        stats = EventStats(event_id=1, player_id=7998, rating=1.35, maps_played=12, kd_ratio=1.45)
        db_session.add(stats)
        db_session.commit()

        result = db_session.query(EventStats).first()
        assert result.rating == 1.35
        assert result.maps_played == 12

    def test_unique_constraint(self, db_session):
        event = Event(id=1, name="Major")
        player = Player(id=7998, nickname="s1mple")
        db_session.add_all([event, player])
        db_session.commit()

        s1 = EventStats(event_id=1, player_id=7998, rating=1.35)
        db_session.add(s1)
        db_session.commit()

        s2 = EventStats(event_id=1, player_id=7998, rating=1.40)
        db_session.add(s2)
        with pytest.raises(IntegrityError):
            db_session.commit()
