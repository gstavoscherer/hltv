"""
Scraper for HLTV team pages.
Collects team roster, lineup history, and stats.
"""

from playwright.sync_api import sync_playwright
import time
import re


BASE_URL = "https://www.hltv.org"


def scrape_team_details(team_id: int, headless=True):
    """
    Scrape detailed team information including current roster.

    Args:
        team_id: HLTV team ID
        headless: Run browser in headless mode

    Returns:
        dict with team details and roster
    """
    url = f"{BASE_URL}/team/{team_id}/roster"

    print(f"🔍 Scraping team {team_id}: {url}")

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

            team_data = {
                "id": team_id,
                "name": None,
                "country": None,
                "world_rank": None,
                "logo_url": None,
                "current_roster": [],  # List of player dicts
                "coach": None,
                "coach_id": None,
            }

            # Team name
            try:
                name_elem = page.query_selector(".profile-team-name")
                if name_elem:
                    team_data["name"] = name_elem.inner_text().strip()
                    print(f"  🏆 Team: {team_data['name']}")
            except:
                pass

            # Logo
            try:
                logo_elem = page.query_selector(".profile-team-logo img")
                if logo_elem:
                    team_data["logo_url"] = logo_elem.get_attribute("src")
            except:
                pass

            # Country
            try:
                country_elem = page.query_selector(".team-country .flag")
                if country_elem:
                    team_data["country"] = country_elem.get_attribute("title")
                    print(f"  🌍 Country: {team_data['country']}")
            except:
                pass

            # World ranking
            try:
                rank_elem = page.query_selector(".profile-team-stat .right")
                if rank_elem:
                    rank_text = rank_elem.inner_text().strip()
                    rank_match = re.search(r'#(\d+)', rank_text)
                    if rank_match:
                        team_data["world_rank"] = int(rank_match.group(1))
                        print(f"  📊 Rank: #{team_data['world_rank']}")
            except:
                pass

            # Current roster (main lineup)
            try:
                # Try different selectors for roster
                player_cards = page.query_selector_all(".lineup-con .playerPicture")

                if not player_cards:
                    # Alternative: bodyshot-team
                    player_cards = page.query_selector_all(".bodyshot-team a[href*='/player/']")

                for card in player_cards[:10]:  # Limit to 10 players max
                    try:
                        # Get href directly if card is an <a> tag
                        if card.evaluate("el => el.tagName") == "A":
                            player_href = card.get_attribute("href")
                            parent = card
                        else:
                            # Otherwise find parent <a>
                            parent = card.query_selector("xpath=ancestor::a")
                            if not parent:
                                continue
                            player_href = parent.get_attribute("href")

                        if not player_href:
                            continue

                        # Extract player ID from URL: /player/7998/broky
                        player_id_match = re.search(r'/player/(\d+)/', player_href)
                        if not player_id_match:
                            continue

                        player_id = int(player_id_match.group(1))

                        # Player nickname - try different selectors
                        nickname = None
                        nickname_elem = parent.query_selector(".playerNickname, .text-ellipsis, [class*='nickname']")
                        if nickname_elem:
                            nickname = nickname_elem.inner_text().strip()

                        if not nickname:
                            # Try getting from URL
                            nickname = player_href.split('/')[-1] if player_href else None

                        # Player real name (title attribute or alt)
                        real_name = parent.get_attribute("title")
                        if not real_name:
                            img_elem = parent.query_selector("img")
                            if img_elem:
                                real_name = img_elem.get_attribute("alt") or img_elem.get_attribute("title")

                        # Player image
                        img_elem = parent.query_selector("img")
                        img_url = img_elem.get_attribute("src") if img_elem else None

                        player_info = {
                            "player_id": player_id,
                            "nickname": nickname,
                            "real_name": real_name,
                            "image_url": img_url,
                            "role": "player",  # Default role
                        }

                        team_data["current_roster"].append(player_info)
                        print(f"    ✓ Player: {nickname} (ID: {player_id})")

                    except Exception as e:
                        print(f"    ⚠️  Error parsing player: {e}")
                        continue

                print(f"  👥 Roster size: {len(team_data['current_roster'])}")

            except Exception as e:
                print(f"  ⚠️  Error loading roster: {e}")

            # Coach
            try:
                coach_elem = page.query_selector(".coach-col a")
                if coach_elem:
                    coach_name = coach_elem.inner_text().strip()
                    coach_href = coach_elem.get_attribute("href")

                    team_data["coach"] = coach_name

                    if coach_href:
                        coach_id_match = re.search(r'/player/(\d+)/', coach_href)
                        if coach_id_match:
                            team_data["coach_id"] = int(coach_id_match.group(1))

                    print(f"  🎓 Coach: {team_data['coach']} (ID: {team_data['coach_id']})")
            except:
                pass

            browser.close()
            return team_data

        except Exception as e:
            print(f"  ❌ Error scraping team {team_id}: {e}")
            browser.close()
            return None


def scrape_multiple_teams(team_ids: list, headless=True, delay=3):
    """
    Scrape multiple teams with delay between requests.

    Args:
        team_ids: List of team IDs
        headless: Run in headless mode
        delay: Seconds to wait between requests

    Returns:
        List of team data dicts
    """
    results = []

    for idx, team_id in enumerate(team_ids, 1):
        print(f"\n[{idx}/{len(team_ids)}] Processing team {team_id}")

        team_data = scrape_team_details(team_id, headless=headless)

        if team_data:
            results.append(team_data)
            print(f"  ✅ Success")
        else:
            print(f"  ❌ Failed")

        # Delay between requests
        if idx < len(team_ids):
            print(f"  ⏳ Waiting {delay}s...")
            time.sleep(delay)

    return results


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        team_id = int(sys.argv[1])
        print(f"Testing team scraper with ID: {team_id}")

        result = scrape_team_details(team_id, headless=False)

        if result:
            print("\n" + "="*60)
            print("RESULT:")
            print("="*60)
            for key, value in result.items():
                if key == "current_roster":
                    print(f"\n{key}:")
                    for player in value:
                        print(f"  - {player}")
                elif value:
                    print(f"{key}: {value}")
    else:
        print("Usage: python team_scraper.py <team_id>")
        print("Example: python team_scraper.py 5973")
