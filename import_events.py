"""
Simple script to import events from archive into database
"""

import json
import time
from database import get_db_session
from database.models import Event
from datetime import datetime


def parse_date(date_str):
    """Parse date string like 'Oct 4th - Oct 12th' to start/end dates"""
    if not date_str or '-' not in date_str:
        return None, None

    try:
        parts = date_str.split('-')
        # For now, just return None - we'll get better dates from full scrape
        return None, None
    except:
        return None, None


def import_from_archive(event_ids=None, limit=5):
    """
    Import events from hltv_archive_events.json

    Args:
        event_ids: List of specific event IDs to import, or None for top events
        limit: Max number of events to import
    """

    # Load archive
    with open('hltv_archive_events.json', 'r') as f:
        archive_data = json.load(f)

    print(f"📚 Loaded {len(archive_data)} events from archive")

    # Filter events
    if event_ids:
        # Convert to int for comparison
        events_to_import = [e for e in archive_data if int(e['id']) in event_ids]
    else:
        # Get big events (16+ teams)
        big_events = [
            e for e in archive_data
            if e.get('teams_count', '0').replace('+','').isdigit()
            and int(e.get('teams_count', '0').replace('+','')) >= 16
        ]
        events_to_import = big_events[:limit]

    print(f"🎯 Selected {len(events_to_import)} events to import\n")

    with get_db_session() as session:
        imported = 0
        skipped = 0

        for event_data in events_to_import:
            event_id = int(event_data['id'])  # Convert to int

            # Check if already exists
            existing = session.query(Event).filter(Event.id == event_id).first()
            if existing:
                print(f"⏭️  Event {event_id} already exists, skipping")
                skipped += 1
                continue

            # Parse dates
            start_date, end_date = parse_date(event_data.get('dates', ''))

            # Create event
            event = Event(
                id=event_id,
                name=event_data.get('name'),
                location=event_data.get('location', 'Online'),
                event_type=event_data.get('format', 'Online'),
                prize_pool=event_data.get('prize_pool'),
                start_date=start_date,
                end_date=end_date,
            )

            session.add(event)
            print(f"✅ Imported: [{event_id}] {event.name}")
            print(f"   Teams: {event_data.get('teams_count')} | Prize: {event_data.get('prize_pool')}")
            imported += 1

        session.commit()

        print(f"\n{'='*60}")
        print(f"✅ Imported: {imported} events")
        print(f"⏭️  Skipped: {skipped} events (already exist)")
        print(f"{'='*60}")


if __name__ == '__main__':
    import sys

    if len(sys.argv) > 1:
        # Import specific event IDs
        event_ids = [int(x) for x in sys.argv[1:]]
        import_from_archive(event_ids=event_ids)
    else:
        # Import top 5 big events
        import_from_archive(limit=5)
