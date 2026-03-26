#!/usr/bin/env python3
"""
Sync diario: novos eventos (ultimos 30 dias) + decay do CartolaCS.
"""

import logging
from datetime import date, timedelta

from src.database import init_db, session_scope
from src.database.models import Event
from sync_events_archive import scrape_archive_events
from sync_all import sync_full_event
from cartola.tasks import daily_maintenance
from cartola.pricing import initialize_market

logger = logging.getLogger(__name__)


def sync_new_events():
    """Busca eventos novos dos ultimos 30 dias."""
    init_db()

    end_date = date.today().isoformat()
    start_date = (date.today() - timedelta(days=30)).isoformat()

    events = scrape_archive_events(start_date, end_date, headless=True)
    if not events:
        print("Nenhum evento novo encontrado.")
        return

    # Filtrar os que ja existem
    with session_scope() as s:
        existing_ids = {e.id for e in s.query(Event.id).all()}
    new_events = [e for e in events if e['id'] not in existing_ids]

    if not new_events:
        print(f"{len(events)} eventos encontrados, todos ja no banco.")
        return

    print(f"{len(new_events)} eventos novos para syncar:")
    for evt in new_events:
        print(f"  - {evt['name']} (ID: {evt['id']})")

        with session_scope() as s:
            if not s.query(Event).filter_by(id=evt['id']).first():
                s.add(Event(id=evt['id'], name=evt['name']))

        try:
            sync_full_event(evt['id'], headless=True, team_workers=1, player_workers=1)
        except Exception as e:
            logger.error("Erro no evento %d: %s", evt['id'], e)


def main():
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

    print("=== SYNC DIARIO ===\n")

    # 1. Novos eventos
    print("1. Buscando eventos novos...")
    sync_new_events()

    # 2. Inicializar mercado pra jogadores novos
    print("\n2. Inicializando mercado pra jogadores novos...")
    initialize_market()

    # 3. Decay do CartolaCS
    print("\n3. Aplicando decay do CartolaCS...")
    daily_maintenance()

    print("\n=== SYNC DIARIO CONCLUIDO ===")


if __name__ == '__main__':
    main()
