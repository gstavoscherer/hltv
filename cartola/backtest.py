"""
Backtest do motor de precificacao CartolaCS.

Simula evolucao de precos usando dados historicos de partidas.
NAO modifica o banco — precos sao mantidos em memoria.

Uso:
    python3 cartola/backtest.py
"""

import sys
import os
import statistics
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database import session_scope
from src.database.models import (
    Player, Team, Match, MatchMap, MatchPlayerStats,
)
from cartola.pricing import (
    calculate_initial_price, calculate_short_term,
    SHORT_TERM_WEIGHT, MID_TERM_WEIGHT, LONG_TERM_WEIGHT,
    MAX_VARIATION_PER_MATCH, MIN_PRICE, MAX_PRICE,
    MID_TERM_MATCH_COUNT, MID_TERM_WEIGHTS,
)


def _clamp(value, min_val, max_val):
    return max(min_val, min(max_val, value))


def _get_players_in_match(match_id, session):
    """Retorna set de player_ids que jogaram nessa partida."""
    rows = (
        session.query(MatchPlayerStats.player_id)
        .join(MatchMap, MatchPlayerStats.map_id == MatchMap.id)
        .filter(MatchMap.match_id == match_id)
        .distinct()
        .all()
    )
    return {pid for (pid,) in rows}


def _sim_mid_term(player_id, match_history, session):
    """Calcula mid-term usando historico simulado (ultimas N partidas do jogador).
    match_history: lista de Match objects ja processados para esse jogador, ordem cronologica."""
    recent = list(reversed(match_history))[:MID_TERM_MATCH_COUNT]
    if not recent:
        return 0.0

    total_weight = 0.0
    weighted_sum = 0.0
    for i, m in enumerate(recent):
        w = MID_TERM_WEIGHTS[i] if i < len(MID_TERM_WEIGHTS) else 0.1
        st = calculate_short_term(player_id, m, session)
        weighted_sum += st * w
        total_weight += w

    return weighted_sum / total_weight if total_weight > 0 else 0.0


def _sim_long_term(player_id, current_price, session):
    """Calcula long-term: pullback em direcao ao preco justo."""
    player = session.query(Player).get(player_id)
    if not player or current_price <= 0:
        return 0.0
    team = session.query(Team).get(player.current_team_id) if player.current_team_id else None
    fair = calculate_initial_price(player, team, session=session)
    return (fair - current_price) / current_price * 0.1


def run_backtest():
    with session_scope() as session:
        # 1) Carregar matches ordenadas por data
        matches = (
            session.query(Match)
            .order_by(Match.date.asc().nullslast(), Match.id.asc())
            .all()
        )
        if not matches:
            print("Nenhuma partida encontrada no banco.")
            return

        # 2) Inicializar precos de todos os jogadores
        players = session.query(Player).all()
        if not players:
            print("Nenhum jogador encontrado no banco.")
            return

        # prices[player_id] = current price
        prices = {}
        initial_prices = {}
        player_names = {}

        for p in players:
            team = session.query(Team).get(p.current_team_id) if p.current_team_id else None
            price = calculate_initial_price(p, team, session=session)
            prices[p.id] = price
            initial_prices[p.id] = price
            player_names[p.id] = p.nickname

        print(f"Jogadores inicializados: {len(prices)}")
        print(f"Partidas a processar:    {len(matches)}")
        print()

        # 3) Iterar matches cronologicamente
        # Tracking: historico de precos e matches por jogador
        price_history = defaultdict(list)  # player_id -> [(match_id, price)]
        player_match_history = defaultdict(list)  # player_id -> [Match, ...]
        match_count = 0

        for match in matches:
            player_ids = _get_players_in_match(match.id, session)
            if not player_ids:
                continue

            match_count += 1

            for pid in player_ids:
                if pid not in prices:
                    # Jogador novo que nao estava no set inicial — inicializar
                    p = session.query(Player).get(pid)
                    if not p:
                        continue
                    team = session.query(Team).get(p.current_team_id) if p.current_team_id else None
                    price = calculate_initial_price(p, team, session=session)
                    prices[pid] = price
                    initial_prices[pid] = price
                    player_names[pid] = p.nickname

                current = prices[pid]

                # Short term: performance nessa partida
                short = calculate_short_term(pid, match, session)

                # Mid term: media ponderada das ultimas partidas (do historico simulado)
                mid = _sim_mid_term(pid, player_match_history[pid], session)

                # Long term: pullback ao preco justo
                long = _sim_long_term(pid, current, session)

                # Variacao combinada
                variation = (
                    SHORT_TERM_WEIGHT * short
                    + MID_TERM_WEIGHT * mid
                    + LONG_TERM_WEIGHT * long
                )
                variation = _clamp(variation, -MAX_VARIATION_PER_MATCH, MAX_VARIATION_PER_MATCH)

                new_price = _clamp(round(current * (1 + variation), 2), MIN_PRICE, MAX_PRICE)
                prices[pid] = new_price
                price_history[pid].append((match.id, new_price))
                player_match_history[pid].append(match)

        print(f"Partidas processadas:    {match_count}")
        print()

        # 4) Gerar relatorio
        _print_report(prices, initial_prices, price_history, player_names)


def _print_report(prices, initial_prices, price_history, player_names):
    """Imprime relatorio completo do backtest."""

    # Filtrar apenas jogadores que participaram de pelo menos 1 match
    active_players = {pid for pid in price_history if price_history[pid]}
    if not active_players:
        print("Nenhum jogador ativo com historico de precos.")
        return

    # --- Top 20 por preco final ---
    print("=" * 70)
    print(" TOP 20 JOGADORES POR PRECO FINAL")
    print("=" * 70)
    sorted_by_price = sorted(
        active_players, key=lambda pid: prices[pid], reverse=True
    )
    print(f"{'#':<4} {'Jogador':<20} {'Inicial':>10} {'Final':>10} {'Var%':>10}")
    print("-" * 54)
    for i, pid in enumerate(sorted_by_price[:20], 1):
        ini = initial_prices[pid]
        fin = prices[pid]
        var = ((fin - ini) / ini * 100) if ini > 0 else 0
        print(f"{i:<4} {player_names.get(pid, str(pid)):<20} {ini:>10.2f} {fin:>10.2f} {var:>+9.1f}%")

    # --- Top 10 maiores valorizacoes ---
    pct_changes = {}
    for pid in active_players:
        ini = initial_prices[pid]
        if ini > 0:
            pct_changes[pid] = (prices[pid] - ini) / ini * 100

    print()
    print("=" * 70)
    print(" TOP 10 MAIORES VALORIZACOES (% desde inicio)")
    print("=" * 70)
    gainers = sorted(pct_changes, key=lambda pid: pct_changes[pid], reverse=True)
    print(f"{'#':<4} {'Jogador':<20} {'Inicial':>10} {'Final':>10} {'Var%':>10}")
    print("-" * 54)
    for i, pid in enumerate(gainers[:10], 1):
        ini = initial_prices[pid]
        fin = prices[pid]
        print(f"{i:<4} {player_names.get(pid, str(pid)):<20} {ini:>10.2f} {fin:>10.2f} {pct_changes[pid]:>+9.1f}%")

    # --- Top 10 maiores quedas ---
    print()
    print("=" * 70)
    print(" TOP 10 MAIORES QUEDAS (% desde inicio)")
    print("=" * 70)
    losers = sorted(pct_changes, key=lambda pid: pct_changes[pid])
    print(f"{'#':<4} {'Jogador':<20} {'Inicial':>10} {'Final':>10} {'Var%':>10}")
    print("-" * 54)
    for i, pid in enumerate(losers[:10], 1):
        ini = initial_prices[pid]
        fin = prices[pid]
        print(f"{i:<4} {player_names.get(pid, str(pid)):<20} {ini:>10.2f} {fin:>10.2f} {pct_changes[pid]:>+9.1f}%")

    # --- Distribuicao de precos ---
    all_final = [prices[pid] for pid in active_players]
    print()
    print("=" * 70)
    print(" DISTRIBUICAO DE PRECOS FINAIS")
    print("=" * 70)
    print(f"  Jogadores ativos: {len(all_final)}")
    print(f"  Media:            {statistics.mean(all_final):.2f}")
    print(f"  Mediana:          {statistics.median(all_final):.2f}")
    if len(all_final) >= 2:
        print(f"  Desvio padrao:    {statistics.stdev(all_final):.2f}")
    print(f"  Minimo:           {min(all_final):.2f}")
    print(f"  Maximo:           {max(all_final):.2f}")

    # --- Volatilidade ---
    print()
    print("=" * 70)
    print(" VOLATILIDADE (media de |variacao%| por match)")
    print("=" * 70)

    vol_per_player = {}
    for pid in active_players:
        history = price_history[pid]
        if len(history) < 2:
            continue
        changes = []
        prev = initial_prices[pid]
        for _, p in history:
            if prev > 0:
                changes.append(abs((p - prev) / prev * 100))
            prev = p
        if changes:
            vol_per_player[pid] = statistics.mean(changes)

    if vol_per_player:
        all_vols = list(vol_per_player.values())
        print(f"  Jogadores com 2+ matches: {len(vol_per_player)}")
        print(f"  Volatilidade media:       {statistics.mean(all_vols):.2f}%")
        print(f"  Volatilidade mediana:     {statistics.median(all_vols):.2f}%")
        if len(all_vols) >= 2:
            print(f"  Desvio padrao vol:        {statistics.stdev(all_vols):.2f}%")

        # Top 5 mais volateis
        print()
        print("  Top 5 mais volateis:")
        top_vol = sorted(vol_per_player, key=lambda pid: vol_per_player[pid], reverse=True)
        for i, pid in enumerate(top_vol[:5], 1):
            print(f"    {i}. {player_names.get(pid, str(pid)):<20} {vol_per_player[pid]:.2f}% avg/match")

        # Top 5 menos volateis
        print()
        print("  Top 5 menos volateis:")
        bot_vol = sorted(vol_per_player, key=lambda pid: vol_per_player[pid])
        for i, pid in enumerate(bot_vol[:5], 1):
            print(f"    {i}. {player_names.get(pid, str(pid)):<20} {vol_per_player[pid]:.2f}% avg/match")
    else:
        print("  Dados insuficientes para calcular volatilidade.")

    print()
    print("=" * 70)
    print(" BACKTEST CONCLUIDO")
    print("=" * 70)


if __name__ == '__main__':
    run_backtest()
