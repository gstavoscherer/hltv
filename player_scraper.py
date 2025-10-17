"""
Scraper for HLTV player pages.
Collects detailed player information including stats, teams, etc.
"""

from playwright.sync_api import sync_playwright
import time
import re
from datetime import datetime


BASE_URL = "https://www.hltv.org"


def scrape_player_details(player_id: int, headless=True):
    """
    Scrape detailed player information from HLTV.

    Args:
        player_id: HLTV player ID
        headless: Run browser in headless mode

    Returns:
        dict with player details
    """
    # URL com qualquer coisa após o ID funciona
    url = f"{BASE_URL}/player/{player_id}/details"

    print(f"🔍 Scraping player {player_id}: {url}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/118.0.0.0 Safari/537.36"
            )
        )
        page = context.new_page()

        try:
            page.goto(url, timeout=30000)
            time.sleep(2)

            # Accept cookies
            try:
                page.locator("text=Accept All Cookies").click(timeout=3000)
            except:
                pass

            player_data = {
                "id": player_id,
                "nickname": None,
                "real_name": None,
                "age": None,
                "country": None,
                "current_team": None,
                "current_team_id": None,
                "total_maps": None,
                "total_kills": None,
                "total_deaths": None,
                "kd_ratio": None,
                "headshot_percentage": None,
                "rounds_played": None,
                "average_rating": None,
                "past_teams": [],
            }

            # Nickname (main title)
            try:
                nickname_elem = page.query_selector(".playerNickname")
                if nickname_elem:
                    player_data["nickname"] = nickname_elem.inner_text().strip()
                    print(f"  👤 Nickname: {player_data['nickname']}")
            except:
                pass

            # Real name
            try:
                real_name_elem = page.query_selector(".playerRealname")
                if real_name_elem:
                    player_data["real_name"] = real_name_elem.inner_text().strip()
                    print(f"  📝 Real name: {player_data['real_name']}")
            except:
                pass

            # Age
            try:
                age_elem = page.query_selector(".playerAge")
                if age_elem:
                    age_text = age_elem.inner_text().strip()
                    age_match = re.search(r'(\d+)\s*years', age_text)
                    if age_match:
                        player_data["age"] = int(age_match.group(1))
                        print(f"  🎂 Age: {player_data['age']}")
            except:
                pass

            # Country
            try:
                country_elem = page.query_selector(".playerRealname .flag")
                if country_elem:
                    country_title = country_elem.get_attribute("title")
                    player_data["country"] = country_title
                    print(f"  🌍 Country: {player_data['country']}")
            except:
                pass

            # Current team
            try:
                team_elem = page.query_selector(".playerTeam a")
                if team_elem:
                    team_name = team_elem.inner_text().strip()
                    team_href = team_elem.get_attribute("href")
                    player_data["current_team"] = team_name

                    # Extract team ID from URL: /team/5973/liquid
                    if team_href:
                        team_id_match = re.search(r'/team/(\d+)/', team_href)
                        if team_id_match:
                            player_data["current_team_id"] = int(team_id_match.group(1))

                    print(f"  🏆 Team: {player_data['current_team']} (ID: {player_data['current_team_id']})")
            except:
                pass

            # Statistics from the stats table
            try:
                stats_rows = page.query_selector_all(".statistics .stats-row")
                for row in stats_rows:
                    label_elem = row.query_selector(".stats-label")
                    value_elem = row.query_selector(".stats-value")

                    if not (label_elem and value_elem):
                        continue

                    label = label_elem.inner_text().strip().lower()
                    value = value_elem.inner_text().strip()

                    if "maps played" in label:
                        player_data["total_maps"] = int(value.replace(',', ''))
                    elif "rounds played" in label:
                        player_data["total_rounds"] = int(value.replace(',', ''))
                    elif "k/d ratio" in label:
                        player_data["kd_ratio"] = float(value)
                    elif "headshot" in label:
                        hs_match = re.search(r'([\d.]+)%', value)
                        if hs_match:
                            player_data["headshot_percentage"] = float(hs_match.group(1))
                    elif "rating" in label:
                        player_data["average_rating"] = float(value)

                print(f"  📊 Stats loaded: {len([k for k,v in player_data.items() if v is not None and k.startswith('total_') or k.endswith('_ratio') or k.endswith('_percentage')])} metrics")
            except Exception as e:
                print(f"  ⚠️  Error loading stats: {e}")

            # Past teams (team history)
            try:
                team_history = page.query_selector_all(".team-history-for-player .team-name")
                for team_elem in team_history[:10]:  # Limit to last 10 teams
                    team_link = team_elem.query_selector("a")
                    if team_link:
                        team_name = team_link.inner_text().strip()
                        team_href = team_link.get_attribute("href")
                        team_id = None

                        if team_href:
                            team_id_match = re.search(r'/team/(\d+)/', team_href)
                            if team_id_match:
                                team_id = int(team_id_match.group(1))

                        if team_name and team_id:
                            player_data["past_teams"].append({
                                "team_id": team_id,
                                "team_name": team_name,
                            })

                if player_data["past_teams"]:
                    print(f"  📜 Past teams: {len(player_data['past_teams'])}")
            except Exception as e:
                print(f"  ⚠️  Error loading team history: {e}")

            browser.close()
            return player_data

        except Exception as e:
            print(f"  ❌ Error scraping player {player_id}: {e}")
            browser.close()
            return None


def scrape_multiple_players(player_ids: list, headless=True, delay=3):
    """
    Scrape multiple players with delay between requests.

    Args:
        player_ids: List of player IDs
        headless: Run in headless mode
        delay: Seconds to wait between requests

    Returns:
        List of player data dicts
    """
    results = []

    for idx, player_id in enumerate(player_ids, 1):
        print(f"\n[{idx}/{len(player_ids)}] Processing player {player_id}")

        player_data = scrape_player_details(player_id, headless=headless)

        if player_data:
            results.append(player_data)
            print(f"  ✅ Success")
        else:
            print(f"  ❌ Failed")

        # Delay between requests
        if idx < len(player_ids):
            print(f"  ⏳ Waiting {delay}s...")
            time.sleep(delay)

    return results


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        player_id = int(sys.argv[1])
        print(f"Testing player scraper with ID: {player_id}")

        result = scrape_player_details(player_id, headless=False)

        if result:
            print("\n" + "="*60)
            print("RESULT:")
            print("="*60)
            for key, value in result.items():
                if value:
                    print(f"{key}: {value}")
    else:
        print("Usage: python player_scraper.py <player_id>")
        print("Example: python player_scraper.py 7998")
