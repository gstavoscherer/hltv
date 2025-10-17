"""
Database models for HLTV data storage.

Schema design:
- Events: Main tournament/event information
- Teams: Team profiles (referenced by multiple events/matches)
- Players: Player profiles
- Matches: Individual match data
- MatchMaps: Map-by-map results for each match
- EventStats: Top player/team stats per event
- Brackets: Tournament bracket structure (JSON)
"""

from sqlalchemy import (
    Column, Integer, String, DateTime, Boolean, Float,
    ForeignKey, Text, JSON, Date, Enum as SQLEnum, UniqueConstraint
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

Base = declarative_base()


class EventType(enum.Enum):
    """Event type enum"""
    LAN = "LAN"
    ONLINE = "Online"
    MIXED = "Mixed"


class EventStatus(enum.Enum):
    """Event status enum"""
    UPCOMING = "upcoming"
    ONGOING = "ongoing"
    FINISHED = "finished"
    CANCELLED = "cancelled"


# ============================================================================
# CORE ENTITIES
# ============================================================================

class Event(Base):
    """Tournament/Event entity - CLEAN VERSION"""
    __tablename__ = 'events'

    # Basic info
    id = Column(Integer, primary_key=True)  # HLTV event ID
    name = Column(String(255), nullable=False)

    # Dates
    start_date = Column(Date)
    end_date = Column(Date)

    # Location & Type
    location = Column(String(255))
    event_type = Column(String(50))  # 'LAN', 'Online', etc.
    prize_pool = Column(String(100))

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    event_teams = relationship("EventTeam", back_populates="event", cascade="all, delete-orphan")
    event_stats = relationship("EventStats", back_populates="event", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Event(id={self.id}, name='{self.name}')>"


class Team(Base):
    """Team entity - CLEAN VERSION"""
    __tablename__ = 'teams'

    # Basic info
    id = Column(Integer, primary_key=True)  # HLTV team ID
    name = Column(String(255), nullable=False)
    country = Column(String(100))
    world_rank = Column(Integer)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    event_teams = relationship("EventTeam", back_populates="team")
    roster = relationship("TeamPlayer", back_populates="team", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Team(id={self.id}, name='{self.name}')>"


class Player(Base):
    """Player entity - CLEAN VERSION"""
    __tablename__ = 'players'

    # Basic info
    id = Column(Integer, primary_key=True)  # HLTV player ID
    nickname = Column(String(100), nullable=False)
    real_name = Column(String(255))
    country = Column(String(100))
    age = Column(Integer)

    # Current team
    current_team_id = Column(Integer, ForeignKey('teams.id'), nullable=True)

    # Career stats - Basic
    total_maps = Column(Integer)
    total_rounds = Column(Integer)
    total_kills = Column(Integer)
    total_deaths = Column(Integer)
    kd_ratio = Column(Float)
    headshot_percentage = Column(Float)

    # Career stats - Rating & Performance
    rating_2_0 = Column(Float)
    kpr = Column(Float)  # Kills per round
    apr = Column(Float)  # Assists per round
    kast = Column(Float)  # KAST %
    impact = Column(Float)
    adr = Column(Float)  # Average damage per round

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    event_stats = relationship("EventStats", back_populates="player")
    current_team = relationship("Team", foreign_keys=[current_team_id])
    team_history = relationship("TeamPlayer", back_populates="player", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Player(id={self.id}, nickname='{self.nickname}')>"
# ============================================================================
# MATCH DATA
# ============================================================================

# ============================================================================
# STATISTICS & RELATIONSHIPS
# ============================================================================

class EventStats(Base):
    """Player statistics for a specific event - CLEAN VERSION"""
    __tablename__ = 'event_stats'

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(Integer, ForeignKey('events.id'), nullable=False)
    player_id = Column(Integer, ForeignKey('players.id'), nullable=False)

    # Core stats
    rating = Column(Float)
    maps_played = Column(Integer)
    kd_ratio = Column(Float)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    event = relationship("Event", back_populates="event_stats")
    player = relationship("Player", back_populates="event_stats")

    __table_args__ = (
        UniqueConstraint('event_id', 'player_id', name='uq_event_player_stats'),
    )

    def __repr__(self):
        return f"<EventStats(event_id={self.event_id}, player_id={self.player_id})>"



class EventTeam(Base):
    """Many-to-many relationship between Events and Teams"""
    __tablename__ = 'event_teams'

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(Integer, ForeignKey('events.id'), nullable=False)
    team_id = Column(Integer, ForeignKey('teams.id'), nullable=False)

    # Additional info
    placement = Column(Integer)  # Final placement (1st, 2nd, etc)
    prize = Column(String(100))

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    event = relationship("Event", back_populates="event_teams")
    team = relationship("Team", back_populates="event_teams")

    __table_args__ = (
        UniqueConstraint('event_id', 'team_id', name='uq_event_team'),
    )

    def __repr__(self):
        return f"<EventTeam(event_id={self.event_id}, team_id={self.team_id})>"


class TeamPlayer(Base):
    """Team roster - CLEAN VERSION"""
    __tablename__ = 'team_players'

    id = Column(Integer, primary_key=True, autoincrement=True)
    team_id = Column(Integer, ForeignKey('teams.id'), nullable=False)
    player_id = Column(Integer, ForeignKey('players.id'), nullable=False)

    # Role in team
    role = Column(String(50))  # 'player', 'coach', 'standin', etc
    is_current = Column(Boolean, default=True)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    team = relationship("Team", back_populates="roster")
    player = relationship("Player", back_populates="team_history")

    __table_args__ = (
        UniqueConstraint('team_id', 'player_id', name='uq_team_player'),
    )

    def __repr__(self):
        return f"<TeamPlayer(team_id={self.team_id}, player_id={self.player_id}, role='{self.role}')>"
