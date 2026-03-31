#!/usr/bin/env python3
"""
Sync all HLTV events from the archive (last 2 years).
Scrapes event list from archive page, then syncs each event fully.
"""

import argparse
import logging
import re
import time
import traceback
from datetime import datetime, date, timedelta

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from src.database import init_db, session_scope
from src.database.models import Event
from src.scrapers.selenium_helpers import create_driver, wait_for_cloudflare, random_delay
from sync_all import sync_full_event

logger = logging.getLogger(__name__)


def scrape_archive_events(start_date, end_date, headless=True):
    """Scrape event IDs from HLTV archive page (MAJOR + INTLLAN events)."""
    driver = create_driver(headless=headless)
    events = []

    try:
        # HLTV archive URL with date range + event type filter
        url = (
            f"https://www.hltv.org/events/archive"
            f"?startDate={start_date}&endDate={end_date}"
            f"&eventType=MAJOR&eventType=INTLLAN"
        )
        print(f"Buscando eventos do archive: {start_date} a {end_date}...")
        driver.get(url)
        wait_for_cloudflare(driver)
        random_delay(3.0, 5.0)

        wait = WebDriverWait(driver, 20)
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))

        # Scroll down to load more events
        for _ in range(5):
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1)

        # Find all event links
        event_links = driver.find_elements(By.CSS_SELECTOR, "a.a-reset")
        print(f"  Encontrados {len(event_links)} links de eventos")

        seen_ids = set()
        for link in event_links:
            try:
                href = link.get_attribute("href") or ""
                # Match /events/NNNN/event-name
                m = re.search(r'/events/(\d+)/', href)
                if not m:
                    continue
                event_id = int(m.group(1))
                if event_id in seen_ids:
                    continue
                seen_ids.add(event_id)

                # Get event name
                name = ""
                try:
                    name_elem = link.find_element(By.CSS_SELECTOR, ".big-event-name, .event-name-small, .text-ellipsis")
                    name = name_elem.text.strip()
                except Exception:
                    name = link.text.strip().split('\n')[0] if link.text else f"Event {event_id}"

                events.append({
                    'id': event_id,
                    'name': name or f"Event {event_id}",
                })

            except Exception as e:
                continue

        print(f"  {len(events)} eventos encontrados (MAJOR + INTLLAN)")
        return events

    except Exception as e:
        logger.error("Erro ao buscar archive: %s", e)
        traceback.print_exc()
        return []
    finally:
        driver.quit()


def main():
    parser = argparse.ArgumentParser(description="Sync HLTV events from archive")
    parser.add_argument('--years', type=float, default=2.0, help='Years back to sync (default: 2)')
    parser.add_argument('--show', action='store_true', help='Show browser')
    parser.add_argument('--workers', type=int, default=1, help='Worker threads')
    parser.add_argument('--dry-run', action='store_true', help='Only list events, dont sync')
    parser.add_argument('--skip-existing', action='store_true', default=True,
                        help='Skip events already in DB (default: True)')

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    headless = not args.show

    # Initialize DB
    init_db()

    # Calculate date range
    end_date = date.today().isoformat()
    start_date = (date.today() - timedelta(days=int(args.years * 365))).isoformat()

    # Get events from archive
    events = scrape_archive_events(start_date, end_date, headless=headless)

    if not events:
        print("Nenhum evento encontrado")
        return

    # Filter out existing events
    if args.skip_existing:
        with session_scope() as session:
            existing_ids = {e.id for e in session.query(Event.id).all()}
        new_events = [e for e in events if e['id'] not in existing_ids]
        print(f"\n{len(events)} total, {len(existing_ids)} ja no banco, {len(new_events)} novos")
        events = new_events

    if args.dry_run:
        print(f"\nDRY RUN - {len(events)} eventos para syncar:")
        for e in events:
            print(f"  {e['name']} (ID: {e['id']})")
        return

    # Sync each event
    print(f"\nSyncando {len(events)} eventos...\n")
    for idx, evt in enumerate(events, 1):
        print(f"\n{'#'*70}")
        print(f"[{idx}/{len(events)}] {evt['name']} (ID: {evt['id']})")
        print(f"{'#'*70}")

        # Ensure event record exists
        with session_scope() as session:
            if not session.query(Event).filter_by(id=evt['id']).first():
                session.add(Event(id=evt['id'], name=evt['name']))

        try:
            sync_full_event(
                evt['id'], headless=headless,
                team_workers=args.workers, player_workers=args.workers,
            )
        except Exception as e:
            logger.error("ERRO no evento %d: %s", evt['id'], e)
            traceback.print_exc()

        # Pause between events
        if idx < len(events):
            print(f"\nPausa de 5s antes do proximo evento...")
            time.sleep(5)

    print(f"\n{'='*70}")
    print(f"SYNC COMPLETO: {len(events)} eventos processados")
    print(f"{'='*70}\n")


if __name__ == '__main__':
    main()
