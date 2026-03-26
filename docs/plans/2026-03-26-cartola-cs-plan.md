# CartolaCS Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a fantasy CS2 game (CartolaCS) where users buy/sell players based on real match performance.

**Architecture:** Monolito no repo HLTV. Novos models no mesmo SQLite, API endpoints via FastAPI router, Discord bot no mesmo processo, frontend React no SPA existente.

**Tech Stack:** Python 3.10, FastAPI, SQLAlchemy, SQLite, discord.py, PyJWT, bcrypt, React, recharts

---

### Task 1: Models do CartolaCS

**Files:**
- Modify: `src/database/models.py` (adicionar novos models após MatchVeto)
- Modify: `src/database/__init__.py` (nenhuma mudança necessária — init_db já cria tudo via Base)

**Step 1: Adicionar models ao models.py**

Adicionar após a class `MatchVeto`, na seção `# CARTOLA CS`:

```python
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
    role = Column(String(20), nullable=False)  # awp, rifler, igl, lurker, entry, support
    is_primary = Column(Boolean, default=False)

    player = relationship("Player")

    __table_args__ = (
        UniqueConstraint('player_id', 'role', name='uq_player_role'),
    )


class PlayerMarket(Base):
    __tablename__ = 'player_market'

    player_id = Column(Integer, ForeignKey('players.id'), primary_key=True)
    current_price = Column(Float, nullable=False)
    previous_price = Column(Float)
    price_change_pct = Column(Float, default=0.0)
    last_updated = Column(DateTime, server_default=func.now())

    player = relationship("Player")


class PlayerPriceHistory(Base):
    __tablename__ = 'player_price_history'

    id = Column(Integer, primary_key=True, autoincrement=True)
    player_id = Column(Integer, ForeignKey('players.id'), nullable=False)
    price = Column(Float, nullable=False)
    match_id = Column(Integer, ForeignKey('matches.id'), nullable=True)
    timestamp = Column(DateTime, server_default=func.now())

    player = relationship("Player")
    match = relationship("Match")


class UserPortfolio(Base):
    __tablename__ = 'user_portfolio'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    player_id = Column(Integer, ForeignKey('players.id'), nullable=False)
    buy_price = Column(Float, nullable=False)
    bought_at = Column(DateTime, server_default=func.now())

    user = relationship("User", back_populates="portfolio")
    player = relationship("Player")


class Transaction(Base):
    __tablename__ = 'transactions'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    player_id = Column(Integer, ForeignKey('players.id'), nullable=False)
    type = Column(String(10), nullable=False)  # buy, sell
    price = Column(Float, nullable=False)
    timestamp = Column(DateTime, server_default=func.now())

    user = relationship("User", back_populates="transactions")
    player = relationship("Player")
```

**Step 2: Rodar init_db pra criar as tabelas**

```bash
cd /root/hltv && python3 -c "from src.database import init_db; init_db(); print('OK')"
```

**Step 3: Verificar que as tabelas foram criadas**

```bash
sqlite3 hltv_data.db ".tables" | grep -E "users|player_market|player_roles|player_price_history|user_portfolio|transactions"
```

**Step 4: Commit**

```bash
git add src/database/models.py
git commit -m "feat(cartola): add CartolaCS database models"
```

---

### Task 2: Motor de Precificação

**Files:**
- Create: `cartola/__init__.py`
- Create: `cartola/pricing.py`

**Step 1: Criar cartola/__init__.py**

```python
# CartolaCS — Fantasy CS2
```

**Step 2: Criar cartola/pricing.py**

```python
"""
Motor de precificacao do CartolaCS.
Calcula precos iniciais e atualiza precos pos-partida.
"""

from src.database import session_scope
from src.database.models import (
    Player, Team, Match, MatchMap, MatchPlayerStats,
    PlayerMarket, PlayerPriceHistory, TeamPlayer,
)
from sqlalchemy import func
from datetime import datetime, timedelta


# ============================================================================
# CONSTANTES
# ============================================================================

MAX_VARIATION_PER_MATCH = 0.15   # ±15%
MAX_VARIATION_PER_DAY = 0.20     # ±20%
MIN_PRICE = 1.0
MAX_PRICE = 200.0
DECAY_START_DAYS = 14
DECAY_RATE = 0.01                # -1%/dia
ROSTER_CRASH = 0.30              # -30% ao sair do roster

SHORT_TERM_WEIGHT = 0.40
MID_TERM_WEIGHT = 0.40
LONG_TERM_WEIGHT = 0.20

MID_TERM_MATCH_COUNT = 10
MID_TERM_WEIGHTS = [1.0, 0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2, 0.1]

TEAM_RANK_FACTORS = [
    (5, 5.0), (10, 4.0), (20, 3.0), (30, 2.0), (50, 1.5),
]
DEFAULT_TEAM_FACTOR = 1.0

OPPONENT_MULT = [
    (5, 1.3), (10, 1.2), (20, 1.1), (30, 1.0), (50, 0.9),
]
DEFAULT_OPPONENT_MULT = 0.8

EVENT_WEIGHTS = {
    'Major': 1.5,
    'big': 1.2,
}
DEFAULT_EVENT_WEIGHT = 1.0

BO_WEIGHTS = {1: 0.7}
DEFAULT_BO_WEIGHT = 1.0

WIN_BONUS = 0.03
DEMAND_MAX = 0.03


# ============================================================================
# HELPERS
# ============================================================================

def _get_team_factor(world_rank):
    """Retorna o fator de time baseado no ranking mundial."""
    if world_rank is None:
        return DEFAULT_TEAM_FACTOR
    for threshold, factor in TEAM_RANK_FACTORS:
        if world_rank <= threshold:
            return factor
    return DEFAULT_TEAM_FACTOR


def _get_opponent_mult(world_rank):
    """Retorna o multiplicador do adversario."""
    if world_rank is None:
        return DEFAULT_OPPONENT_MULT
    for threshold, mult in OPPONENT_MULT:
        if world_rank <= threshold:
            return mult
    return DEFAULT_OPPONENT_MULT


def _get_event_weight(event):
    """Retorna o peso do evento."""
    if not event:
        return DEFAULT_EVENT_WEIGHT
    etype = (event.event_type or '').lower()
    if 'major' in etype:
        return EVENT_WEIGHTS['Major']
    if 'big' in etype:
        return EVENT_WEIGHTS['big']
    return DEFAULT_EVENT_WEIGHT


def _get_bo_weight(best_of):
    """Retorna o peso do formato (bo1 vale menos)."""
    return BO_WEIGHTS.get(best_of, DEFAULT_BO_WEIGHT)


def _clamp(value, min_val, max_val):
    return max(min_val, min(max_val, value))


# ============================================================================
# PRECO INICIAL
# ============================================================================

def calculate_initial_price(player, team=None):
    """Calcula preco inicial baseado no rank do time + rating do jogador."""
    rating = player.rating_2_0 or 1.0
    rank = team.world_rank if team else None
    team_factor = _get_team_factor(rank)
    price = team_factor * rating * 10
    return _clamp(round(price, 2), MIN_PRICE, MAX_PRICE)


def initialize_market():
    """Popula player_market com precos iniciais pra todos os jogadores."""
    with session_scope() as s:
        players = s.query(Player).all()
        count = 0
        for p in players:
            existing = s.query(PlayerMarket).get(p.id)
            if existing:
                continue

            team = None
            if p.current_team_id:
                team = s.query(Team).get(p.current_team_id)

            price = calculate_initial_price(p, team)
            s.add(PlayerMarket(
                player_id=p.id,
                current_price=price,
                previous_price=price,
                price_change_pct=0.0,
            ))
            s.add(PlayerPriceHistory(
                player_id=p.id,
                price=price,
            ))
            count += 1
        print(f"Mercado inicializado: {count} jogadores com preco")


# ============================================================================
# SHORT TERM — performance numa partida
# ============================================================================

def calculate_short_term(player_id, match, session):
    """Calcula variacao short_term pra um jogador numa partida."""
    # Pegar stats do jogador nos mapas dessa partida
    maps = session.query(MatchMap).filter(MatchMap.match_id == match.id).all()
    if not maps:
        return 0.0

    total_rounds = 0
    weighted_rating = 0.0
    weighted_adr = 0.0
    weighted_kast = 0.0
    total_opening_kills = 0
    total_opening_deaths = 0
    total_clutches = 0

    for mm in maps:
        stats = (
            session.query(MatchPlayerStats)
            .filter(MatchPlayerStats.map_id == mm.id, MatchPlayerStats.player_id == player_id)
            .first()
        )
        if not stats:
            continue

        rounds = (mm.team1_score or 0) + (mm.team2_score or 0)
        if rounds == 0:
            rounds = 1
        total_rounds += rounds
        weighted_rating += (stats.rating or 1.0) * rounds
        weighted_adr += (stats.adr or 80.0) * rounds
        weighted_kast += (stats.kast or 70.0) * rounds
        total_opening_kills += stats.opening_kills or 0
        total_opening_deaths += stats.opening_deaths or 0
        total_clutches += stats.clutches_won or 0

    if total_rounds == 0:
        return 0.0

    avg_rating = weighted_rating / total_rounds
    avg_adr = weighted_adr / total_rounds
    avg_kast = weighted_kast / total_rounds

    # base_perf
    rating_diff = (avg_rating - 1.0) * 0.3
    adr_diff = (avg_adr - 80) / 200
    kast_diff = (avg_kast - 70) / 100
    opening_diff = (total_opening_kills - total_opening_deaths) * 0.03
    clutch_bonus = total_clutches * 0.02

    base_perf = (
        0.40 * rating_diff
        + 0.25 * adr_diff
        + 0.15 * kast_diff
        + 0.10 * opening_diff
        + 0.10 * clutch_bonus
    )

    # Opponent multiplier
    opponent_id = match.team2_id if match.team1_id == _get_player_team_in_match(player_id, match, session) else match.team1_id
    opponent = session.query(Team).get(opponent_id) if opponent_id else None
    opp_mult = _get_opponent_mult(opponent.world_rank if opponent else None)

    # Event + BO weight
    event_w = _get_event_weight(match.event)
    bo_w = _get_bo_weight(match.best_of)

    # Win bonus
    player_team_id = _get_player_team_in_match(player_id, match, session)
    if match.winner_id and match.winner_id == player_team_id:
        w_bonus = WIN_BONUS
    elif match.winner_id:
        w_bonus = -WIN_BONUS
    else:
        w_bonus = 0.0

    short = base_perf * opp_mult * event_w * bo_w + w_bonus
    return short


def _get_player_team_in_match(player_id, match, session):
    """Descobre em qual time o jogador estava nessa partida."""
    maps = session.query(MatchMap).filter(MatchMap.match_id == match.id).all()
    for mm in maps:
        stats = (
            session.query(MatchPlayerStats)
            .filter(MatchPlayerStats.map_id == mm.id, MatchPlayerStats.player_id == player_id)
            .first()
        )
        if stats and stats.team_id:
            return stats.team_id
    return None


# ============================================================================
# MID TERM — ultimas 10 partidas
# ============================================================================

def calculate_mid_term(player_id, session, exclude_match_id=None):
    """Media ponderada dos short_terms das ultimas 10 partidas."""
    # Pegar ultimas 10 partidas do jogador
    subq = (
        session.query(MatchPlayerStats.map_id)
        .filter(MatchPlayerStats.player_id == player_id)
        .subquery()
    )
    match_ids = (
        session.query(MatchMap.match_id)
        .filter(MatchMap.id.in_(subq))
        .distinct()
        .subquery()
    )
    matches = (
        session.query(Match)
        .filter(Match.id.in_(match_ids))
        .order_by(Match.date.desc().nullslast())
        .limit(MID_TERM_MATCH_COUNT + 1)  # +1 caso precise excluir
        .all()
    )

    if exclude_match_id:
        matches = [m for m in matches if m.id != exclude_match_id]
    matches = matches[:MID_TERM_MATCH_COUNT]

    if not matches:
        return 0.0

    total_weight = 0.0
    weighted_sum = 0.0
    for i, m in enumerate(matches):
        w = MID_TERM_WEIGHTS[i] if i < len(MID_TERM_WEIGHTS) else 0.1
        st = calculate_short_term(player_id, m, session)
        weighted_sum += st * w
        total_weight += w

    return weighted_sum / total_weight if total_weight > 0 else 0.0


# ============================================================================
# LONG TERM — fair price anchor
# ============================================================================

def calculate_long_term(player_id, current_price, session):
    """Puxa o preco de volta pro fair price lentamente."""
    player = session.query(Player).get(player_id)
    if not player:
        return 0.0

    team = session.query(Team).get(player.current_team_id) if player.current_team_id else None
    fair = calculate_initial_price(player, team)

    if current_price <= 0:
        return 0.0
    return (fair - current_price) / current_price * 0.1


# ============================================================================
# UPDATE PRINCIPAL
# ============================================================================

def update_player_price(player_id, match, session):
    """Atualiza preco de um jogador apos uma partida."""
    market = session.query(PlayerMarket).get(player_id)
    if not market:
        return

    current = market.current_price

    # 3 janelas
    short = calculate_short_term(player_id, match, session)
    mid = calculate_mid_term(player_id, session, exclude_match_id=match.id)
    long = calculate_long_term(player_id, current, session)

    variation = (
        SHORT_TERM_WEIGHT * short
        + MID_TERM_WEIGHT * mid
        + LONG_TERM_WEIGHT * long
    )

    # Clamp variacao por partida
    variation = _clamp(variation, -MAX_VARIATION_PER_MATCH, MAX_VARIATION_PER_MATCH)

    # Checar cap diario
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today_history = (
        session.query(PlayerPriceHistory)
        .filter(
            PlayerPriceHistory.player_id == player_id,
            PlayerPriceHistory.timestamp >= today_start,
        )
        .order_by(PlayerPriceHistory.timestamp.asc())
        .first()
    )
    if today_history:
        day_start_price = today_history.price
        projected = current * (1 + variation)
        day_change = (projected - day_start_price) / day_start_price
        if abs(day_change) > MAX_VARIATION_PER_DAY:
            # Limitar ao cap diario
            max_price = day_start_price * (1 + MAX_VARIATION_PER_DAY)
            min_price_day = day_start_price * (1 - MAX_VARIATION_PER_DAY)
            projected = _clamp(projected, min_price_day, max_price)
            variation = (projected - current) / current if current > 0 else 0

    new_price = _clamp(round(current * (1 + variation), 2), MIN_PRICE, MAX_PRICE)

    # Atualizar mercado
    market.previous_price = current
    market.current_price = new_price
    market.price_change_pct = round(variation * 100, 2)
    market.last_updated = datetime.utcnow()

    # Historico
    session.add(PlayerPriceHistory(
        player_id=player_id,
        price=new_price,
        match_id=match.id,
    ))


def update_prices_for_match(match_id):
    """Atualiza precos de todos os jogadores que jogaram numa partida."""
    with session_scope() as s:
        match = s.query(Match).get(match_id)
        if not match:
            return

        # Pegar todos os jogadores que jogaram
        player_ids = (
            s.query(MatchPlayerStats.player_id)
            .join(MatchMap, MatchPlayerStats.map_id == MatchMap.id)
            .filter(MatchMap.match_id == match_id)
            .distinct()
            .all()
        )
        player_ids = [pid for (pid,) in player_ids]

        for pid in player_ids:
            update_player_price(pid, match, s)

        print(f"  Precos atualizados: {len(player_ids)} jogadores (match {match_id})")


def apply_decay():
    """Aplica decay de -1%/dia pra jogadores inativos ha mais de 14 dias."""
    with session_scope() as s:
        cutoff = datetime.utcnow() - timedelta(days=DECAY_START_DAYS)
        markets = s.query(PlayerMarket).filter(PlayerMarket.last_updated < cutoff).all()
        for m in markets:
            days_inactive = (datetime.utcnow() - m.last_updated).days - DECAY_START_DAYS
            if days_inactive <= 0:
                continue
            decay = DECAY_RATE * days_inactive
            new_price = _clamp(round(m.current_price * (1 - decay), 2), MIN_PRICE, MAX_PRICE)
            m.previous_price = m.current_price
            m.current_price = new_price
            m.price_change_pct = round(-decay * 100, 2)
        if markets:
            print(f"Decay aplicado: {len(markets)} jogadores")


def apply_roster_crash(player_id):
    """Aplica crash de -30% quando jogador sai do roster."""
    with session_scope() as s:
        market = s.query(PlayerMarket).get(player_id)
        if not market:
            return
        new_price = _clamp(round(market.current_price * (1 - ROSTER_CRASH), 2), MIN_PRICE, MAX_PRICE)
        market.previous_price = market.current_price
        market.current_price = new_price
        market.price_change_pct = round(-ROSTER_CRASH * 100, 2)
        market.last_updated = datetime.utcnow()
        session.add(PlayerPriceHistory(player_id=player_id, price=new_price))
        print(f"Roster crash: jogador {player_id} -> {new_price}")


def recalculate_fair_prices():
    """Recalcula fair prices semanalmente (long term anchor)."""
    # Nao precisa de acao separada — o long_term e calculado on-the-fly
    # usando os stats e rankings atualizados.
    # Esta funcao existe pra ser chamada no sync semanal se necessario.
    print("Fair prices recalculados (usa stats atuais on-the-fly)")
```

**Step 3: Rodar teste basico**

```bash
cd /root/hltv && python3 -c "from cartola.pricing import calculate_initial_price; print('Import OK')"
```

**Step 4: Commit**

```bash
git add cartola/
git commit -m "feat(cartola): add pricing engine with 3-window model"
```

---

### Task 3: Auth (JWT + bcrypt + Discord OAuth2)

**Files:**
- Create: `cartola/auth.py`

**Step 1: Criar cartola/auth.py**

```python
"""
Autenticacao do CartolaCS: JWT, bcrypt, Discord OAuth2.
"""

import os
import hashlib
import secrets
from datetime import datetime, timedelta

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from src.database import session_scope
from src.database.models import User

SECRET_KEY = os.environ.get("CARTOLA_SECRET_KEY", "cartola-cs-dev-key-change-in-prod")
ALGORITHM = "HS256"
TOKEN_EXPIRE_DAYS = 7

DISCORD_CLIENT_ID = os.environ.get("DISCORD_CLIENT_ID", "")
DISCORD_CLIENT_SECRET = os.environ.get("DISCORD_CLIENT_SECRET", "")
DISCORD_REDIRECT_URI = os.environ.get("DISCORD_REDIRECT_URI", "https://gustavoscherer.com/hltv/api/cartola/auth/discord/callback")

security = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


def create_token(user_id: int, username: str) -> str:
    payload = {
        "sub": user_id,
        "username": username,
        "exp": datetime.utcnow() + timedelta(days=TOKEN_EXPIRE_DAYS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expirado")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token invalido")


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if not credentials:
        raise HTTPException(status_code=401, detail="Auth required")
    payload = decode_token(credentials.credentials)
    return payload


def generate_link_token(user_id: int) -> str:
    """Gera token temporario pra vincular Discord."""
    payload = {
        "sub": user_id,
        "purpose": "discord_link",
        "exp": datetime.utcnow() + timedelta(minutes=15),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
```

**Step 2: Instalar dependencias**

```bash
pip install bcrypt PyJWT
```

**Step 3: Testar import**

```bash
cd /root/hltv && python3 -c "from cartola.auth import hash_password, verify_password; h = hash_password('test'); print(verify_password('test', h))"
```

**Step 4: Commit**

```bash
git add cartola/auth.py
git commit -m "feat(cartola): add auth module with JWT and bcrypt"
```

---

### Task 4: API Endpoints do CartolaCS

**Files:**
- Create: `cartola/api.py`
- Modify: `api/main.py` (incluir router)

**Step 1: Criar cartola/api.py**

```python
"""
API endpoints do CartolaCS.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from datetime import datetime

from src.database import session_scope
from src.database.models import (
    Player, Team, PlayerMarket, PlayerPriceHistory, PlayerRole,
    User, UserPortfolio, Transaction,
)
from cartola.auth import (
    hash_password, verify_password, create_token,
    get_current_user, generate_link_token, decode_token,
)
from cartola.pricing import calculate_initial_price
from sqlalchemy import func, desc

router = APIRouter(prefix="/api/cartola", tags=["cartola"])


# ============================================================================
# Schemas
# ============================================================================

class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str

class LoginRequest(BaseModel):
    email: str
    password: str


# ============================================================================
# AUTH
# ============================================================================

@router.post("/auth/register")
def register(req: RegisterRequest):
    with session_scope() as s:
        if s.query(User).filter(User.email == req.email).first():
            raise HTTPException(400, "Email ja cadastrado")
        if s.query(User).filter(User.username == req.username).first():
            raise HTTPException(400, "Username ja em uso")
        user = User(
            username=req.username,
            email=req.email,
            password_hash=hash_password(req.password),
        )
        s.add(user)
        s.flush()
        token = create_token(user.id, user.username)
    return {"token": token, "username": req.username}


@router.post("/auth/login")
def login(req: LoginRequest):
    with session_scope() as s:
        user = s.query(User).filter(User.email == req.email).first()
        if not user or not verify_password(req.password, user.password_hash):
            raise HTTPException(401, "Credenciais invalidas")
        token = create_token(user.id, user.username)
    return {"token": token, "username": user.username}


# ============================================================================
# MARKET
# ============================================================================

@router.get("/market")
def list_market(
    role: str = Query(None, description="Filtrar por role"),
    sort_by: str = Query("current_price", description="current_price, price_change_pct, rating"),
    order: str = Query("desc"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    with session_scope() as s:
        q = (
            s.query(PlayerMarket, Player)
            .join(Player, PlayerMarket.player_id == Player.id)
        )

        if role:
            q = q.join(PlayerRole, PlayerRole.player_id == Player.id).filter(PlayerRole.role == role)

        sort_map = {
            "current_price": PlayerMarket.current_price,
            "price_change_pct": PlayerMarket.price_change_pct,
            "rating": Player.rating_2_0,
        }
        sort_col = sort_map.get(sort_by, PlayerMarket.current_price)
        if order == "asc":
            q = q.order_by(sort_col.asc().nullslast())
        else:
            q = q.order_by(sort_col.desc().nullslast())

        total = q.count()
        results = q.offset(offset).limit(limit).all()

        players = []
        for market, player in results:
            roles = s.query(PlayerRole).filter(PlayerRole.player_id == player.id).all()
            team = s.query(Team).get(player.current_team_id) if player.current_team_id else None
            players.append({
                "id": player.id,
                "nickname": player.nickname,
                "country": player.country,
                "team": {"id": team.id, "name": team.name} if team else None,
                "rating_2_0": player.rating_2_0,
                "roles": [{"role": r.role, "is_primary": r.is_primary} for r in roles],
                "current_price": market.current_price,
                "previous_price": market.previous_price,
                "price_change_pct": market.price_change_pct,
            })

        return {"total": total, "offset": offset, "limit": limit, "players": players}


@router.get("/market/{player_id}")
def get_market_player(player_id: int):
    with session_scope() as s:
        market = s.query(PlayerMarket).get(player_id)
        if not market:
            raise HTTPException(404, "Jogador nao encontrado no mercado")
        player = s.query(Player).get(player_id)
        team = s.query(Team).get(player.current_team_id) if player.current_team_id else None
        roles = s.query(PlayerRole).filter(PlayerRole.player_id == player_id).all()

        return {
            "id": player.id,
            "nickname": player.nickname,
            "real_name": player.real_name,
            "country": player.country,
            "age": player.age,
            "team": {"id": team.id, "name": team.name, "world_rank": team.world_rank} if team else None,
            "rating_2_0": player.rating_2_0,
            "kd_ratio": player.kd_ratio,
            "adr": player.adr,
            "kast": player.kast,
            "impact": player.impact,
            "roles": [{"role": r.role, "is_primary": r.is_primary} for r in roles],
            "current_price": market.current_price,
            "previous_price": market.previous_price,
            "price_change_pct": market.price_change_pct,
        }


@router.get("/market/{player_id}/history")
def get_price_history(player_id: int, days: int = Query(30, ge=1, le=365)):
    with session_scope() as s:
        cutoff = datetime.utcnow() - __import__('datetime').timedelta(days=days)
        history = (
            s.query(PlayerPriceHistory)
            .filter(PlayerPriceHistory.player_id == player_id, PlayerPriceHistory.timestamp >= cutoff)
            .order_by(PlayerPriceHistory.timestamp.asc())
            .all()
        )
        return [
            {"price": h.price, "timestamp": h.timestamp.isoformat(), "match_id": h.match_id}
            for h in history
        ]


# ============================================================================
# PORTFOLIO
# ============================================================================

@router.get("/portfolio")
def get_portfolio(user=Depends(get_current_user)):
    with session_scope() as s:
        u = s.query(User).get(user["sub"])
        if not u:
            raise HTTPException(404, "Usuario nao encontrado")
        items = s.query(UserPortfolio).filter(UserPortfolio.user_id == u.id).all()
        portfolio = []
        total_value = u.balance
        for item in items:
            market = s.query(PlayerMarket).get(item.player_id)
            player = s.query(Player).get(item.player_id)
            team = s.query(Team).get(player.current_team_id) if player and player.current_team_id else None
            current_price = market.current_price if market else item.buy_price
            total_value += current_price
            portfolio.append({
                "player_id": item.player_id,
                "nickname": player.nickname if player else None,
                "team": {"id": team.id, "name": team.name} if team else None,
                "buy_price": item.buy_price,
                "current_price": current_price,
                "profit": round(current_price - item.buy_price, 2),
                "bought_at": item.bought_at.isoformat() if item.bought_at else None,
            })
        return {
            "balance": u.balance,
            "total_value": round(total_value, 2),
            "profit": round(total_value - 100.0, 2),
            "players": portfolio,
        }


@router.post("/portfolio/buy/{player_id}")
def buy_player(player_id: int, user=Depends(get_current_user)):
    with session_scope() as s:
        u = s.query(User).get(user["sub"])
        if not u:
            raise HTTPException(404, "Usuario nao encontrado")

        # Checar limite de 5
        count = s.query(UserPortfolio).filter(UserPortfolio.user_id == u.id).count()
        if count >= 5:
            raise HTTPException(400, "Limite de 5 jogadores atingido")

        # Checar se ja tem esse jogador
        existing = (
            s.query(UserPortfolio)
            .filter(UserPortfolio.user_id == u.id, UserPortfolio.player_id == player_id)
            .first()
        )
        if existing:
            raise HTTPException(400, "Voce ja tem esse jogador")

        # Checar preco
        market = s.query(PlayerMarket).get(player_id)
        if not market:
            raise HTTPException(404, "Jogador nao encontrado no mercado")

        if u.balance < market.current_price:
            raise HTTPException(400, f"Saldo insuficiente ({u.balance:.2f} < {market.current_price:.2f})")

        # Comprar
        u.balance -= market.current_price
        s.add(UserPortfolio(
            user_id=u.id,
            player_id=player_id,
            buy_price=market.current_price,
        ))
        s.add(Transaction(
            user_id=u.id,
            player_id=player_id,
            type="buy",
            price=market.current_price,
        ))

        return {"message": "Compra realizada", "balance": round(u.balance, 2), "price": market.current_price}


@router.post("/portfolio/sell/{player_id}")
def sell_player(player_id: int, user=Depends(get_current_user)):
    with session_scope() as s:
        u = s.query(User).get(user["sub"])
        if not u:
            raise HTTPException(404, "Usuario nao encontrado")

        item = (
            s.query(UserPortfolio)
            .filter(UserPortfolio.user_id == u.id, UserPortfolio.player_id == player_id)
            .first()
        )
        if not item:
            raise HTTPException(404, "Jogador nao esta no seu time")

        market = s.query(PlayerMarket).get(player_id)
        sell_price = market.current_price if market else item.buy_price

        u.balance += sell_price
        s.delete(item)
        s.add(Transaction(
            user_id=u.id,
            player_id=player_id,
            type="sell",
            price=sell_price,
        ))

        return {
            "message": "Venda realizada",
            "balance": round(u.balance, 2),
            "price": sell_price,
            "profit": round(sell_price - item.buy_price, 2),
        }


# ============================================================================
# RANKINGS
# ============================================================================

@router.get("/ranking")
def ranking_patrimony(limit: int = Query(20, ge=1, le=100)):
    """Ranking por patrimonio total (saldo + valor dos jogadores)."""
    with session_scope() as s:
        users = s.query(User).all()
        ranking = []
        for u in users:
            items = s.query(UserPortfolio).filter(UserPortfolio.user_id == u.id).all()
            total = u.balance
            for item in items:
                market = s.query(PlayerMarket).get(item.player_id)
                total += market.current_price if market else item.buy_price
            ranking.append({
                "user_id": u.id,
                "username": u.username,
                "total_value": round(total, 2),
                "balance": round(u.balance, 2),
                "players_count": len(items),
            })
        ranking.sort(key=lambda x: x["total_value"], reverse=True)
        return ranking[:limit]


@router.get("/ranking/profit")
def ranking_profit(limit: int = Query(20, ge=1, le=100)):
    """Ranking por lucro (patrimonio - 100 inicial)."""
    with session_scope() as s:
        users = s.query(User).all()
        ranking = []
        for u in users:
            items = s.query(UserPortfolio).filter(UserPortfolio.user_id == u.id).all()
            total = u.balance
            for item in items:
                market = s.query(PlayerMarket).get(item.player_id)
                total += market.current_price if market else item.buy_price
            profit = total - 100.0
            ranking.append({
                "user_id": u.id,
                "username": u.username,
                "profit": round(profit, 2),
                "profit_pct": round(profit, 2),
            })
        ranking.sort(key=lambda x: x["profit"], reverse=True)
        return ranking[:limit]


@router.get("/ranking/weekly")
def ranking_weekly(limit: int = Query(20, ge=1, le=100)):
    """Ranking por lucro na semana atual."""
    with session_scope() as s:
        from datetime import timedelta
        week_start = datetime.utcnow() - timedelta(days=datetime.utcnow().weekday())
        week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)

        users = s.query(User).all()
        ranking = []
        for u in users:
            # Soma de vendas - soma de compras na semana
            buys = (
                s.query(func.coalesce(func.sum(Transaction.price), 0))
                .filter(Transaction.user_id == u.id, Transaction.type == "buy", Transaction.timestamp >= week_start)
                .scalar()
            )
            sells = (
                s.query(func.coalesce(func.sum(Transaction.price), 0))
                .filter(Transaction.user_id == u.id, Transaction.type == "sell", Transaction.timestamp >= week_start)
                .scalar()
            )
            # Valorizacao do portfolio na semana
            items = s.query(UserPortfolio).filter(UserPortfolio.user_id == u.id).all()
            valorization = 0
            for item in items:
                market = s.query(PlayerMarket).get(item.player_id)
                if market and item.bought_at and item.bought_at >= week_start:
                    valorization += market.current_price - item.buy_price
                elif market:
                    # Pegar preco no inicio da semana
                    hist = (
                        s.query(PlayerPriceHistory)
                        .filter(
                            PlayerPriceHistory.player_id == item.player_id,
                            PlayerPriceHistory.timestamp <= week_start,
                        )
                        .order_by(PlayerPriceHistory.timestamp.desc())
                        .first()
                    )
                    start_price = hist.price if hist else item.buy_price
                    valorization += market.current_price - start_price

            weekly_profit = sells - buys + valorization
            ranking.append({
                "user_id": u.id,
                "username": u.username,
                "weekly_profit": round(weekly_profit, 2),
            })
        ranking.sort(key=lambda x: x["weekly_profit"], reverse=True)
        return ranking[:limit]
```

**Step 2: Incluir router no api/main.py**

Adicionar no final dos imports:
```python
from cartola.api import router as cartola_router
```

E depois do CORS middleware:
```python
app.include_router(cartola_router)
```

**Step 3: Testar API**

```bash
cd /root/hltv && python3 -c "from cartola.api import router; print('Router OK:', len(router.routes), 'routes')"
```

**Step 4: Commit**

```bash
git add cartola/api.py api/main.py
git commit -m "feat(cartola): add API endpoints (auth, market, portfolio, rankings)"
```

---

### Task 5: Discord Bot

**Files:**
- Create: `cartola/bot.py`
- Modify: `api/main.py` (startup do bot)

**Step 1: Instalar discord.py**

```bash
pip install discord.py
```

**Step 2: Criar cartola/bot.py**

```python
"""
Discord bot do CartolaCS.
Roda no mesmo processo que o FastAPI.
"""

import os
import asyncio
import discord
from discord import app_commands

from src.database import session_scope
from src.database.models import (
    Player, Team, PlayerMarket, User, UserPortfolio, Transaction,
)
from cartola.auth import generate_link_token

DISCORD_TOKEN = os.environ.get("DISCORD_BOT_TOKEN", "")
SITE_URL = "https://gustavoscherer.com/hltv/cartola"


class CartolaBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        await self.tree.sync()


bot = CartolaBot()


# ============================================================================
# COMANDOS PUBLICOS
# ============================================================================

@bot.tree.command(name="cartola-market", description="Top jogadores do mercado")
async def market_cmd(interaction: discord.Interaction, jogador: str = None):
    with session_scope() as s:
        if jogador:
            player = s.query(Player).filter(Player.nickname.ilike(f"%{jogador}%")).first()
            if not player:
                await interaction.response.send_message(f"Jogador '{jogador}' nao encontrado")
                return
            market = s.query(PlayerMarket).get(player.id)
            if not market:
                await interaction.response.send_message(f"{player.nickname} nao esta no mercado")
                return
            team = s.query(Team).get(player.current_team_id) if player.current_team_id else None
            embed = discord.Embed(title=f"{player.nickname}", color=0x00ff00 if market.price_change_pct >= 0 else 0xff0000)
            embed.add_field(name="Preco", value=f"{market.current_price:.2f} moedas", inline=True)
            embed.add_field(name="Variacao", value=f"{market.price_change_pct:+.2f}%", inline=True)
            embed.add_field(name="Time", value=team.name if team else "Free agent", inline=True)
            embed.add_field(name="Rating", value=f"{player.rating_2_0:.2f}" if player.rating_2_0 else "--", inline=True)
            await interaction.response.send_message(embed=embed)
        else:
            markets = (
                s.query(PlayerMarket, Player)
                .join(Player, PlayerMarket.player_id == Player.id)
                .order_by(PlayerMarket.current_price.desc())
                .limit(10)
                .all()
            )
            embed = discord.Embed(title="Top 10 Mercado CartolaCS", color=0x1a1a2e)
            for m, p in markets:
                change = f"{m.price_change_pct:+.2f}%" if m.price_change_pct else "0%"
                embed.add_field(
                    name=f"{p.nickname}",
                    value=f"{m.current_price:.2f} moedas ({change})",
                    inline=False,
                )
            await interaction.response.send_message(embed=embed)


@bot.tree.command(name="cartola-ranking", description="Ranking de jogadores")
async def ranking_cmd(interaction: discord.Interaction, tipo: str = "patrimonio"):
    with session_scope() as s:
        users = s.query(User).all()
        ranking = []
        for u in users:
            items = s.query(UserPortfolio).filter(UserPortfolio.user_id == u.id).all()
            total = u.balance
            for item in items:
                market = s.query(PlayerMarket).get(item.player_id)
                total += market.current_price if market else item.buy_price
            ranking.append({"username": u.username, "total": total, "profit": total - 100.0})

        if tipo == "lucro" or tipo == "profit":
            ranking.sort(key=lambda x: x["profit"], reverse=True)
            title = "Ranking por Lucro"
            field = "profit"
        else:
            ranking.sort(key=lambda x: x["total"], reverse=True)
            title = "Ranking por Patrimonio"
            field = "total"

        embed = discord.Embed(title=title, color=0x1a1a2e)
        for i, r in enumerate(ranking[:10], 1):
            embed.add_field(
                name=f"#{i} {r['username']}",
                value=f"{r[field]:.2f} moedas",
                inline=False,
            )
        await interaction.response.send_message(embed=embed)


# ============================================================================
# COMANDOS AUTENTICADOS
# ============================================================================

def _get_user_by_discord(discord_id: str, session):
    return session.query(User).filter(User.discord_id == str(discord_id)).first()


@bot.tree.command(name="cartola-link", description="Vincular conta Discord ao CartolaCS")
async def link_cmd(interaction: discord.Interaction):
    with session_scope() as s:
        user = _get_user_by_discord(interaction.user.id, s)
        if user:
            await interaction.response.send_message(f"Ja vinculado como **{user.username}**!", ephemeral=True)
            return
    await interaction.response.send_message(
        f"Acesse o site pra vincular sua conta:\n{SITE_URL}/link?discord_id={interaction.user.id}",
        ephemeral=True,
    )


@bot.tree.command(name="cartola-portfolio", description="Ver meu time")
async def portfolio_cmd(interaction: discord.Interaction):
    with session_scope() as s:
        user = _get_user_by_discord(interaction.user.id, s)
        if not user:
            await interaction.response.send_message("Conta nao vinculada. Use `/cartola-link`", ephemeral=True)
            return

        items = s.query(UserPortfolio).filter(UserPortfolio.user_id == user.id).all()
        embed = discord.Embed(title=f"Portfolio de {user.username}", color=0x1a1a2e)
        embed.add_field(name="Saldo", value=f"{user.balance:.2f} moedas", inline=False)

        total = user.balance
        for item in items:
            player = s.query(Player).get(item.player_id)
            market = s.query(PlayerMarket).get(item.player_id)
            price = market.current_price if market else item.buy_price
            profit = price - item.buy_price
            total += price
            emoji = "📈" if profit >= 0 else "📉"
            embed.add_field(
                name=f"{emoji} {player.nickname if player else 'Unknown'}",
                value=f"Compra: {item.buy_price:.2f} | Atual: {price:.2f} | {profit:+.2f}",
                inline=False,
            )

        embed.add_field(name="Patrimonio Total", value=f"{total:.2f} moedas", inline=False)
        await interaction.response.send_message(embed=embed)


@bot.tree.command(name="cartola-buy", description="Comprar jogador")
async def buy_cmd(interaction: discord.Interaction, jogador: str):
    with session_scope() as s:
        user = _get_user_by_discord(interaction.user.id, s)
        if not user:
            await interaction.response.send_message("Conta nao vinculada. Use `/cartola-link`", ephemeral=True)
            return

        player = s.query(Player).filter(Player.nickname.ilike(f"%{jogador}%")).first()
        if not player:
            await interaction.response.send_message(f"Jogador '{jogador}' nao encontrado")
            return

        market = s.query(PlayerMarket).get(player.id)
        if not market:
            await interaction.response.send_message(f"{player.nickname} nao esta no mercado")
            return

        count = s.query(UserPortfolio).filter(UserPortfolio.user_id == user.id).count()
        if count >= 5:
            await interaction.response.send_message("Limite de 5 jogadores atingido!")
            return

        existing = s.query(UserPortfolio).filter(
            UserPortfolio.user_id == user.id, UserPortfolio.player_id == player.id
        ).first()
        if existing:
            await interaction.response.send_message(f"Voce ja tem {player.nickname}!")
            return

        if user.balance < market.current_price:
            await interaction.response.send_message(
                f"Saldo insuficiente ({user.balance:.2f} < {market.current_price:.2f})"
            )
            return

        user.balance -= market.current_price
        s.add(UserPortfolio(user_id=user.id, player_id=player.id, buy_price=market.current_price))
        s.add(Transaction(user_id=user.id, player_id=player.id, type="buy", price=market.current_price))

        await interaction.response.send_message(
            f"Compra realizada! **{player.nickname}** por {market.current_price:.2f} moedas. "
            f"Saldo: {user.balance:.2f}"
        )


@bot.tree.command(name="cartola-sell", description="Vender jogador")
async def sell_cmd(interaction: discord.Interaction, jogador: str):
    with session_scope() as s:
        user = _get_user_by_discord(interaction.user.id, s)
        if not user:
            await interaction.response.send_message("Conta nao vinculada. Use `/cartola-link`", ephemeral=True)
            return

        player = s.query(Player).filter(Player.nickname.ilike(f"%{jogador}%")).first()
        if not player:
            await interaction.response.send_message(f"Jogador '{jogador}' nao encontrado")
            return

        item = s.query(UserPortfolio).filter(
            UserPortfolio.user_id == user.id, UserPortfolio.player_id == player.id
        ).first()
        if not item:
            await interaction.response.send_message(f"Voce nao tem {player.nickname} no time!")
            return

        market = s.query(PlayerMarket).get(player.id)
        sell_price = market.current_price if market else item.buy_price
        profit = sell_price - item.buy_price

        user.balance += sell_price
        s.delete(item)
        s.add(Transaction(user_id=user.id, player_id=player.id, type="sell", price=sell_price))

        emoji = "📈" if profit >= 0 else "📉"
        await interaction.response.send_message(
            f"Venda realizada! **{player.nickname}** por {sell_price:.2f} moedas. "
            f"{emoji} Lucro: {profit:+.2f}. Saldo: {user.balance:.2f}"
        )


@bot.tree.command(name="cartola-history", description="Historico de transacoes")
async def history_cmd(interaction: discord.Interaction):
    with session_scope() as s:
        user = _get_user_by_discord(interaction.user.id, s)
        if not user:
            await interaction.response.send_message("Conta nao vinculada. Use `/cartola-link`", ephemeral=True)
            return

        txs = (
            s.query(Transaction)
            .filter(Transaction.user_id == user.id)
            .order_by(Transaction.timestamp.desc())
            .limit(10)
            .all()
        )
        if not txs:
            await interaction.response.send_message("Nenhuma transacao ainda.")
            return

        embed = discord.Embed(title=f"Historico de {user.username}", color=0x1a1a2e)
        for tx in txs:
            player = s.query(Player).get(tx.player_id)
            emoji = "🟢" if tx.type == "buy" else "🔴"
            embed.add_field(
                name=f"{emoji} {tx.type.upper()} {player.nickname if player else 'Unknown'}",
                value=f"{tx.price:.2f} moedas — {tx.timestamp.strftime('%d/%m %H:%M') if tx.timestamp else ''}",
                inline=False,
            )
        await interaction.response.send_message(embed=embed)


# ============================================================================
# START
# ============================================================================

async def start_bot():
    """Inicia o bot Discord."""
    if not DISCORD_TOKEN:
        print("DISCORD_BOT_TOKEN nao configurado, bot nao iniciado")
        return
    await bot.start(DISCORD_TOKEN)
```

**Step 3: Integrar bot no startup do FastAPI**

Adicionar em `api/main.py`:
```python
import asyncio
from cartola.bot import start_bot

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(start_bot())
```

**Step 4: Commit**

```bash
git add cartola/bot.py api/main.py
git commit -m "feat(cartola): add Discord bot with slash commands"
```

---

### Task 6: Tasks (integracao com sync)

**Files:**
- Create: `cartola/tasks.py`
- Modify: `sync_all.py` (chamar update_prices no final)

**Step 1: Criar cartola/tasks.py**

```python
"""
Tasks do CartolaCS: atualizacao de precos pos-sync, decay, inicializacao.
"""

from cartola.pricing import (
    update_prices_for_match, apply_decay, initialize_market, recalculate_fair_prices,
)
from src.database import session_scope
from src.database.models import Match, MatchMap, MatchPlayerStats
from datetime import datetime


def update_prices_after_sync(event_id):
    """Chamada apos sync de um evento. Atualiza precos de todas as partidas novas."""
    with session_scope() as s:
        matches = (
            s.query(Match)
            .filter(Match.event_id == event_id)
            .order_by(Match.date.asc().nullslast())
            .all()
        )
        match_ids = [m.id for m in matches]

    for mid in match_ids:
        update_prices_for_match(mid)


def daily_maintenance():
    """Roda diariamente: decay de jogadores inativos."""
    apply_decay()
    print(f"Manutencao diaria concluida: {datetime.utcnow().isoformat()}")


def weekly_maintenance():
    """Roda semanalmente: recalcula fair prices."""
    recalculate_fair_prices()
    print(f"Manutencao semanal concluida: {datetime.utcnow().isoformat()}")
```

**Step 2: Integrar no sync_all.py**

Adicionar ao final da funcao `sync_full_event`, depois de fechar o match_driver:
```python
# Atualizar precos do CartolaCS
try:
    from cartola.tasks import update_prices_after_sync
    update_prices_after_sync(event_id)
except ImportError:
    pass  # CartolaCS nao instalado
except Exception as e:
    logger.warning("Erro ao atualizar precos CartolaCS: %s", e)
```

**Step 3: Commit**

```bash
git add cartola/tasks.py sync_all.py
git commit -m "feat(cartola): add tasks module and integrate pricing with sync"
```

---

### Task 7: Frontend — Auth (Login, Register, AuthProvider)

**Files:**
- Create: `frontend/src/components/cartola/AuthProvider.jsx`
- Create: `frontend/src/pages/cartola/Login.jsx`
- Create: `frontend/src/pages/cartola/Register.jsx`
- Modify: `frontend/src/api.js` (adicionar fetchCartola com auth)
- Modify: `frontend/src/App.jsx` (adicionar rotas)

**Step 1: Adicionar fetchCartola em api.js**

```javascript
const CARTOLA_BASE = '/hltv/api/cartola'

export function getToken() {
  return localStorage.getItem('cartola_token')
}

export function setToken(token) {
  localStorage.setItem('cartola_token', token)
}

export function removeToken() {
  localStorage.removeItem('cartola_token')
}

export async function fetchCartola(path, options = {}) {
  const token = getToken()
  const headers = { 'Content-Type': 'application/json', ...options.headers }
  if (token) headers['Authorization'] = `Bearer ${token}`

  const res = await fetch(`${CARTOLA_BASE}${path}`, { ...options, headers })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || 'API error')
  }
  return res.json()
}
```

**Step 2: Criar AuthProvider.jsx**

```jsx
import { createContext, useContext, useState, useEffect } from 'react'
import { getToken, setToken, removeToken } from '../../api'

const AuthContext = createContext(null)

export function useAuth() {
  return useContext(AuthContext)
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)

  useEffect(() => {
    const token = getToken()
    if (token) {
      try {
        const payload = JSON.parse(atob(token.split('.')[1]))
        if (payload.exp * 1000 > Date.now()) {
          setUser({ id: payload.sub, username: payload.username })
        } else {
          removeToken()
        }
      } catch { removeToken() }
    }
  }, [])

  function login(token, username) {
    setToken(token)
    const payload = JSON.parse(atob(token.split('.')[1]))
    setUser({ id: payload.sub, username })
  }

  function logout() {
    removeToken()
    setUser(null)
  }

  return (
    <AuthContext.Provider value={{ user, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}
```

**Step 3: Criar Login.jsx e Register.jsx**

Login.jsx:
```jsx
import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { fetchCartola } from '../../api'
import { useAuth } from '../../components/cartola/AuthProvider'

export default function Login() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState(null)
  const { login } = useAuth()
  const navigate = useNavigate()

  async function handleSubmit(e) {
    e.preventDefault()
    setError(null)
    try {
      const data = await fetchCartola('/auth/login', {
        method: 'POST',
        body: JSON.stringify({ email, password }),
      })
      login(data.token, data.username)
      navigate('/cartola/portfolio')
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <div style={{ maxWidth: 400, margin: '40px auto' }}>
      <h1>Login CartolaCS</h1>
      {error && <div className="error-message">{error}</div>}
      <form onSubmit={handleSubmit}>
        <input type="email" placeholder="Email" value={email} onChange={e => setEmail(e.target.value)} required style={{ width: '100%', padding: 8, marginBottom: 12 }} />
        <input type="password" placeholder="Senha" value={password} onChange={e => setPassword(e.target.value)} required style={{ width: '100%', padding: 8, marginBottom: 12 }} />
        <button type="submit" style={{ width: '100%', padding: 10 }}>Entrar</button>
      </form>
      <p style={{ marginTop: 16, color: 'var(--text-secondary)' }}>
        Nao tem conta? <Link to="/cartola/register">Cadastre-se</Link>
      </p>
    </div>
  )
}
```

Register.jsx:
```jsx
import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { fetchCartola } from '../../api'
import { useAuth } from '../../components/cartola/AuthProvider'

export default function Register() {
  const [username, setUsername] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState(null)
  const { login } = useAuth()
  const navigate = useNavigate()

  async function handleSubmit(e) {
    e.preventDefault()
    setError(null)
    try {
      const data = await fetchCartola('/auth/register', {
        method: 'POST',
        body: JSON.stringify({ username, email, password }),
      })
      login(data.token, data.username)
      navigate('/cartola/portfolio')
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <div style={{ maxWidth: 400, margin: '40px auto' }}>
      <h1>Cadastro CartolaCS</h1>
      {error && <div className="error-message">{error}</div>}
      <form onSubmit={handleSubmit}>
        <input type="text" placeholder="Username" value={username} onChange={e => setUsername(e.target.value)} required style={{ width: '100%', padding: 8, marginBottom: 12 }} />
        <input type="email" placeholder="Email" value={email} onChange={e => setEmail(e.target.value)} required style={{ width: '100%', padding: 8, marginBottom: 12 }} />
        <input type="password" placeholder="Senha" value={password} onChange={e => setPassword(e.target.value)} required style={{ width: '100%', padding: 8, marginBottom: 12 }} />
        <button type="submit" style={{ width: '100%', padding: 10 }}>Criar conta</button>
      </form>
      <p style={{ marginTop: 16, color: 'var(--text-secondary)' }}>
        Ja tem conta? <Link to="/cartola/login">Entrar</Link>
      </p>
    </div>
  )
}
```

**Step 4: Adicionar rotas no App.jsx**

Adicionar imports e rotas do Cartola dentro do Router.

**Step 5: Commit**

```bash
git add frontend/src/components/cartola/ frontend/src/pages/cartola/ frontend/src/api.js frontend/src/App.jsx
git commit -m "feat(cartola): add frontend auth (login, register, AuthProvider)"
```

---

### Task 8: Frontend — Market

**Files:**
- Create: `frontend/src/pages/cartola/Market.jsx`
- Create: `frontend/src/pages/cartola/PlayerMarket.jsx`
- Create: `frontend/src/components/cartola/PlayerMarketCard.jsx`
- Create: `frontend/src/components/cartola/PriceChart.jsx`

**Step 1: Instalar recharts**

```bash
cd /root/hltv/frontend && npm install recharts
```

**Step 2: Criar PlayerMarketCard.jsx**

Card com nickname, team, preco, variacao %, role badges.

**Step 3: Criar PriceChart.jsx**

Grafico de linha com recharts mostrando historico de precos.

**Step 4: Criar Market.jsx**

Lista de jogadores com filtro por role, sort, paginacao. Usa PlayerMarketCard.

**Step 5: Criar PlayerMarket.jsx**

Detalhe do jogador: PriceChart, stats, botao comprar (se logado).

**Step 6: Commit**

```bash
git add frontend/src/pages/cartola/ frontend/src/components/cartola/
git commit -m "feat(cartola): add market pages and price chart"
```

---

### Task 9: Frontend — Portfolio e Rankings

**Files:**
- Create: `frontend/src/pages/cartola/Portfolio.jsx`
- Create: `frontend/src/pages/cartola/TransactionHistory.jsx`
- Create: `frontend/src/pages/cartola/Ranking.jsx`
- Create: `frontend/src/components/cartola/PortfolioSlot.jsx`
- Create: `frontend/src/components/cartola/RankingTable.jsx`

**Step 1: Criar PortfolioSlot.jsx**

Card com jogador ou slot vazio, botao vender, lucro/prejuizo.

**Step 2: Criar Portfolio.jsx**

5 PortfolioSlots, saldo, patrimonio total, lucro. Botao vender em cada slot.

**Step 3: Criar TransactionHistory.jsx**

Lista de compras/vendas com data, preco, tipo.

**Step 4: Criar RankingTable.jsx**

Tabela com tabs (patrimonio, lucro, semanal).

**Step 5: Criar Ranking.jsx**

Pagina com RankingTable.

**Step 6: Adicionar todas as rotas no App.jsx**

**Step 7: Commit**

```bash
git add frontend/src/
git commit -m "feat(cartola): add portfolio, transaction history, and ranking pages"
```

---

### Task 10: Landing Page e Navbar

**Files:**
- Create: `frontend/src/pages/cartola/CartolaHome.jsx`
- Modify: `frontend/src/components/Navbar.jsx` (adicionar link CartolaCS)

**Step 1: Criar CartolaHome.jsx**

Landing page com:
- Top 10 ranking
- Top 5 valorizacoes do dia
- Top 5 desvalorizacoes do dia
- Botao "Entrar" / "Meu Portfolio"

**Step 2: Adicionar link na Navbar**

**Step 3: Build e deploy**

```bash
cd /root/hltv/frontend && npm run build && rm -rf /var/www/hltv && cp -r dist /var/www/hltv
```

**Step 4: Commit**

```bash
git add frontend/src/
git commit -m "feat(cartola): add landing page and navbar integration"
```

---

### Task 11: Deploy e teste E2E

**Step 1: Instalar dependencias Python**

```bash
pip install bcrypt PyJWT discord.py
```

**Step 2: Rodar init_db**

```bash
cd /root/hltv && python3 -c "from src.database import init_db; init_db()"
```

**Step 3: Inicializar mercado**

```bash
cd /root/hltv && python3 -c "from cartola.pricing import initialize_market; initialize_market()"
```

**Step 4: Restart do servico**

```bash
sudo systemctl restart hltv-api
```

**Step 5: Testar endpoints**

```bash
# Stats do mercado
curl -s https://gustavoscherer.com/hltv/api/cartola/market | python3 -m json.tool | head -20

# Registro
curl -s -X POST https://gustavoscherer.com/hltv/api/cartola/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"test","email":"test@test.com","password":"test123"}'

# Ranking
curl -s https://gustavoscherer.com/hltv/api/cartola/ranking
```

**Step 6: Build frontend**

```bash
cd /root/hltv/frontend && npm run build && rm -rf /var/www/hltv && cp -r dist /var/www/hltv
```

**Step 7: Commit final**

```bash
git add -A
git commit -m "feat(cartola): CartolaCS MVP complete — fantasy CS2 game"
```
