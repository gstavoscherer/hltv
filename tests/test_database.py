"""Tests for database initialization and session management."""

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

from src.database.models import Base, Event, Team, Player


class TestDatabaseInit:
    def test_all_tables_created(self, db_session):
        engine = db_session.get_bind()
        inspector = inspect(engine)
        table_names = inspector.get_table_names()

        expected = ['events', 'teams', 'players', 'event_stats', 'event_teams', 'team_players']
        for table in expected:
            assert table in table_names, f"Missing table: {table}"

    def test_create_all_is_idempotent(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=engine)
        Base.metadata.create_all(bind=engine)  # Should not raise

        inspector = inspect(engine)
        assert 'events' in inspector.get_table_names()


class TestSessionScope:
    def test_session_scope_commits_on_success(self):
        from src.database.models import Base, Event

        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=engine)

        from unittest.mock import patch
        from src.database import session_scope

        with patch('src.database.SessionLocal', sessionmaker(bind=engine)):
            with session_scope() as session:
                session.add(Event(id=1, name="Test"))

        Session = sessionmaker(bind=engine)
        verify = Session()
        assert verify.query(Event).count() == 1
        verify.close()

    def test_session_scope_rolls_back_on_error(self):
        from src.database.models import Base, Event

        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=engine)

        from unittest.mock import patch
        from src.database import session_scope

        with patch('src.database.SessionLocal', sessionmaker(bind=engine)):
            with pytest.raises(ValueError):
                with session_scope() as session:
                    session.add(Event(id=1, name="Test"))
                    raise ValueError("Something went wrong")

        Session = sessionmaker(bind=engine)
        verify = Session()
        assert verify.query(Event).count() == 0
        verify.close()


class TestUpsertPattern:
    def test_upsert_event(self, db_session):
        event = Event(id=1, name="Original Name")
        db_session.add(event)
        db_session.commit()

        existing = db_session.query(Event).filter_by(id=1).first()
        existing.name = "Updated Name"
        db_session.commit()

        result = db_session.query(Event).filter_by(id=1).first()
        assert result.name == "Updated Name"
        assert db_session.query(Event).count() == 1

    def test_upsert_player_stats(self, db_session):
        team = Team(id=100, name="NAVI")
        player = Player(id=7998, nickname="s1mple", current_team_id=100, rating_2_0=1.20)
        db_session.add_all([team, player])
        db_session.commit()

        existing = db_session.query(Player).filter_by(id=7998).first()
        existing.rating_2_0 = 1.28
        existing.kd_ratio = 1.35
        db_session.commit()

        result = db_session.query(Player).filter_by(id=7998).first()
        assert result.rating_2_0 == 1.28
        assert result.kd_ratio == 1.35
