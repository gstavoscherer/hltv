#!/usr/bin/env python3
"""
Sync matches de eventos ativos (em andamento).
Detecta eventos com start_date <= hoje <= end_date e synca matches.
"""

import logging
from datetime import date

from src.database import init_db, session_scope
from src.database.models import Event, Match
from src.scrapers.matches import scrape_event_matches, scrape_match_detail, scrape_map_stats
from src.scrapers.selenium_helpers import create_driver, wait_for_cloudflare, random_delay
from sync_all import sync_full_event

logger = logging.getLogger(__name__)


def get_active_events():
    """Retorna eventos em andamento (start_date <= hoje <= end_date)."""
    today = date.today()
    with session_scope() as s:
        events = (
            s.query(Event)
            .filter(Event.start_date <= today, Event.end_date >= today)
            .all()
        )
        return [{"id": e.id, "name": e.name} for e in events]


def main():
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    init_db()

    events = get_active_events()
    if not events:
        print("Nenhum evento ativo no momento.")
        return

    print(f"{len(events)} eventos ativos encontrados:")
    for e in events:
        print(f"  - {e['name']} (ID: {e['id']})")

    for evt in events:
        print(f"\nSyncando matches de {evt['name']}...")
        try:
            sync_full_event(evt['id'], headless=True, team_workers=1, player_workers=1)
        except Exception as e:
            logger.error("Erro no evento %d: %s", evt['id'], e)

    print("\nSync de eventos ativos concluido.")


if __name__ == '__main__':
    main()
