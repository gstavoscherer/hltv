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


# ============================================================================
# MATCH DATA
# ============================================================================

class Match(Base):
    __tablename__ = 'matches'

    id = Column(Integer, primary_key=True)
    event_id = Column(Integer, ForeignKey('events.id'), nullable=False)
    team1_id = Column(Integer, ForeignKey('teams.id'), nullable=True)
    team2_id = Column(Integer, ForeignKey('teams.id'), nullable=True)

    score1 = Column(Integer)
    score2 = Column(Integer)
    best_of = Column(Integer)
    date = Column(Date)
    winner_id = Column(Integer, ForeignKey('teams.id'), nullable=True)
    stars = Column(Integer)

    created_at = Column(DateTime, server_default=func.now())

    event = relationship("Event")
    team1 = relationship("Team", foreign_keys=[team1_id])
    team2 = relationship("Team", foreign_keys=[team2_id])
    winner = relationship("Team", foreign_keys=[winner_id])
    maps = relationship("MatchMap", back_populates="match", cascade="all, delete-orphan")
    vetos = relationship("MatchVeto", back_populates="match", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Match(id={self.id}, {self.team1_id} vs {self.team2_id})>"


class MatchMap(Base):
    __tablename__ = 'match_maps'

    id = Column(Integer, primary_key=True)
    match_id = Column(Integer, ForeignKey('matches.id'), nullable=False)
    map_name = Column(String(50), nullable=False)
    map_number = Column(Integer, nullable=False)

    team1_score = Column(Integer)
    team2_score = Column(Integer)
    team1_ct_score = Column(Integer)
    team1_t_score = Column(Integer)
    team2_ct_score = Column(Integer)
    team2_t_score = Column(Integer)

    picked_by = Column(Integer, ForeignKey('teams.id'), nullable=True)
    winner_id = Column(Integer, ForeignKey('teams.id'), nullable=True)

    created_at = Column(DateTime, server_default=func.now())

    match = relationship("Match", back_populates="maps")
    picker = relationship("Team", foreign_keys=[picked_by])
    winner = relationship("Team", foreign_keys=[winner_id])
    player_stats = relationship("MatchPlayerStats", back_populates="match_map", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<MatchMap(id={self.id}, map={self.map_name})>"


class MatchPlayerStats(Base):
    __tablename__ = 'match_player_stats'

    id = Column(Integer, primary_key=True, autoincrement=True)
    map_id = Column(Integer, ForeignKey('match_maps.id'), nullable=False)
    player_id = Column(Integer, ForeignKey('players.id'), nullable=False)
    team_id = Column(Integer, ForeignKey('teams.id'), nullable=False)

    kills = Column(Integer)
    deaths = Column(Integer)
    assists = Column(Integer)
    headshots = Column(Integer)
    flash_assists = Column(Integer)
    adr = Column(Float)
    kast = Column(Float)
    rating = Column(Float)
    opening_kills = Column(Integer)
    opening_deaths = Column(Integer)
    multi_kill_rounds = Column(Integer)
    clutches_won = Column(Integer)

    created_at = Column(DateTime, server_default=func.now())

    match_map = relationship("MatchMap", back_populates="player_stats")
    player = relationship("Player")
    team = relationship("Team")

    __table_args__ = (
        UniqueConstraint('map_id', 'player_id', name='uq_map_player_stats'),
    )

    def __repr__(self):
        return f"<MatchPlayerStats(map_id={self.map_id}, player_id={self.player_id})>"


class MatchVeto(Base):
    __tablename__ = 'match_vetos'

    id = Column(Integer, primary_key=True, autoincrement=True)
    match_id = Column(Integer, ForeignKey('matches.id'), nullable=False)
    veto_number = Column(Integer, nullable=False)
    team_id = Column(Integer, ForeignKey('teams.id'), nullable=True)
    action = Column(String(20), nullable=False)
    map_name = Column(String(50), nullable=False)

    created_at = Column(DateTime, server_default=func.now())

    match = relationship("Match", back_populates="vetos")
    team = relationship("Team")

    __table_args__ = (
        UniqueConstraint('match_id', 'veto_number', name='uq_match_veto_number'),
    )

    def __repr__(self):
        return f"<MatchVeto(match_id={self.match_id}, #{self.veto_number} {self.action} {self.map_name})>"


# ============================================================================
# CARTOLA CS
# ============================================================================

class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), nullable=False, unique=True)
    email = Column(String(255), nullable=False, unique=True)
    password_hash = Column(String(255), nullable=False)
    discord_id = Column(String(50), nullable=True, unique=True)
    balance = Column(Float, default=100.0)
    created_at = Column(DateTime, server_default=func.now())

    portfolio = relationship("UserPortfolio", back_populates="user", cascade="all, delete-orphan")
    transactions = relationship("Transaction", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User(id={self.id}, username='{self.username}')>"


class PlayerRole(Base):
    __tablename__ = 'player_roles'

    id = Column(Integer, primary_key=True, autoincrement=True)
    player_id = Column(Integer, ForeignKey('players.id'), nullable=False)
    role = Column(String(20), nullable=False)
    is_primary = Column(Boolean, default=False)

    player = relationship("Player")

    __table_args__ = (
        UniqueConstraint('player_id', 'role', name='uq_player_role'),
    )

    def __repr__(self):
        return f"<PlayerRole(player_id={self.player_id}, role='{self.role}')>"


class PlayerMarket(Base):
    __tablename__ = 'player_market'

    player_id = Column(Integer, ForeignKey('players.id'), primary_key=True)
    current_price = Column(Float, nullable=False)
    previous_price = Column(Float)
    price_change_pct = Column(Float, default=0.0)
    last_updated = Column(DateTime, server_default=func.now())

    player = relationship("Player")

    def __repr__(self):
        return f"<PlayerMarket(player_id={self.player_id}, price={self.current_price})>"


class PlayerPriceHistory(Base):
    __tablename__ = 'player_price_history'

    id = Column(Integer, primary_key=True, autoincrement=True)
    player_id = Column(Integer, ForeignKey('players.id'), nullable=False)
    price = Column(Float, nullable=False)
    match_id = Column(Integer, ForeignKey('matches.id'), nullable=True)
    timestamp = Column(DateTime, server_default=func.now())

    player = relationship("Player")
    match = relationship("Match")

    def __repr__(self):
        return f"<PlayerPriceHistory(player_id={self.player_id}, price={self.price})>"


class UserPortfolio(Base):
    __tablename__ = 'user_portfolio'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    player_id = Column(Integer, ForeignKey('players.id'), nullable=False)
    buy_price = Column(Float, nullable=False)
    bought_at = Column(DateTime, server_default=func.now())

    user = relationship("User", back_populates="portfolio")
    player = relationship("Player")

    def __repr__(self):
        return f"<UserPortfolio(user_id={self.user_id}, player_id={self.player_id})>"


class Transaction(Base):
    __tablename__ = 'transactions'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    player_id = Column(Integer, ForeignKey('players.id'), nullable=False)
    type = Column(String(10), nullable=False)
    price = Column(Float, nullable=False)
    timestamp = Column(DateTime, server_default=func.now())

    user = relationship("User", back_populates="transactions")
    player = relationship("Player")

    def __repr__(self):
        return f"<Transaction(user_id={self.user_id}, {self.type} player_id={self.player_id})>"
