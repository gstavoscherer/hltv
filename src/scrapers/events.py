"""Event scraper for HLTV."""

import logging
import re
import time
import traceback

from datetime import datetime
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException

from .selenium_helpers import create_driver, wait_for_cloudflare, random_delay

logger = logging.getLogger(__name__)


def _parse_date_range(start_unix_ms, end_unix_ms):
    """Convert unix timestamps (ms) to date objects."""
    start = datetime.fromtimestamp(start_unix_ms / 1000).date() if start_unix_ms else None
    end = datetime.fromtimestamp(end_unix_ms / 1000).date() if end_unix_ms else None
    return start, end


def _scrape_events_selenium(limit=None, headless=True):
    driver = create_driver(headless=headless)
    events = []

    try:
        print("Acessando HLTV events page...")
        driver.get("https://www.hltv.org/events")
        wait_for_cloudflare(driver)
        random_delay(2.0, 4.0)

        wait = WebDriverWait(driver, 20)
        wait.until(EC.presence_of_element_located((By.CLASS_NAME, "events-holder")))

        event_elements = driver.find_elements(By.CSS_SELECTOR, ".big-event, .small-event")
        print(f"Encontrados {len(event_elements)} eventos")

        if limit:
            event_elements = event_elements[:limit]

        for idx, event_elem in enumerate(event_elements, 1):
            try:
                event_url = event_elem.get_attribute("href")
                event_id = int(event_url.split('/')[-2]) if event_url else None

                if not event_id:
                    continue

                try:
                    name_elem = event_elem.find_element(By.CSS_SELECTOR, ".big-event-name, .small-event-name")
                    name = name_elem.text.strip()
                except NoSuchElementException:
                    name = event_elem.text.split('\n')[0].strip()

                start_date = None
                end_date = None
                try:
                    date_elems = event_elem.find_elements(By.CSS_SELECTOR, "span[data-unix]")
                    if len(date_elems) >= 1:
                        start_unix = int(date_elems[0].get_attribute("data-unix"))
                        start_date = datetime.fromtimestamp(start_unix / 1000).date()
                    if len(date_elems) >= 2:
                        end_unix = int(date_elems[1].get_attribute("data-unix"))
                        end_date = datetime.fromtimestamp(end_unix / 1000).date()
                except Exception:
                    pass

                location = None
                try:
                    loc_elem = event_elem.find_element(By.CSS_SELECTOR, "span.text-ellipsis")
                    location_text = loc_elem.text.strip()
                    months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                              'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
                    if location_text and not any(m in location_text for m in months):
                        location = location_text
                except NoSuchElementException:
                    pass

                event_type = "LAN" if "big-event" in event_elem.get_attribute("class") else "Online"

                event_data = {
                    'id': event_id,
                    'name': name,
                    'start_date': start_date,
                    'end_date': end_date or start_date,
                    'location': location,
                    'event_type': event_type,
                    'prize_pool': None
                }

                events.append(event_data)
                print(f"  [{idx}/{len(event_elements)}] {name} (ID: {event_id})")

            except Exception as e:
                logger.warning("Erro ao processar evento %d: %s", idx, e)
                continue

        print(f"Total de eventos coletados: {len(events)}")
        return events

    except Exception as e:
        logger.error("Erro ao fazer scraping de eventos: %s", e)
        return []
    finally:
        driver.quit()


def scrape_events(limit=None, headless=True):
    """Scrape events from HLTV events page."""
    return _scrape_events_selenium(limit=limit, headless=headless)


def _get_event_details_selenium(event_id, headless=True, driver=None):
    owns_driver = driver is None
    if owns_driver:
        driver = create_driver(headless=headless)
    details = {}

    try:
        url = f"https://www.hltv.org/events/{event_id}/a"
        print(f"Buscando detalhes do evento {event_id}...")
        driver.get(url)
        wait_for_cloudflare(driver)
        random_delay(2.0, 4.0)

        wait = WebDriverWait(driver, 20)
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))

        # Extract location
        try:
            location_elems = driver.find_elements(By.CSS_SELECTOR, "span.text-ellipsis")
            months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                      'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
            for elem in location_elems:
                text = elem.text.strip()
                if ',' in text and len(text) > 3:
                    if not any(m in text for m in months):
                        details['location'] = text
                        break

            if 'location' not in details:
                try:
                    flag_elems = driver.find_elements(By.CSS_SELECTOR, "img.flag")
                    for flag in flag_elems:
                        parent = flag.find_element(By.XPATH, "..")
                        text = parent.text.strip()
                        if text and len(text) > 2:
                            details['location'] = text
                            break
                except Exception:
                    pass
        except Exception as e:
            logger.warning("Nao foi possivel extrair location: %s", e)

        # Extract dates
        try:
            date_elems = driver.find_elements(By.CSS_SELECTOR, ".eventdate span[data-unix]")
            if len(date_elems) >= 2:
                start_unix = int(date_elems[0].get_attribute("data-unix"))
                end_unix = int(date_elems[1].get_attribute("data-unix"))
                details['start_date'] = datetime.fromtimestamp(start_unix / 1000).date()
                details['end_date'] = datetime.fromtimestamp(end_unix / 1000).date()
        except Exception:
            pass

        # Extract prize pool
        try:
            prize_elems = driver.find_elements(By.XPATH, "//*[contains(text(), '$')]")

            max_prize = None
            max_amount = 0

            for elem in prize_elems:
                text = elem.text.strip()
                match = re.search(r'\$([0-9,]+)', text)
                if match:
                    amount_str = match.group(1).replace(',', '')
                    try:
                        amount = int(amount_str)
                        if amount > max_amount:
                            max_amount = amount
                            max_prize = match.group(0)
                    except ValueError:
                        pass

            if max_prize:
                details['prize_pool'] = max_prize
        except Exception as e:
            logger.warning("Nao foi possivel extrair prize_pool: %s", e)

        print(f"  Detalhes: location={details.get('location', 'N/A')}, prize={details.get('prize_pool', 'N/A')}")
        return details

    except Exception as e:
        logger.error("Erro ao buscar detalhes do evento %d: %s", event_id, e)
        traceback.print_exc()
        return {}
    finally:
        if owns_driver:
            driver.quit()


def get_event_details(event_id, headless=True, driver=None):
    """Get detailed event information (location, prize pool)."""
    return _get_event_details_selenium(event_id, headless=headless, driver=driver)


def _extract_team_id_from_href(href):
    """Extract team ID from an HLTV team URL."""
    if not href or '/team/' not in href:
        return None
    parts = href.split('/')
    for i, part in enumerate(parts):
        if part == 'team' and i + 1 < len(parts):
            try:
                return int(parts[i + 1])
            except ValueError:
                pass
    return None


def _get_event_teams_selenium(event_id, headless=True, driver=None):
    """Get participating teams scoped to tournament-specific containers."""
    owns_driver = driver is None
    if owns_driver:
        driver = create_driver(headless=headless)
    teams = []

    try:
        url = f"https://www.hltv.org/events/{event_id}/a"
        print(f"Acessando evento {event_id}...")
        driver.get(url)
        wait_for_cloudflare(driver)
        random_delay(2.0, 4.0)

        wait = WebDriverWait(driver, 20)
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))

        # Strategy 1: Teams from placements section (most reliable)
        try:
            placement_links = driver.find_elements(
                By.CSS_SELECTOR, ".placements a[href*='/team/']"
            )
            for link in placement_links:
                tid = _extract_team_id_from_href(link.get_attribute("href"))
                if tid and tid not in teams:
                    teams.append(tid)
        except Exception:
            pass

        # Strategy 2: Teams from groups/brackets section
        group_selectors = [
            ".group-team a[href*='/team/']",
            ".bracket-team a[href*='/team/']",
            ".swiss-visual-team a[href*='/team/']",
            ".team-box a[href*='/team/']",
        ]
        for sel in group_selectors:
            try:
                group_links = driver.find_elements(By.CSS_SELECTOR, sel)
                for link in group_links:
                    tid = _extract_team_id_from_href(link.get_attribute("href"))
                    if tid and tid not in teams:
                        teams.append(tid)
            except Exception:
                pass

        # Strategy 3: Teams from the "Teams attending" section
        try:
            attending_sections = driver.find_elements(
                By.CSS_SELECTOR, ".teams-attending a[href*='/team/']"
            )
            for link in attending_sections:
                tid = _extract_team_id_from_href(link.get_attribute("href"))
                if tid and tid not in teams:
                    teams.append(tid)
        except Exception:
            pass

        # Strategy 4: Teams from lineup containers (team logos/cards)
        try:
            lineup_links = driver.find_elements(
                By.CSS_SELECTOR, ".lineup-container a[href*='/team/']"
            )
            for link in lineup_links:
                tid = _extract_team_id_from_href(link.get_attribute("href"))
                if tid and tid not in teams:
                    teams.append(tid)
        except Exception:
            pass

        # Strategy 5: If still empty, look in main event content area only
        # (exclude header/footer/sidebar by targeting the event-specific content)
        if not teams:
            content_selectors = [
                ".event-holder a[href*='/team/']",
                ".contentCol a[href*='/team/']",
                "#eventContent a[href*='/team/']",
            ]
            for sel in content_selectors:
                try:
                    content_links = driver.find_elements(By.CSS_SELECTOR, sel)
                    for link in content_links:
                        tid = _extract_team_id_from_href(link.get_attribute("href"))
                        if tid and tid not in teams:
                            teams.append(tid)
                except Exception:
                    pass

        print(f"  Encontrados {len(teams)} times no evento {event_id}")
        return teams

    except Exception as e:
        logger.error("Erro ao buscar times do evento %d: %s", event_id, e)
        traceback.print_exc()
        return []
    finally:
        if owns_driver:
            driver.quit()


def get_event_teams(event_id, headless=True, driver=None):
    """Get participating teams for a specific event."""
    return _get_event_teams_selenium(event_id, headless=headless, driver=driver)


def _parse_placement_number(text):
    """Parse placement from text like '1st', '2nd', '3rd-4th', '5-8th'."""
    if not text:
        return None
    text = text.strip().lower()

    # Range matches first like "3-4th", "5-8th" (before direct matches)
    range_match = re.search(r'(\d+)\s*-\s*\d+\s*(?:st|nd|rd|th)', text)
    if range_match:
        return int(range_match.group(1))

    # Direct matches
    direct = {'1st': 1, '2nd': 2, '3rd': 3, '4th': 4, '5th': 5}
    for key, val in direct.items():
        if key in text:
            return val

    # Just a number
    num_match = re.search(r'(\d+)', text)
    if num_match:
        return int(num_match.group(1))

    return None


def _get_event_results_selenium(event_id, headless=True, driver=None):
    """Get event results from the placements container."""
    owns_driver = driver is None
    if owns_driver:
        driver = create_driver(headless=headless)
    results = []

    try:
        url = f"https://www.hltv.org/events/{event_id}/a"
        print(f"Buscando resultados do evento {event_id}...")
        driver.get(url)
        wait_for_cloudflare(driver)
        random_delay(2.0, 4.0)

        wait = WebDriverWait(driver, 20)
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))

        seen_teams = set()

        # Strategy 1: Structured placements container
        placement_divs = driver.find_elements(By.CSS_SELECTOR, ".placements .placement")

        for div in placement_divs:
            try:
                # Find team link
                team_link = div.find_elements(By.CSS_SELECTOR, "a[href*='/team/']")
                if not team_link:
                    continue

                tid = _extract_team_id_from_href(team_link[0].get_attribute("href"))
                if not tid or tid in seen_teams:
                    continue
                seen_teams.add(tid)

                # Find placement text - look for text with ordinal suffixes
                placement = None
                all_text = div.text
                placement = _parse_placement_number(all_text)

                # Find prize - look for .prize div or $ text
                prize = None
                try:
                    prize_elem = div.find_element(By.CSS_SELECTOR, ".prize")
                    prize = prize_elem.text.strip()
                except Exception:
                    # Fallback: look for $ in any child
                    try:
                        dollar_elems = div.find_elements(By.XPATH, ".//*[contains(text(), '$')]")
                        if dollar_elems:
                            prize = dollar_elems[0].text.strip()
                    except Exception:
                        pass

                results.append({
                    'team_id': tid,
                    'placement': placement,
                    'prize': prize
                })
            except Exception:
                continue

        # Strategy 2: If no structured placements, try top-placement containers
        if not results:
            top_placements = driver.find_elements(
                By.CSS_SELECTOR, ".top-placement, .placement-container"
            )
            for container in top_placements:
                try:
                    team_link = container.find_elements(By.CSS_SELECTOR, "a[href*='/team/']")
                    if not team_link:
                        continue

                    tid = _extract_team_id_from_href(team_link[0].get_attribute("href"))
                    if not tid or tid in seen_teams:
                        continue
                    seen_teams.add(tid)

                    placement = _parse_placement_number(container.text)

                    prize = None
                    try:
                        dollar_elems = container.find_elements(By.XPATH, ".//*[contains(text(), '$')]")
                        if dollar_elems:
                            prize = dollar_elems[0].text.strip()
                    except Exception:
                        pass

                    results.append({
                        'team_id': tid,
                        'placement': placement,
                        'prize': prize
                    })
                except Exception:
                    continue

        # Strategy 3: Fallback - search within placements-holder broadly
        if not results:
            try:
                holder = driver.find_elements(By.CSS_SELECTOR, ".placements-holder")
                if holder:
                    team_links = holder[0].find_elements(By.CSS_SELECTOR, "a[href*='/team/']")
                    for idx, link in enumerate(team_links):
                        tid = _extract_team_id_from_href(link.get_attribute("href"))
                        if tid and tid not in seen_teams:
                            seen_teams.add(tid)
                            results.append({
                                'team_id': tid,
                                'placement': idx + 1,
                                'prize': None
                            })
            except Exception:
                pass

        print(f"  Encontrados resultados de {len(results)} times")
        return results

    except Exception as e:
        logger.error("Erro ao buscar resultados do evento %d: %s", event_id, e)
        traceback.print_exc()
        return []
    finally:
        if owns_driver:
            driver.quit()


def get_event_results(event_id, headless=True, driver=None):
    """Get event results with team placements and prizes."""
    return _get_event_results_selenium(event_id, headless=headless, driver=driver)
