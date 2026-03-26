"""Player scraper for HLTV."""

import logging
import re
import time

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

from .selenium_helpers import create_driver, wait_for_cloudflare, random_delay

logger = logging.getLogger(__name__)


def parse_stat_value(text):
    """Parse stat value from text, handling various formats."""
    if not text:
        return None

    text = text.strip().replace(',', '')

    match = re.search(r'[\d.]+', text)
    if match:
        try:
            return float(match.group())
        except ValueError:
            return None
    return None


def _extract_player_data(driver, player_id):
    """Extract player data from an already-loaded page. Returns dict or raises."""
    player_data = {'id': player_id}

    title = driver.title
    nickname_match = re.search(r"'([^']+)'", title)
    if nickname_match:
        player_data['nickname'] = nickname_match.group(1)

    name_match = re.search(r'^([^\']+)\s+\'', title)
    if name_match:
        player_data['real_name'] = name_match.group(1).strip()

    try:
        country_elem = driver.find_element(By.CSS_SELECTOR, ".player-summary-stat-box-left-flag .flag")
        player_data['country'] = country_elem.get_attribute("title")
    except Exception:
        pass

    try:
        age_elem = driver.find_element(By.CSS_SELECTOR, ".player-summary-stat-box-left-player-age")
        age_text = age_elem.text.strip()
        age_match = re.search(r'(\d+)', age_text)
        if age_match:
            player_data['age'] = int(age_match.group(1))
    except Exception:
        pass

    try:
        team_elem = driver.find_element(By.CSS_SELECTOR, ".playerTeam a")
        team_url = team_elem.get_attribute("href")
        if team_url and '/team/' in team_url:
            player_data['current_team_id'] = int(team_url.split('/')[-2])
    except Exception:
        pass

    # Detect player role from page content
    try:
        page_text = driver.page_source.lower()
        role = None
        if 'in-game leader' in page_text:
            role = 'igl'
        elif 'awper' in page_text:
            role = 'awp'
        elif 'entry fragger' in page_text:
            role = 'entry'
        elif 'rifler' in page_text:
            role = 'rifler'
        player_data['role'] = role
    except Exception:
        player_data['role'] = None

    # Extract career stats from stats-row elements
    stats_rows = driver.find_elements(By.CLASS_NAME, "stats-row")

    for row in stats_rows:
        try:
            spans = row.find_elements(By.TAG_NAME, "span")
            if len(spans) >= 2:
                label = spans[0].text.strip().lower()
                value = spans[1].text.strip()

                if 'total kills' in label:
                    player_data['total_kills'] = int(value.replace(',', ''))
                elif 'headshot %' in label:
                    player_data['headshot_percentage'] = float(value.replace('%', ''))
                elif 'k/d ratio' in label:
                    player_data['kd_ratio'] = float(value)
                elif 'damage / round' in label or 'adr' in label:
                    player_data['adr'] = float(value)
                elif 'maps played' in label:
                    player_data['total_maps'] = int(value.replace(',', ''))
                elif 'rounds played' in label:
                    player_data['total_rounds'] = int(value.replace(',', ''))
                elif 'deaths' in label and 'per' not in label:
                    player_data['total_deaths'] = int(value.replace(',', ''))
                elif 'kills / round' in label or 'kpr' in label:
                    player_data['kpr'] = float(value)
                elif 'kast' in label:
                    player_data['kast'] = float(value.replace('%', ''))
                elif 'impact' in label:
                    player_data['impact'] = float(value)
        except Exception:
            continue

    # Extract from summary stat boxes
    try:
        stat_wrappers = driver.find_elements(By.CSS_SELECTOR, ".player-summary-stat-box-data-wrapper")

        for wrapper in stat_wrappers:
            try:
                label_elem = wrapper.find_element(By.CSS_SELECTOR, ".player-summary-stat-box-data-text")
                label = label_elem.text.strip().lower()

                value_elem = wrapper.find_element(By.CSS_SELECTOR, ".player-summary-stat-box-data")
                value_text = value_elem.text.strip().replace('%', '').replace(',', '')

                if not value_text or value_text == 'N/A':
                    continue

                if 'kast' in label:
                    player_data['kast'] = float(value_text)
                elif 'kpr' in label or 'kills per round' in label:
                    player_data['kpr'] = float(value_text)
                elif 'adr' in label or 'average damage' in label:
                    player_data['adr'] = float(value_text)
                elif 'impact' in label:
                    player_data['impact'] = float(value_text)
            except Exception:
                continue
    except Exception:
        pass

    # Extract Rating
    try:
        rating_elem = driver.find_element(By.CSS_SELECTOR, ".player-summary-stat-box-rating-data-text")
        rating_text = rating_elem.text.strip()
        if rating_text and rating_text != 'N/A':
            player_data['rating_2_0'] = float(rating_text)
    except Exception:
        pass

    return player_data


def _scrape_player_selenium(player_id, headless=True, max_retries=3, driver=None):
    """Scrape player with retry logic and Cloudflare bypass.

    If ``driver`` is provided, reuses it (no create/quit). On Cloudflare
    block the caller's driver is marked for replacement via the pool.
    """
    owns_driver = driver is None
    attempt = 0
    last_error = None
    cf_timeout = 20  # progressive: 20, 30, 45

    while attempt < max_retries:
        attempt += 1
        try:
            if owns_driver and driver is None:
                driver = create_driver(headless=headless)

            url = f"https://www.hltv.org/stats/players/{player_id}/placeholder"

            if attempt > 1:
                print(f"    Tentativa {attempt}/{max_retries} para jogador {player_id}...")

            driver.get(url)
            cf_ok = wait_for_cloudflare(driver, timeout=cf_timeout)

            if not cf_ok:
                raise TimeoutException(f"Cloudflare nao resolveu em {cf_timeout}s")

            random_delay(0.5, 1.5)

            wait = WebDriverWait(driver, 20)
            wait.until(EC.presence_of_element_located((By.CLASS_NAME, "stats-row")))

            player_data = _extract_player_data(driver, player_id)

            nickname = player_data.get('nickname', 'Unknown')
            rating = player_data.get('rating_2_0', 'N/A')
            print(f"  Jogador: {nickname} | Rating: {rating}")

            return player_data

        except TimeoutException:
            last_error = f"Timeout ao carregar pagina de stats do jogador {player_id}"
            logger.warning("Timeout tentativa %d/%d jogador %d", attempt, max_retries, player_id)
            cf_timeout = min(cf_timeout + 10, 45)  # progressive timeout
            time.sleep(3 * attempt)

            # If using external driver and Cloudflare blocked, signal bad driver
            if not owns_driver:
                raise  # let caller handle pool.mark_bad

        except Exception as e:
            last_error = str(e)
            logger.warning("Erro tentativa %d/%d jogador %d: %s", attempt, max_retries, player_id, e)
            time.sleep(2 * attempt)

            if not owns_driver:
                raise

        finally:
            # Only quit driver if we created it AND we're done retrying or succeeded
            if owns_driver and driver and attempt >= max_retries:
                try:
                    driver.quit()
                except Exception:
                    pass

    # Clean up owned driver on exhausted retries
    if owns_driver and driver:
        try:
            driver.quit()
        except Exception:
            pass

    logger.error("Falha ao coletar jogador %d apos %d tentativas: %s", player_id, max_retries, last_error)
    return None


def scrape_player(player_id, headless=True, max_retries=3, driver=None):
    return _scrape_player_selenium(player_id, headless=headless, max_retries=max_retries, driver=driver)


def scrape_players(player_ids, headless=True):
    """Scrape multiple players."""
    results = []

    for idx, player_id in enumerate(player_ids, 1):
        print(f"\n[{idx}/{len(player_ids)}] Processando jogador {player_id}...")

        player_data = scrape_player(player_id, headless=headless)

        if player_data:
            results.append(player_data)

        if idx < len(player_ids):
            time.sleep(1)

    print(f"\nTotal de jogadores coletados: {len(results)}")
    return results


def scrape_event_stats(event_id, headless=True):
    """Scrape player statistics for a specific event."""
    driver = create_driver(headless=headless)

    try:
        url = f"https://www.hltv.org/stats/events/{event_id}/placeholder"
        print(f"  Acessando stats do evento {event_id}...")
        driver.get(url)

        wait = WebDriverWait(driver, 10)
        wait.until(EC.presence_of_element_located((By.CLASS_NAME, "stats-table")))

        time.sleep(2)

        stats = []

        player_rows = driver.find_elements(By.CSS_SELECTOR, ".stats-table tbody tr")

        for row in player_rows:
            try:
                player_link = row.find_element(By.CSS_SELECTOR, "td.playerCol a")
                player_url = player_link.get_attribute("href")

                if not player_url or '/player/' not in player_url:
                    continue

                player_id = int(player_url.split('/')[-2])

                cells = row.find_elements(By.TAG_NAME, "td")

                stat_data = {
                    'player_id': player_id,
                    'event_id': event_id
                }

                if len(cells) >= 3:
                    try:
                        stat_data['maps_played'] = int(parse_stat_value(cells[1].text) or 0)
                        stat_data['rating'] = parse_stat_value(cells[2].text)

                        if len(cells) >= 4:
                            kd_text = cells[3].text.strip()
                            stat_data['kd_ratio'] = parse_stat_value(kd_text)
                    except Exception:
                        pass

                stats.append(stat_data)

            except Exception:
                continue

        print(f"  Stats do evento {event_id}: {len(stats)} jogadores")
        return stats

    except Exception as e:
        logger.error("Erro ao buscar stats do evento %d: %s", event_id, e)
        return []
    finally:
        driver.quit()
