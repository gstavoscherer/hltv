#!/usr/bin/env python3
"""
Sync semanal: atualiza stats de carreira, rosters e rankings de todos os jogadores/times.
"""

import logging
import time
import traceback

from src.database import init_db, session_scope
from src.database.models import Player, Team, TeamPlayer
from src.scrapers.players import scrape_player
from src.scrapers.teams import scrape_team
from src.scrapers.selenium_helpers import DriverPool
from cartola.pricing import initialize_market
from cartola.tasks import weekly_maintenance

logger = logging.getLogger(__name__)


def update_all_player_stats(headless=True):
    """Atualiza stats de carreira de todos os jogadores."""
    with session_scope() as s:
        player_ids = [p.id for p in s.query(Player.id).all()]

    print(f"Atualizando stats de {len(player_ids)} jogadores...")

    with DriverPool(size=1, headless=headless) as pool:
        for i, pid in enumerate(player_ids, 1):
            if i % 50 == 0:
                print(f"  Progresso: {i}/{len(player_ids)}")

            driver = pool.checkout()
            try:
                stats = scrape_player(pid, headless=headless, max_retries=2, driver=driver)
                pool.checkin(driver)

                if stats:
                    with session_scope() as s:
                        player = s.query(Player).filter_by(id=pid).first()
                        if player:
                            for key, value in stats.items():
                                if hasattr(player, key):
                                    setattr(player, key, value)
            except Exception as e:
                pool.mark_bad(driver)
                pool.checkin(driver)
                logger.warning("Erro ao atualizar jogador %d: %s", pid, e)

    print(f"  {len(player_ids)} jogadores atualizados.")


def update_all_teams(headless=True):
    """Atualiza info e roster de todos os times."""
    with session_scope() as s:
        team_ids = [t.id for t in s.query(Team.id).all()]

    print(f"Atualizando {len(team_ids)} times...")

    with DriverPool(size=1, headless=headless) as pool:
        for i, tid in enumerate(team_ids, 1):
            if i % 20 == 0:
                print(f"  Progresso: {i}/{len(team_ids)}")

            driver = pool.checkout()
            try:
                team_data = scrape_team(tid, headless=headless, driver=driver)
                pool.checkin(driver)

                if team_data:
                    with session_scope() as s:
                        team = s.query(Team).filter_by(id=tid).first()
                        if team:
                            if 'name' in team_data:
                                team.name = team_data['name']
                            if 'country' in team_data:
                                team.country = team_data['country']
                            if 'world_rank' in team_data:
                                team.world_rank = team_data['world_rank']
            except Exception as e:
                pool.mark_bad(driver)
                pool.checkin(driver)
                logger.warning("Erro ao atualizar time %d: %s", tid, e)

    print(f"  {len(team_ids)} times atualizados.")


def main():
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    init_db()

    print("=== SYNC SEMANAL ===\n")

    # 1. Atualizar times (rankings + rosters)
    print("1. Atualizando times e rankings...")
    update_all_teams(headless=True)

    # 2. Atualizar stats de jogadores
    print("\n2. Atualizando stats de jogadores...")
    update_all_player_stats(headless=True)

    # 3. Inicializar mercado pra jogadores novos
    print("\n3. Inicializando mercado pra jogadores novos...")
    initialize_market()

    # 4. Recalcular fair prices
    print("\n4. Manutencao semanal CartolaCS...")
    weekly_maintenance()

    print("\n=== SYNC SEMANAL CONCLUIDO ===")


if __name__ == '__main__':
    main()
