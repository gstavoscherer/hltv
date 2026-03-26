"""
Motor de precificacao do CartolaCS.
Calcula precos iniciais e atualiza precos pos-partida.
"""

import math

from src.database import session_scope
from src.database.models import (
    Player, Team, Match, MatchMap, MatchPlayerStats,
    PlayerMarket, PlayerPriceHistory, PlayerRole,
    EventTeam, TeamPlayer,
)
from sqlalchemy import or_, func
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

DEFAULT_TEAM_FACTOR = 1.0
DEFAULT_OPPONENT_MULT = 0.8

EVENT_WEIGHTS = {'major': 1.5, 'big': 1.2}
DEFAULT_EVENT_WEIGHT = 1.0

BO_WEIGHTS = {1: 0.7}
DEFAULT_BO_WEIGHT = 1.0

WIN_BONUS = 0.03
DEMAND_MAX = 0.03

IGL_BASE_BONUS = 0.08
IGL_MAX_BONUS = 0.20

MIN_PLAYERS_FOR_ZSCORE = 20

ROLE_WEIGHTS = {
    'default': {'rating': 0.35, 'impact': 0.20, 'kast': 0.15, 'adr': 0.15, 'kd': 0.15},
    'awp':     {'rating': 0.40, 'impact': 0.20, 'kast': 0.15, 'adr': 0.10, 'kd': 0.15},
    'entry':   {'rating': 0.30, 'impact': 0.30, 'kast': 0.15, 'adr': 0.15, 'kd': 0.10},
    'rifler':  {'rating': 0.35, 'impact': 0.20, 'kast': 0.15, 'adr': 0.15, 'kd': 0.15},
    'lurker':  {'rating': 0.30, 'impact': 0.20, 'kast': 0.20, 'adr': 0.15, 'kd': 0.15},
    'support': {'rating': 0.30, 'impact': 0.15, 'kast': 0.25, 'adr': 0.15, 'kd': 0.15},
}

# Cache for stats distribution (reset per session_scope call)
_stats_cache = {}


# ============================================================================
# HELPERS
# ============================================================================

def _get_team_factor(world_rank):
    """Formula continua: rank 1 = 1.35, rank 5 = 1.18, rank 10 = 1.12, rank 30 = 1.05.
    f(rank) = 1.0 + 0.35 * (1/rank)^0.35 — bonus relevante mas nao dominante."""
    if world_rank is None:
        return DEFAULT_TEAM_FACTOR
    if world_rank < 1:
        world_rank = 1
    factor = 1.0 + 0.35 * (1 / world_rank) ** 0.35
    return max(factor, DEFAULT_TEAM_FACTOR)


def _get_opponent_mult(world_rank):
    """Formula continua: rank 1 = 1.4x, rank 30 = 1.0x, rank 100 = 0.75x.
    Baseado em interpolacao linear por faixas."""
    if world_rank is None:
        return DEFAULT_OPPONENT_MULT
    if world_rank <= 30:
        # rank 1 -> 1.4, rank 30 -> 1.0
        return 1.4 - (world_rank - 1) * (0.4 / 29)
    elif world_rank <= 100:
        # rank 30 -> 1.0, rank 100 -> 0.75
        return 1.0 - (world_rank - 30) * (0.25 / 70)
    else:
        return 0.75


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

def _get_stats_distribution(session):
    """Calcula mean/stdev de cada stat a partir de todos os jogadores no banco.
    Resultado cacheado por id(session) pra evitar queries repetidas."""
    global _stats_cache
    cache_key = id(session)
    if cache_key in _stats_cache:
        return _stats_cache[cache_key]

    stats = ['rating_2_0', 'impact', 'kast', 'adr', 'kd_ratio']
    result = {}

    for stat_name in stats:
        col = getattr(Player, stat_name)
        row = session.query(
            func.count(col),
            func.avg(col),
        ).filter(col.isnot(None)).first()

        count = row[0] or 0
        mean = float(row[1]) if row[1] is not None else 0.0

        if count >= MIN_PLAYERS_FOR_ZSCORE:
            # Calculate stdev manually: sqrt(avg((x - mean)^2))
            variance_row = session.query(
                func.avg((col - mean) * (col - mean))
            ).filter(col.isnot(None)).first()
            variance = float(variance_row[0]) if variance_row[0] is not None else 0.0
            stdev = math.sqrt(variance) if variance > 0 else 0.0
        else:
            stdev = 0.0

        result[stat_name] = {'mean': mean, 'stdev': stdev, 'count': count}

    _stats_cache[cache_key] = result
    return result


def _get_player_role_weights(player_id, session):
    """Retorna weight profile baseado na role primaria do jogador."""
    if not session:
        return ROLE_WEIGHTS['default']

    role_row = session.query(PlayerRole).filter_by(
        player_id=player_id, is_primary=True
    ).first()

    if not role_row:
        # Fallback: pega qualquer role que nao seja IGL
        role_row = session.query(PlayerRole).filter(
            PlayerRole.player_id == player_id,
            PlayerRole.role != 'igl',
        ).first()

    if not role_row:
        return ROLE_WEIGHTS['default']

    role_key = role_row.role.lower()
    return ROLE_WEIGHTS.get(role_key, ROLE_WEIGHTS['default'])


def _individual_score_fallback(player):
    """Fallback: normalizacao antiga pra quando nao tem dados suficientes."""
    rating = player.rating_2_0 or 1.0
    impact = player.impact or 1.0
    kast = (player.kast or 70.0) / 70.0
    adr = (player.adr or 75.0) / 75.0
    kd = player.kd_ratio or 1.0

    return (
        0.35 * rating
        + 0.20 * impact
        + 0.15 * kast
        + 0.15 * adr
        + 0.15 * kd
    )


def _individual_score(player, session=None):
    """Score individual baseado em z-score normalization com role-aware weights.
    Calcula z-score de cada stat usando distribuicao de todos os jogadores no banco.
    Resultado ~1.0 pra jogador mediano, ~1.3 pra elite (2 sigma), ~0.7 pra ruim."""
    if not session:
        return _individual_score_fallback(player)

    dist = _get_stats_distribution(session)

    # Checa se tem dados suficientes pra z-score
    has_enough = all(
        dist[s]['count'] >= MIN_PLAYERS_FOR_ZSCORE and dist[s]['stdev'] > 0
        for s in dist
    )
    if not has_enough:
        return _individual_score_fallback(player)

    # Calcula z-scores
    raw = {
        'rating': player.rating_2_0 or 1.0,
        'impact': player.impact or 1.0,
        'kast': player.kast or 70.0,
        'adr': player.adr or 75.0,
        'kd': player.kd_ratio or 1.0,
    }
    stat_map = {
        'rating': 'rating_2_0',
        'impact': 'impact',
        'kast': 'kast',
        'adr': 'adr',
        'kd': 'kd_ratio',
    }

    zscores = {}
    for key, db_col in stat_map.items():
        d = dist[db_col]
        zscores[key] = (raw[key] - d['mean']) / d['stdev']

    # Role-aware weights
    weights = _get_player_role_weights(player.id, session)

    weighted_zscore = sum(weights[key] * zscores[key] for key in weights)

    # Final score: ~1.0 average, ~1.3 elite (2 sigma), ~0.7 bad (-2 sigma)
    return 1.0 + 0.15 * weighted_zscore


def _get_igl_bonus(player_id, team, session):
    """Bonus pra IGLs baseado em performance do time que lidera.
    Componentes:
      - Round win rate (40%): % de rounds ganhos nos matches
      - Match win rate (30%): % de matches ganhos
      - Event placements (30%): top 1 = 1.0, top 3 = 0.6, top 8 = 0.3
    Retorna multiplicador entre IGL_BASE_BONUS e IGL_MAX_BONUS."""
    is_igl = session.query(PlayerRole).filter_by(
        player_id=player_id, role='igl'
    ).first()
    if not is_igl:
        return 0.0
    if not team:
        return IGL_BASE_BONUS

    tid = team.id
    score = 0.0

    # Round win rate
    maps_as_t1 = (session.query(
        func.coalesce(func.sum(MatchMap.team1_score), 0),
        func.coalesce(func.sum(MatchMap.team2_score), 0),
    ).join(Match).filter(Match.team1_id == tid).first())

    maps_as_t2 = (session.query(
        func.coalesce(func.sum(MatchMap.team2_score), 0),
        func.coalesce(func.sum(MatchMap.team1_score), 0),
    ).join(Match).filter(Match.team2_id == tid).first())

    rounds_won = maps_as_t1[0] + maps_as_t2[0]
    rounds_total = rounds_won + maps_as_t1[1] + maps_as_t2[1]

    if rounds_total > 0:
        rwr = rounds_won / rounds_total
        # 50% = 0.0, 55% = 0.5, 60%+ = 1.0
        rwr_score = _clamp((rwr - 0.50) / 0.10, 0.0, 1.0)
    else:
        rwr_score = 0.0

    # Match win rate
    total_matches = session.query(Match).filter(
        or_(Match.team1_id == tid, Match.team2_id == tid)
    ).count()
    wins = session.query(Match).filter(Match.winner_id == tid).count()

    if total_matches > 0:
        mwr = wins / total_matches
        # 50% = 0.0, 65% = 0.5, 80%+ = 1.0
        mwr_score = _clamp((mwr - 0.50) / 0.30, 0.0, 1.0)
    else:
        mwr_score = 0.0

    # Event placements
    placements = (session.query(EventTeam)
        .filter_by(team_id=tid)
        .filter(EventTeam.placement != None)
        .all())

    if placements:
        placement_points = 0.0
        for p in placements:
            if p.placement == 1:
                placement_points += 1.0
            elif p.placement <= 3:
                placement_points += 0.6
            elif p.placement <= 8:
                placement_points += 0.3
        # Normaliza: avg de pontos por evento, cap em 1.0
        evt_score = _clamp(placement_points / len(placements), 0.0, 1.0)
    else:
        evt_score = 0.0

    # Score combinado (0.0 a 1.0)
    combined = 0.40 * rwr_score + 0.30 * mwr_score + 0.30 * evt_score

    return IGL_BASE_BONUS + combined * (IGL_MAX_BONUS - IGL_BASE_BONUS)


def calculate_initial_price(player, team=None, session=None):
    """Preco = individual_score^1.5 * (1 + igl_bonus) * team_factor * base.
    IGLs recebem bonus baseado em performance do time (win rates, placements)."""
    ind = _individual_score(player, session=session)
    rank = team.world_rank if team else None
    team_factor = _get_team_factor(rank)

    igl_bonus = 0.0
    if session:
        igl_bonus = _get_igl_bonus(player.id, team, session)

    price = (ind ** 1.5) * (1 + igl_bonus) * team_factor * 38
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

            price = calculate_initial_price(p, team, session=s)
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
    fair = calculate_initial_price(player, team, session=session)
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
