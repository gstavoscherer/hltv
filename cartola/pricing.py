"""
Motor de precificacao do CartolaCS.
Calcula precos iniciais e atualiza precos pos-partida.
"""

from src.database import session_scope
from src.database.models import (
    Player, Team, Match, MatchMap, MatchPlayerStats,
    PlayerMarket, PlayerPriceHistory,
)
from datetime import datetime, timedelta


# ============================================================================
# CONSTANTES
# ============================================================================

MAX_VARIATION_PER_MATCH = 0.15
MAX_VARIATION_PER_DAY = 0.20
MIN_PRICE = 1.0
MAX_PRICE = 200.0
DECAY_START_DAYS = 14
DECAY_RATE = 0.01
ROSTER_CRASH = 0.30

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

EVENT_WEIGHTS = {'major': 1.5, 'big': 1.2}
DEFAULT_EVENT_WEIGHT = 1.0

BO_WEIGHTS = {1: 0.7}
DEFAULT_BO_WEIGHT = 1.0

WIN_BONUS = 0.03
DEMAND_MAX = 0.03


# ============================================================================
# HELPERS
# ============================================================================

def _get_team_factor(world_rank):
    if world_rank is None:
        return DEFAULT_TEAM_FACTOR
    for threshold, factor in TEAM_RANK_FACTORS:
        if world_rank <= threshold:
            return factor
    return DEFAULT_TEAM_FACTOR


def _get_opponent_mult(world_rank):
    if world_rank is None:
        return DEFAULT_OPPONENT_MULT
    for threshold, mult in OPPONENT_MULT:
        if world_rank <= threshold:
            return mult
    return DEFAULT_OPPONENT_MULT


def _get_event_weight(event):
    if not event:
        return DEFAULT_EVENT_WEIGHT
    etype = (event.event_type or '').lower()
    if 'major' in etype:
        return EVENT_WEIGHTS['major']
    if 'big' in etype:
        return EVENT_WEIGHTS['big']
    return DEFAULT_EVENT_WEIGHT


def _get_bo_weight(best_of):
    return BO_WEIGHTS.get(best_of, DEFAULT_BO_WEIGHT)


def _clamp(value, min_val, max_val):
    return max(min_val, min(max_val, value))


def _get_player_team_in_match(player_id, match, session):
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
# PRECO INICIAL
# ============================================================================

def calculate_initial_price(player, team=None):
    rating = player.rating_2_0 or 1.0
    rank = team.world_rank if team else None
    team_factor = _get_team_factor(rank)
    price = team_factor * rating * 10
    return _clamp(round(price, 2), MIN_PRICE, MAX_PRICE)


def initialize_market():
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
# SHORT TERM
# ============================================================================

def calculate_short_term(player_id, match, session):
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
    player_team_id = _get_player_team_in_match(player_id, match, session)
    if match.team1_id == player_team_id:
        opponent_id = match.team2_id
    else:
        opponent_id = match.team1_id
    opponent = session.query(Team).get(opponent_id) if opponent_id else None
    opp_mult = _get_opponent_mult(opponent.world_rank if opponent else None)

    event_w = _get_event_weight(match.event)
    bo_w = _get_bo_weight(match.best_of)

    if match.winner_id and match.winner_id == player_team_id:
        w_bonus = WIN_BONUS
    elif match.winner_id:
        w_bonus = -WIN_BONUS
    else:
        w_bonus = 0.0

    return base_perf * opp_mult * event_w * bo_w + w_bonus


# ============================================================================
# MID TERM
# ============================================================================

def calculate_mid_term(player_id, session, exclude_match_id=None):
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
        .limit(MID_TERM_MATCH_COUNT + 1)
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
# LONG TERM
# ============================================================================

def calculate_long_term(player_id, current_price, session):
    player = session.query(Player).get(player_id)
    if not player or current_price <= 0:
        return 0.0

    team = session.query(Team).get(player.current_team_id) if player.current_team_id else None
    fair = calculate_initial_price(player, team)
    return (fair - current_price) / current_price * 0.1


# ============================================================================
# UPDATE PRINCIPAL
# ============================================================================

def update_player_price(player_id, match, session):
    market = session.query(PlayerMarket).get(player_id)
    if not market:
        return

    current = market.current_price

    short = calculate_short_term(player_id, match, session)
    mid = calculate_mid_term(player_id, session, exclude_match_id=match.id)
    long = calculate_long_term(player_id, current, session)

    variation = (
        SHORT_TERM_WEIGHT * short
        + MID_TERM_WEIGHT * mid
        + LONG_TERM_WEIGHT * long
    )

    variation = _clamp(variation, -MAX_VARIATION_PER_MATCH, MAX_VARIATION_PER_MATCH)

    # Cap diario
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today_first = (
        session.query(PlayerPriceHistory)
        .filter(
            PlayerPriceHistory.player_id == player_id,
            PlayerPriceHistory.timestamp >= today_start,
        )
        .order_by(PlayerPriceHistory.timestamp.asc())
        .first()
    )
    if today_first:
        day_start_price = today_first.price
        projected = current * (1 + variation)
        day_change = (projected - day_start_price) / day_start_price if day_start_price > 0 else 0
        if abs(day_change) > MAX_VARIATION_PER_DAY:
            max_p = day_start_price * (1 + MAX_VARIATION_PER_DAY)
            min_p = day_start_price * (1 - MAX_VARIATION_PER_DAY)
            projected = _clamp(projected, min_p, max_p)
            variation = (projected - current) / current if current > 0 else 0

    new_price = _clamp(round(current * (1 + variation), 2), MIN_PRICE, MAX_PRICE)

    market.previous_price = current
    market.current_price = new_price
    market.price_change_pct = round(variation * 100, 2)
    market.last_updated = datetime.utcnow()

    session.add(PlayerPriceHistory(
        player_id=player_id,
        price=new_price,
        match_id=match.id,
    ))


def update_prices_for_match(match_id):
    with session_scope() as s:
        match = s.query(Match).get(match_id)
        if not match:
            return

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
    with session_scope() as s:
        cutoff = datetime.utcnow() - timedelta(days=DECAY_START_DAYS)
        markets = s.query(PlayerMarket).filter(PlayerMarket.last_updated < cutoff).all()
        count = 0
        for m in markets:
            days_inactive = (datetime.utcnow() - m.last_updated).days - DECAY_START_DAYS
            if days_inactive <= 0:
                continue
            decay = DECAY_RATE * days_inactive
            new_price = _clamp(round(m.current_price * (1 - decay), 2), MIN_PRICE, MAX_PRICE)
            m.previous_price = m.current_price
            m.current_price = new_price
            m.price_change_pct = round(-decay * 100, 2)
            count += 1
        if count:
            print(f"Decay aplicado: {count} jogadores")


def apply_roster_crash(player_id):
    with session_scope() as s:
        market = s.query(PlayerMarket).get(player_id)
        if not market:
            return
        new_price = _clamp(round(market.current_price * (1 - ROSTER_CRASH), 2), MIN_PRICE, MAX_PRICE)
        market.previous_price = market.current_price
        market.current_price = new_price
        market.price_change_pct = round(-ROSTER_CRASH * 100, 2)
        market.last_updated = datetime.utcnow()
        s.add(PlayerPriceHistory(player_id=player_id, price=new_price))
        print(f"Roster crash: jogador {player_id} -> {new_price}")
