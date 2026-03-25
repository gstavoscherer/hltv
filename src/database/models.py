"""
Database models for HLTV data storage.

Schema:
- Events: Tournament/event information
- Teams: Team profiles
- Players: Player profiles and career stats
- EventStats: Player statistics per event
- EventTeam: Event-Team relationship (placement, prize)
- TeamPlayer: Team roster history
"""

from sqlalchemy import (
    Column, Integer, String, DateTime, Boolean, Float,
    ForeignKey, Date, UniqueConstraint, func
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


# ============================================================================
# CORE ENTITIES
# ============================================================================

class Event(Base):
    __tablename__ = 'events'

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)

    start_date = Column(Date)
    end_date = Column(Date)

    location = Column(String(255))
    event_type = Column(String(50))
    prize_pool = Column(String(100))

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    event_teams = relationship("EventTeam", back_populates="event", cascade="all, delete-orphan")
    event_stats = relationship("EventStats", back_populates="event", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Event(id={self.id}, name='{self.name}')>"


class Team(Base):
    __tablename__ = 'teams'

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    country = Column(String(100))
    world_rank = Column(Integer)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    event_teams = relationship("EventTeam", back_populates="team")
    roster = relationship("TeamPlayer", back_populates="team", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Team(id={self.id}, name='{self.name}')>"


class Player(Base):
    __tablename__ = 'players'

    id = Column(Integer, primary_key=True)
    nickname = Column(String(100), nullable=False)
    real_name = Column(String(255))
    country = Column(String(100))
    age = Column(Integer)

    current_team_id = Column(Integer, ForeignKey('teams.id'), nullable=True)

    total_maps = Column(Integer)
    total_rounds = Column(Integer)
    total_kills = Column(Integer)
    total_deaths = Column(Integer)
    kd_ratio = Column(Float)
    headshot_percentage = Column(Float)

    rating_2_0 = Column(Float)
    kpr = Column(Float)
    kast = Column(Float)
    impact = Column(Float)
    adr = Column(Float)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    event_stats = relationship("EventStats", back_populates="player")
    current_team = relationship("Team", foreign_keys=[current_team_id])
    team_history = relationship("TeamPlayer", back_populates="player", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Player(id={self.id}, nickname='{self.nickname}')>"


# ============================================================================
# STATISTICS & RELATIONSHIPS
# ============================================================================

class EventStats(Base):
    __tablename__ = 'event_stats'

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(Integer, ForeignKey('events.id'), nullable=False)
    player_id = Column(Integer, ForeignKey('players.id'), nullable=False)

    rating = Column(Float)
    maps_played = Column(Integer)
    kd_ratio = Column(Float)

    created_at = Column(DateTime, server_default=func.now())

    event = relationship("Event", back_populates="event_stats")
    player = relationship("Player", back_populates="event_stats")

    __table_args__ = (
        UniqueConstraint('event_id', 'player_id', name='uq_event_player_stats'),
    )

    def __repr__(self):
        return f"<EventStats(event_id={self.event_id}, player_id={self.player_id})>"


class EventTeam(Base):
    __tablename__ = 'event_teams'

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(Integer, ForeignKey('events.id'), nullable=False)
    team_id = Column(Integer, ForeignKey('teams.id'), nullable=False)

    placement = Column(Integer)
    prize = Column(String(100))

    created_at = Column(DateTime, server_default=func.now())

    event = relationship("Event", back_populates="event_teams")
    team = relationship("Team", back_populates="event_teams")

    __table_args__ = (
        UniqueConstraint('event_id', 'team_id', name='uq_event_team'),
    )

    def __repr__(self):
        return f"<EventTeam(event_id={self.event_id}, team_id={self.team_id})>"


class TeamPlayer(Base):
    __tablename__ = 'team_players'

    id = Column(Integer, primary_key=True, autoincrement=True)
    team_id = Column(Integer, ForeignKey('teams.id'), nullable=False)
    player_id = Column(Integer, ForeignKey('players.id'), nullable=False)

    role = Column(String(50))
    is_current = Column(Boolean, default=True)

    joined_date = Column(Date, nullable=True)
    left_date = Column(Date, nullable=True)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    team = relationship("Team", back_populates="roster")
    player = relationship("Player", back_populates="team_history")

    __table_args__ = (
        UniqueConstraint('team_id', 'player_id', name='uq_team_player'),
    )

    def __repr__(self):
        return f"<TeamPlayer(team_id={self.team_id}, player_id={self.player_id})>"
