"""
Enhanced player stats scraper for HLTV.
Scrapes comprehensive player statistics from multiple pages:
- /stats/players/{id}/{name} - Overview stats
- /stats/players/matches/{id}/{name} - Match history
- /stats/players/events/{id}/{name} - Event history
- /stats/players/career/{id}/{name} - Career stats
"""

from playwright.sync_api import sync_playwright
import time
import re
from datetime import datetime


BASE_URL = "https://www.hltv.org"


def scrape_player_overview_stats(player_id: int, headless=True):
    """
    Scrape detailed overview stats from /stats/players/{id}

    Returns dict with:
    - Rating 2.0, KPR, APR, KAST%, Impact, ADR, etc.
    - Total maps, kills, deaths, K/D ratio
    - Headshot %, rounds played
    - Clutch stats (1v1, 1v2, etc.)
    """
    url = f"{BASE_URL}/stats/players/{player_id}/player"

    print(f"  📊 Scraping overview stats: {url}")

    stats_data = {
        "player_id": player_id,
        "rating_2_0": None,
        "kpr": None,  # Kills per round
        "spr": None,  # Survived per round
        "apr": None,  # Assists per round
        "kast": None,  # KAST %
        "impact": None,
        "adr": None,  # Average damage per round
        "total_kills": None,
        "headshot_percentage": None,
        "total_deaths": None,
        "kd_ratio": None,
        "damage_per_round": None,
        "grenade_damage_per_round": None,
        "maps_played": None,
        "rounds_played": None,
        "kills_per_round": None,
        "assists_per_round": None,
        "deaths_per_round": None,
        "saved_by_teammate_per_round": None,
        "saved_teammates_per_round": None,
        # Clutch stats
        "clutch_1v1_won": None,
        "clutch_1v2_won": None,
        "clutch_1v3_won": None,
        "clutch_1v4_won": None,
        "clutch_1v5_won": None,
        # Opening/Trading
        "opening_kills": None,
        "opening_deaths": None,
        "opening_success": None,
        "team_win_after_first_kill": None,
        "first_kill_in_won_rounds": None,
    }

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
        page = context.new_page()

        try:
            page.goto(url, timeout=30000)
            time.sleep(3)

            # Accept cookies
            try:
                page.locator("text=Accept").click(timeout=2000)
            except:
                pass

            # Main rating (from center circle)
            try:
                rating_elem = page.query_selector(".summaryStatBreakdownDataValue")
                if rating_elem:
                    rating_text = rating_elem.inner_text().strip()
                    stats_data["rating_2_0"] = float(rating_text)
                    print(f"    ✓ Rating 2.0: {stats_data['rating_2_0']}")
            except:
                pass

            # KPR, DPR, ADR (main stats below rating)
            try:
                # KPR
                kpr_elem = page.query_selector("div.summaryBreakdown:has-text('KPR') .summaryStatBreakdownDataValue")
                if kpr_elem:
                    stats_data["kpr"] = float(kpr_elem.inner_text().strip())
                    print(f"    ✓ KPR: {stats_data['kpr']}")

                # DPR
                dpr_elem = page.query_selector("div.summaryBreakdown:has-text('DPR') .summaryStatBreakdownDataValue")
                if dpr_elem:
                    stats_data["deaths_per_round"] = float(dpr_elem.inner_text().strip())

                # ADR
                adr_elem = page.query_selector("div.summaryBreakdown:has-text('ADR') .summaryStatBreakdownDataValue")
                if adr_elem:
                    stats_data["adr"] = float(adr_elem.inner_text().strip())
                    print(f"    ✓ ADR: {stats_data['adr']}")

                # KAST
                kast_elem = page.query_selector("div.summaryBreakdown:has-text('KAST') .summaryStatBreakdownDataValue")
                if kast_elem:
                    kast_text = kast_elem.inner_text().strip().replace('%', '')
                    stats_data["kast"] = float(kast_text)
                    print(f"    ✓ KAST: {stats_data['kast']}%")

                # Impact
                impact_elem = page.query_selector("div.summaryBreakdown:has-text('Impact') .summaryStatBreakdownDataValue")
                if impact_elem:
                    stats_data["impact"] = float(impact_elem.inner_text().strip())
                    print(f"    ✓ Impact: {stats_data['impact']}")
            except Exception as e:
                print(f"    ⚠️  Error parsing main stats: {e}")

            # Statistics table (Total kills, K/D, etc.)
            try:
                stat_rows = page.query_selector_all(".statistics-table tr, .stats-row")

                for row in stat_rows:
                    try:
                        cells = row.query_selector_all("td, span")
                        if len(cells) < 2:
                            continue

                        label_text = cells[0].inner_text().strip().lower()
                        value_text = cells[1].inner_text().strip()

                        if "total kills" in label_text:
                            stats_data["total_kills"] = int(value_text.replace(',', ''))
                            print(f"    ✓ Total Kills: {stats_data['total_kills']}")
                        elif "headshot" in label_text and "%" in value_text:
                            hs_match = re.search(r'([\d.]+)', value_text)
                            if hs_match:
                                stats_data["headshot_percentage"] = float(hs_match.group(1))
                                print(f"    ✓ HS%: {stats_data['headshot_percentage']}%")
                        elif "total deaths" in label_text:
                            stats_data["total_deaths"] = int(value_text.replace(',', ''))
                            print(f"    ✓ Total Deaths: {stats_data['total_deaths']}")
                        elif "k/d ratio" in label_text:
                            stats_data["kd_ratio"] = float(value_text)
                            print(f"    ✓ K/D: {stats_data['kd_ratio']}")
                        elif "maps played" in label_text:
                            stats_data["maps_played"] = int(value_text.replace(',', ''))
                            print(f"    ✓ Maps: {stats_data['maps_played']}")
                        elif "rounds played" in label_text:
                            stats_data["rounds_played"] = int(value_text.replace(',', ''))
                            print(f"    ✓ Rounds: {stats_data['rounds_played']}")
                    except:
                        continue
            except Exception as e:
                print(f"    ⚠️  Error parsing table stats: {e}")

            browser.close()

            # Log what we collected
            collected = sum(1 for v in stats_data.values() if v is not None)
            print(f"    ✅ Collected {collected}/{len(stats_data)} stats")

            return stats_data

        except Exception as e:
            print(f"    ❌ Error: {e}")
            browser.close()
            return stats_data


def scrape_player_matches(player_id: int, limit=50, headless=True):
    """
    Scrape match history from /stats/players/matches/{id}

    Returns list of recent matches with:
    - Match ID, date, event
    - Map, result, K-D
    - Rating, ADR, KAST
    """
    url = f"{BASE_URL}/stats/players/matches/{player_id}/player"

    print(f"  🎮 Scraping match history: {url}")

    matches = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        page = browser.new_page()

        try:
            page.goto(url, timeout=30000)
            time.sleep(2)

            # Accept cookies
            try:
                page.locator("text=Accept").click(timeout=2000)
            except:
                pass

            # Parse match rows
            match_rows = page.query_selector_all("tbody tr")[:limit]

            for row in match_rows:
                try:
                    match_data = {}

                    # Date
                    date_elem = row.query_selector("td.time, td:first-child")
                    if date_elem:
                        match_data["date"] = date_elem.inner_text().strip()

                    # Match link (to get ID)
                    match_link = row.query_selector("a[href*='/matches/']")
                    if match_link:
                        href = match_link.get_attribute("href")
                        match_id_search = re.search(r'/matches/(\d+)/', href)
                        if match_id_search:
                            match_data["match_id"] = int(match_id_search.group(1))

                    # Event
                    event_elem = row.query_selector(".event-name, td:nth-child(2)")
                    if event_elem:
                        match_data["event"] = event_elem.inner_text().strip()

                    # Map
                    map_elem = row.query_selector(".map, .dynamic-map-name-short")
                    if map_elem:
                        match_data["map"] = map_elem.inner_text().strip()

                    # K-D
                    kd_elem = row.query_selector("td.kd-ratio, td:nth-child(4)")
                    if kd_elem:
                        kd_text = kd_elem.inner_text().strip()
                        match_data["kills_deaths"] = kd_text

                        # Parse kills and deaths
                        kd_match = re.search(r'(\d+)\s*-\s*(\d+)', kd_text)
                        if kd_match:
                            match_data["kills"] = int(kd_match.group(1))
                            match_data["deaths"] = int(kd_match.group(2))

                    # Rating
                    rating_elem = row.query_selector("td.rating, .rating-cell")
                    if rating_elem:
                        rating_text = rating_elem.inner_text().strip()
                        try:
                            match_data["rating"] = float(rating_text)
                        except:
                            pass

                    if match_data:
                        matches.append(match_data)

                except Exception as e:
                    continue

            browser.close()
            print(f"    ✅ Found {len(matches)} matches")
            return matches

        except Exception as e:
            print(f"    ❌ Error: {e}")
            browser.close()
            return matches


def scrape_player_events(player_id: int, limit=30, headless=True):
    """
    Scrape event history from /stats/players/events/{id}

    Returns list of events with stats
    """
    url = f"{BASE_URL}/stats/players/events/{player_id}/player"

    print(f"  🏆 Scraping event history: {url}")

    events = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        page = browser.new_page()

        try:
            page.goto(url, timeout=30000)
            time.sleep(2)

            # Accept cookies
            try:
                page.locator("text=Accept").click(timeout=2000)
            except:
                pass

            # Parse event rows
            event_rows = page.query_selector_all("tbody tr")[:limit]

            for row in event_rows:
                try:
                    event_data = {}

                    # Event name and link
                    event_link = row.query_selector("a.event-name, td:first-child a")
                    if event_link:
                        event_data["name"] = event_link.inner_text().strip()
                        href = event_link.get_attribute("href")
                        event_id_search = re.search(r'/events/(\d+)/', href)
                        if event_id_search:
                            event_data["event_id"] = int(event_id_search.group(1))

                    # Maps played
                    maps_elem = row.query_selector("td:nth-child(2), .maps-played")
                    if maps_elem:
                        try:
                            event_data["maps"] = int(maps_elem.inner_text().strip())
                        except:
                            pass

                    # K-D
                    kd_elem = row.query_selector("td:nth-child(3)")
                    if kd_elem:
                        kd_text = kd_elem.inner_text().strip()
                        kd_match = re.search(r'([\d.]+)', kd_text)
                        if kd_match:
                            event_data["kd_ratio"] = float(kd_match.group(1))

                    # Rating
                    rating_elem = row.query_selector("td:nth-child(4), .rating")
                    if rating_elem:
                        try:
                            event_data["rating"] = float(rating_elem.inner_text().strip())
                        except:
                            pass

                    if event_data:
                        events.append(event_data)

                except:
                    continue

            browser.close()
            print(f"    ✅ Found {len(events)} events")
            return events

        except Exception as e:
            print(f"    ❌ Error: {e}")
            browser.close()
            return events


def scrape_player_full_stats(player_id: int, include_matches=True, include_events=True, headless=True):
    """
    Scrape complete player stats from all pages.

    Returns comprehensive dict with all stats, matches, events.
    """
    print(f"\n{'='*80}")
    print(f"📊 SCRAPING FULL STATS FOR PLAYER {player_id}")
    print(f"{'='*80}\n")

    full_data = {
        "player_id": player_id,
        "overview_stats": None,
        "recent_matches": [],
        "event_history": [],
        "scraped_at": datetime.utcnow().isoformat(),
    }

    # 1. Overview stats
    print("1️⃣  Overview Stats")
    full_data["overview_stats"] = scrape_player_overview_stats(player_id, headless=headless)
    time.sleep(2)

    # 2. Recent matches (optional)
    if include_matches:
        print("\n2️⃣  Match History")
        full_data["recent_matches"] = scrape_player_matches(player_id, limit=50, headless=headless)
        time.sleep(2)

    # 3. Event history (optional)
    if include_events:
        print("\n3️⃣  Event History")
        full_data["event_history"] = scrape_player_events(player_id, limit=30, headless=headless)

    print(f"\n{'='*80}")
    print(f"✅ SCRAPING COMPLETE")
    print(f"{'='*80}\n")

    return full_data


if __name__ == "__main__":
    import sys
    import json

    if len(sys.argv) > 1:
        player_id = int(sys.argv[1])
        print(f"Testing enhanced player scraper with ID: {player_id}")

        result = scrape_player_full_stats(player_id, headless=False)

        print("\n" + "="*80)
        print("RESULTS:")
        print("="*80)
        print(json.dumps(result, indent=2, default=str))
    else:
        print("Usage: python player_stats_scraper.py <player_id>")
        print("Example: python player_stats_scraper.py 21167")
