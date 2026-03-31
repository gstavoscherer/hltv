"""Team scraper for HLTV with retry system."""

import logging
import time

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException

from .selenium_helpers import create_driver, wait_for_cloudflare, random_delay

logger = logging.getLogger(__name__)

# Known role keywords from HLTV lineup section
_ROLE_KEYWORDS = {
    "awper": "awper", "awp": "awper",
    "igl": "igl", "in-game leader": "igl",
    "entry": "entry", "entry fragger": "entry",
    "rifler": "rifler",
    "support": "support",
    "lurker": "lurker",
    "coach": "coach",
}


def _scrape_roles_from_lineup(driver):
    """Extract player roles from the team lineup section on HLTV."""
    roles = {}
    try:
        lineup_items = driver.find_elements(By.CSS_SELECTOR, ".lineup .player-info, .players-table .player-row, .bodyshot-team-flex .col")
        for item in lineup_items:
            try:
                link = item.find_element(By.CSS_SELECTOR, "a[href*='/player/']")
                href = link.get_attribute("href")
                if not href or "/player/" not in href:
                    continue
                player_id = int(href.split("/")[-2])

                # Try to find role text within the same container
                text = item.text.lower()
                for keyword, role in _ROLE_KEYWORDS.items():
                    if keyword in text:
                        roles[player_id] = role
                        break
            except (NoSuchElementException, Exception):
                continue

        # Fallback: check for star player / IGL badges in the page
        if not roles:
            try:
                flag_elements = driver.find_elements(By.CSS_SELECTOR, ".playerFlagName, .lineup-player")
                for elem in flag_elements:
                    try:
                        link = elem.find_element(By.CSS_SELECTOR, "a[href*='/player/']")
                        href = link.get_attribute("href")
                        if not href:
                            continue
                        player_id = int(href.split("/")[-2])

                        parent_text = elem.text.lower()
                        for keyword, role in _ROLE_KEYWORDS.items():
                            if keyword in parent_text:
                                roles[player_id] = role
                                break
                    except Exception:
                        continue
            except Exception:
                pass

    except Exception as e:
        logger.debug("Nao conseguiu extrair roles do lineup: %s", e)

    return roles


def _scrape_team_selenium(team_id, headless=True, max_retries=3, driver=None):
    owns_driver = driver is None
    attempt = 0
    last_error = None

    while attempt < max_retries:
        attempt += 1
        print(f"\n  Tentativa {attempt}/{max_retries} para time {team_id}...")

        try:
            if owns_driver and driver is None:
                driver = create_driver(headless=headless)

            url = f"https://www.hltv.org/team/{team_id}/placeholder"
            driver.get(url)
            wait_for_cloudflare(driver)
            random_delay(1.0, 2.0)

            wait = WebDriverWait(driver, 20)
            wait.until(EC.presence_of_element_located((By.CLASS_NAME, "teamProfile")))

            name_elem = driver.find_element(By.CLASS_NAME, "profile-team-name")
            name = name_elem.text.strip()

            try:
                country_elem = driver.find_element(By.CSS_SELECTOR, ".team-country")
                country = country_elem.get_attribute("title") or country_elem.text.strip()
            except NoSuchElementException:
                country = None

            try:
                rank_elem = driver.find_element(By.CSS_SELECTOR, ".profile-team-stat .right")
                txt = rank_elem.text.strip().replace("#", "")
                world_rank = int(txt) if txt.isdigit() else None
            except Exception:
                world_rank = None

            team_data = {
                "id": team_id,
                "name": name,
                "country": country,
                "world_rank": world_rank,
            }

            roster = []
            try:
                players = driver.find_elements(By.CSS_SELECTOR, ".bodyshot-team a")

                for p in players:
                    try:
                        href = p.get_attribute("href")
                        if href and "/player/" in href:
                            player_id = int(href.split("/")[-2])
                            nickname = p.text.strip()

                            if nickname:
                                roster.append({
                                    "player_id": player_id,
                                    "nickname": nickname,
                                    "is_current": True,
                                })
                    except Exception:
                        continue

                print(f"  Time: {name} | Roster: {len(roster)} jogadores")

            except Exception as e:
                logger.warning("Erro ao buscar roster de %d: %s", team_id, e)

            # Scrape roles from lineup section
            roles_map = _scrape_roles_from_lineup(driver)
            for player_entry in roster:
                pid = player_entry["player_id"]
                if pid in roles_map:
                    player_entry["role"] = roles_map[pid]

            return {"team": team_data, "roster": roster}

        except Exception as e:
            last_error = e
            logger.warning("Erro na tentativa %d do time %d: %s", attempt, team_id, e)
            time.sleep(2 * attempt)

            if not owns_driver:
                raise  # let caller handle pool.mark_bad

        finally:
            if owns_driver and driver and attempt >= max_retries:
                try:
                    driver.quit()
                except Exception:
                    pass

    if owns_driver and driver:
        try:
            driver.quit()
        except Exception:
            pass

    logger.error("Falha final ao coletar time %d apos %d tentativas: %s", team_id, max_retries, last_error)
    return None


def scrape_team(team_id, headless=True, max_retries=3, driver=None):
    return _scrape_team_selenium(team_id, headless=headless, max_retries=max_retries, driver=driver)


def scrape_teams(team_ids, headless=True):
    results = []

    for idx, team_id in enumerate(team_ids, 1):
        print(f"\n[{idx}/{len(team_ids)}] Processando time {team_id}...")

        data = scrape_team(team_id, headless=headless)

        if data:
            results.append(data)

        time.sleep(1.5)

    print(f"\nFinalizado - Times coletados: {len(results)}")
    return results
