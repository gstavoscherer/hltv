#!/usr/bin/env python3
"""
Atualiza rankings HLTV de todos os times e recalcula precos do CartolaCS.
"""

import logging
from datetime import date

from src.database import init_db, session_scope
from src.database.models import Team, Player, PlayerMarket, PlayerPriceHistory, TeamRankingHistory
from src.scrapers.rankings import scrape_rankings
from cartola.pricing import calculate_initial_price, _clamp, MIN_PRICE, MAX_PRICE

logger = logging.getLogger(__name__)


def update_rankings(date_str=None, headless=True):
    """Atualiza world_rank de todos os times com o ranking HLTV."""
    rankings = scrape_rankings(date_str=date_str, headless=headless)
    if not rankings:
        print("Nenhum ranking encontrado.")
        return []

    updated = 0
    not_found = []

    with session_scope() as s:
        # Reset all ranks first (times que sairam do ranking)
        s.query(Team).update({Team.world_rank: None})

        for r in rankings:
            team = None
            # Tentar por ID primeiro
            if r['team_id']:
                team = s.query(Team).filter_by(id=r['team_id']).first()
            # Fallback por nome
            if not team:
                team = s.query(Team).filter(Team.name.ilike(r['team_name'])).first()

            if team:
                old_rank = team.world_rank
                team.world_rank = r['rank']
                if old_rank != r['rank']:
                    updated += 1

                # Save ranking history (upsert to avoid duplicates on team_id + date)
                existing_hist = (
                    s.query(TeamRankingHistory)
                    .filter_by(team_id=team.id, date=date.today())
                    .first()
                )
                if existing_hist:
                    existing_hist.rank = r['rank']
                    existing_hist.points = r.get('points')
                else:
                    s.add(TeamRankingHistory(
                        team_id=team.id,
                        rank=r['rank'],
                        points=r.get('points'),
                        date=date.today(),
                    ))
            else:
                not_found.append(f"#{r['rank']} {r['team_name']} (ID: {r['team_id']})")

    print(f"\nRankings atualizados: {updated} times mudaram de posicao")
    if not_found and len(not_found) <= 10:
        print(f"Times nao encontrados no banco ({len(not_found)}):")
        for t in not_found:
            print(f"  - {t}")
    elif not_found:
        print(f"  {len(not_found)} times do ranking nao estao no banco (normal, sao times menores)")

    return rankings


def recalculate_all_prices():
    """Recalcula precos de todos os jogadores baseado nos novos rankings."""
    with session_scope() as s:
        markets = s.query(PlayerMarket).all()
        changed = 0

        for market in markets:
            player = s.query(Player).get(market.player_id)
            if not player:
                continue

            team = s.query(Team).get(player.current_team_id) if player.current_team_id else None
            new_fair_price = calculate_initial_price(player, team, session=s)
            old_price = market.current_price

            # Ajustar preco: mover 20% em direcao ao novo fair price
            diff = new_fair_price - old_price
            adjustment = diff * 0.20
            new_price = _clamp(round(old_price + adjustment, 2), MIN_PRICE, MAX_PRICE)

            if abs(new_price - old_price) >= 0.01:
                market.previous_price = old_price
                market.current_price = new_price
                market.price_change_pct = round((new_price - old_price) / old_price * 100, 2)
                s.add(PlayerPriceHistory(player_id=player.id, price=new_price))
                changed += 1

        print(f"Precos recalculados: {changed} jogadores tiveram preco ajustado")


def main():
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    init_db()

    print("=== ATUALIZANDO RANKINGS HLTV ===\n")
    update_rankings(headless=False)

    print("\n=== RECALCULANDO PRECOS ===\n")
    recalculate_all_prices()

    # Mostrar top 10 precos apos recalculo
    with session_scope() as s:
        top = (
            s.query(PlayerMarket, Player)
            .join(Player, PlayerMarket.player_id == Player.id)
            .order_by(PlayerMarket.current_price.desc())
            .limit(10)
            .all()
        )
        print("\nTop 10 jogadores apos recalculo:")
        for m, p in top:
            team = s.query(Team).get(p.current_team_id) if p.current_team_id else None
            rank = team.world_rank if team else None
            print(f"  {p.nickname:15s} | {m.current_price:6.2f} ({m.price_change_pct:+.2f}%) | {team.name if team else 'N/A':15s} #{rank or '?'}")


if __name__ == '__main__':
    main()
