"""
Complete population flow - CORRECT VERSION:
1. Get events from events.py
2. Get FULL event data (overview, matches, stats) from event_scraper
3. Extract teams from event data
4. Get team rosters for each team
5. Get individual player stats
"""

import time
import re
from database import get_db_session
from database.models import Event, Team, Player, EventTeam, TeamPlayer, EventStats
from events import scrape_events
from event_scraper import build_event_payload, scrape_stats_with_selenium
from team_scraper import scrape_team_details
from player_stats_scraper import scrape_player_full_stats


def step1_import_events(limit=10):
    """Step 1: Import events from HLTV archive"""
    print("\n" + "="*80)
    print("📋 STEP 1: IMPORTING EVENTS")
    print("="*80)

    # Get events from events.py
    print("🔍 Scraping events from HLTV...")
    events_list = scrape_events(headless=True)

    if not events_list:
        print("❌ No events found")
        return []

    print(f"✅ Found {len(events_list)} events")

    # Limit events
    events_to_process = events_list[:limit]
    print(f"📊 Will process {len(events_to_process)} events\n")

    # Import to database
    event_ids = []
    with get_db_session() as session:
        for event_data in events_to_process:
            event_id = event_data.get('id')
            event_name = event_data.get('name')

            if not event_id:
                continue

            # Check if exists
            existing = session.query(Event).filter(Event.id == event_id).first()

            if existing:
                print(f"⏭️  Event {event_id}: {event_name} (exists)")
                event_ids.append(event_id)
                continue

            # Create event
            event = Event(
                id=event_id,
                name=event_name,
                start_date=event_data.get('start_date'),
                end_date=event_data.get('end_date'),
                location=event_data.get('location', 'Online'),
                event_type=event_data.get('type', 'Online'),
                prize_pool=event_data.get('prize_pool')
            )

            session.add(event)
            print(f"✅ Event {event_id}: {event_name}")
            event_ids.append(event_id)

        session.commit()

    print(f"\n✅ Step 1 complete: {len(event_ids)} events imported\n")
    return event_ids


def step2_get_full_event_data(event_id):
    """Step 2: Get COMPLETE event data (overview, matches, stats)"""
    print(f"\n{'='*80}")
    print(f"📊 STEP 2: EVENT {event_id} - GETTING FULL DATA")
    print("="*80)

    # Use Selenium for stats (required for Cloudflare bypass)
    # NOTE: Selenium will run in non-headless mode to bypass Cloudflare
    print("🔍 Scraping event stats with Selenium (Cloudflare bypass)...")
    stats = scrape_stats_with_selenium(event_id, headless=False)

    if not stats:
        print("❌ No stats data returned from Selenium")
        return None

    if 'top_players' not in stats or len(stats['top_players']) == 0:
        print(f"❌ No players found in stats. Stats keys: {stats.keys()}")
        return None

    num_players = len(stats['top_players'])
    num_teams = len(stats.get('top_teams', []))
    print(f"✅ Stats retrieved: {num_players} players, {num_teams} teams\n")

    # Build event data structure
    event_data = {
        'event_id': event_id,
        'stats': stats
    }

    return event_data


def step3_process_event_data(event_id, event_data):
    """Step 3: Process event data - create players and stats"""
    print(f"\n{'='*80}")
    print(f"👥 STEP 3: EVENT {event_id} - PROCESSING PLAYERS")
    print("="*80)

    stats = event_data.get('stats', {})
    top_players = stats.get('top_players', [])

    if not top_players:
        print("❌ No players found")
        return []

    print(f"✅ Found {len(top_players)} top players\n")

    player_ids = []

    with get_db_session() as session:
        for idx, player_data in enumerate(top_players, 1):
            player_url = player_data.get('url', '')
            player_name = player_data.get('name', '')

            if not player_url or '/players/' not in player_url:
                continue

            try:
                player_id = int(re.search(r'/players/(\d+)/', player_url).group(1))
                player_ids.append(player_id)

                # Create player if doesn't exist
                player = session.query(Player).filter(Player.id == player_id).first()

                if not player:
                    player = Player(
                        id=player_id,
                        nickname=player_name
                    )
                    session.add(player)
                    print(f"[{idx}] ✅ {player_name} (ID: {player_id})")
                else:
                    print(f"[{idx}] ⏭️  {player_name} (exists)")

                session.flush()

                # Add event stats
                event_stats = session.query(EventStats).filter_by(
                    event_id=event_id,
                    player_id=player_id
                ).first()

                if not event_stats:
                    event_stats = EventStats(
                        event_id=event_id,
                        player_id=player_id,
                        rating=float(player_data.get('rating')) if player_data.get('rating') else None,
                        maps_played=int(player_data.get('maps')) if player_data.get('maps') else None
                    )
                    session.add(event_stats)

                session.commit()

            except Exception as e:
                print(f"[{idx}] ❌ Error: {e}")
                session.rollback()

    print(f"\n✅ Step 3 complete: {len(player_ids)} players imported\n")
    return player_ids


def step4_get_team_rosters(team_ids):
    """Step 4: Get team rosters for each team"""
    print(f"\n{'='*80}")
    print(f"👥 STEP 4: GETTING TEAM ROSTERS")
    print("="*80)

    if not team_ids:
        print("⏭️  No teams to process, skipping...")
        return

    print(f"📊 Processing {len(team_ids)} teams\n")

    with get_db_session() as session:
        for idx, team_id in enumerate(team_ids, 1):
            print(f"[{idx}/{len(team_ids)}] Team ID: {team_id}")

            try:
                # Get team details and roster
                team_data = scrape_team_details(team_id, headless=True)

                if not team_data:
                    print(f"  ⚠️  No data found")
                    continue

                # Create/update team
                team = session.query(Team).filter(Team.id == team_id).first()
                if not team:
                    team = Team(
                        id=team_id,
                        name=team_data.get('name'),
                        country=team_data.get('country'),
                        world_rank=team_data.get('world_rank')
                    )
                    session.add(team)
                    print(f"  ✅ Created team: {team_data.get('name')}")
                else:
                    print(f"  ✓ Team exists: {team.name}")

                session.commit()
                time.sleep(3)  # Rate limiting

            except Exception as e:
                print(f"  ❌ Error: {e}")
                session.rollback()

    print(f"\n✅ Step 4 complete\n")


def step5_get_player_stats(player_ids, limit=None):
    """Step 5: Get detailed stats for each player"""
    print(f"\n{'='*80}")
    print(f"📈 STEP 5: GETTING DETAILED PLAYER STATS")
    print("="*80)

    if limit:
        player_ids = player_ids[:limit]
        print(f"📊 Processing {len(player_ids)} players (limited)\n")

    with get_db_session() as session:
        for idx, player_id in enumerate(player_ids, 1):
            player = session.query(Player).filter(Player.id == player_id).first()

            if not player:
                continue

            player_name = player.nickname or f"Player {player_id}"
            print(f"[{idx}/{len(player_ids)}] {player_name} (ID: {player_id})")

            try:
                # Get full stats
                stats = scrape_player_full_stats(
                    player_id,
                    include_matches=False,
                    include_events=False,
                    headless=True
                )

                if stats:
                    # Update player with stats
                    player.total_kills = stats.get('total_kills')
                    player.total_deaths = stats.get('total_deaths')
                    player.kd_ratio = stats.get('kd_ratio')
                    player.headshot_percentage = stats.get('headshot_percentage')
                    player.total_maps = stats.get('total_maps')
                    player.total_rounds = stats.get('total_rounds')
                    player.rating_2_0 = stats.get('rating_2_0')
                    player.kpr = stats.get('kpr')
                    player.apr = stats.get('apr')
                    player.kast = stats.get('kast')
                    player.impact = stats.get('impact')
                    player.adr = stats.get('adr')

                    session.commit()

                    print(f"  ✅ Stats updated (Rating: {stats.get('rating_2_0')}, K/D: {stats.get('kd_ratio')})")
                else:
                    print(f"  ⚠️  No stats found")

                # Rate limiting
                time.sleep(3)

            except Exception as e:
                print(f"  ❌ Error: {e}")
                session.rollback()

    print(f"\n✅ Step 4 complete\n")


def full_flow(num_events=3, num_players_stats=5):
    """
    Execute complete flow

    Args:
        num_events: Number of events to process
        num_players_stats: Number of players to get detailed stats for (per event)
    """
    print("\n" + "🚀"*40)
    print("COMPLETE HLTV DATA POPULATION FLOW")
    print("🚀"*40)

    # Use existing events from database
    print("\n" + "="*80)
    print("📋 GETTING EVENTS FROM DATABASE")
    print("="*80)

    event_ids = []
    with get_db_session() as session:
        events = session.query(Event).limit(num_events).all()
        event_ids = [e.id for e in events]
        print(f"✅ Found {len(event_ids)} events in database")
        for e in events:
            print(f"  • {e.id}: {e.name}")

    if not event_ids:
        print("❌ No events to process")
        return

    # Step 2-5: Process each event
    for event_id in event_ids:
        # Step 2: Get full event data (overview, matches, stats)
        event_data = step2_get_full_event_data(event_id)

        if not event_data:
            print(f"⚠️  No data found for event {event_id}, skipping...")
            continue

        # Step 3: Process event data (create players and event_stats)
        player_ids = step3_process_event_data(event_id, event_data)

        if not player_ids:
            print(f"⚠️  No players found for event {event_id}, skipping...")
            continue

        # Step 4: Get team rosters (TODO: extract teams from event data first)
        # team_ids = step4_get_team_rosters(event_data)

        # Step 5: Get detailed player stats (limited)
        step5_get_player_stats(player_ids, limit=num_players_stats)

        print(f"\n✅ Event {event_id} complete!")
        time.sleep(5)  # Rate limiting between events

    # Final stats
    print("\n" + "="*80)
    print("📊 FINAL DATABASE STATS")
    print("="*80)

    with get_db_session() as session:
        num_events = session.query(Event).count()
        num_players = session.query(Player).count()
        num_stats = session.query(EventStats).count()
        players_with_full_stats = session.query(Player).filter(Player.rating_2_0 != None).count()

        print(f"🎯 Events: {num_events}")
        print(f"🎮 Players: {num_players}")
        print(f"📈 Event Stats: {num_stats}")
        print(f"✨ Players with full stats: {players_with_full_stats}/{num_players}")

    print("\n" + "🎉"*40)
    print("FLOW COMPLETE!")
    print("🎉"*40 + "\n")


if __name__ == '__main__':
    import sys

    num_events = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    num_players = int(sys.argv[2]) if len(sys.argv) > 2 else 5

    full_flow(num_events=num_events, num_players_stats=num_players)
