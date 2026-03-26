"""Match scraper for HLTV."""

import logging
import re
import time
import traceback

from datetime import datetime
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from .selenium_helpers import create_driver, wait_for_cloudflare, random_delay
from .events import _extract_team_id_from_href

logger = logging.getLogger(__name__)


def _parse_match_id_from_url(url):
    """Extract match ID from HLTV match URL like /matches/2389987/slug."""
    if not url:
        return None
    match = re.search(r'/matches/(\d+)/', url)
    return int(match.group(1)) if match else None


def _parse_best_of(text):
    """Parse best-of from text like 'bo3', 'bo1', 'bo5'."""
    if not text:
        return None
    m = re.search(r'bo(\d)', text.lower())
    return int(m.group(1)) if m else None


def _parse_veto_line(line):
    """Parse a veto line like '1. Vitality removed Ancient'."""
    # Left over pattern: "7. Anubis was left over"
    leftover = re.match(r'(\d+)\.\s+(\w+)\s+was\s+left\s+over', line.strip())
    if leftover:
        return {
            'veto_number': int(leftover.group(1)),
            'team_name': None,
            'action': 'left over',
            'map_name': leftover.group(2),
        }

    # Standard pattern: "1. TeamName removed/picked MapName"
    standard = re.match(r'(\d+)\.\s+(.+?)\s+(removed|picked)\s+(\w+)', line.strip())
    if standard:
        return {
            'veto_number': int(standard.group(1)),
            'team_name': standard.group(2),
            'action': standard.group(3),
            'map_name': standard.group(4),
        }

    return None


def _parse_half_scores(text):
    """Parse half scores from text like '(10:5; 6:4)'. Returns (ct_score, t_score)."""
    if not text:
        return None, None
    m = re.search(r'\((\d+):(\d+);\s*(\d+):(\d+)\)', text)
    if m:
        return int(m.group(1)), int(m.group(3))
    return None, None


def _parse_kills_hs(text):
    """Parse 'N (M)' or 'N(M)' format used for kills(hs), assists(flash), deaths(traded)."""
    if not text:
        return 0, 0
    m = re.match(r'(\d+)\s*\((\d+)\)', text.strip())
    if m:
        return int(m.group(1)), int(m.group(2))
    m2 = re.match(r'(\d+)', text.strip())
    if m2:
        return int(m2.group(1)), 0
    return 0, 0


def _parse_opening_kd(text):
    """Parse 'K : D' or 'K:D' format for opening kills/deaths."""
    if not text:
        return 0, 0
    m = re.match(r'(\d+)\s*:\s*(\d+)', text.strip())
    if m:
        return int(m.group(1)), int(m.group(2))
    return 0, 0


def scrape_event_matches(event_id, headless=True, driver=None):
    """Scrape all match results for an event from /results?event={id}."""
    owns_driver = driver is None
    if owns_driver:
        driver = create_driver(headless=headless)

    matches = []
    try:
        url = f"https://www.hltv.org/results?event={event_id}"
        print(f"Buscando matches do evento {event_id}...")
        driver.get(url)
        wait_for_cloudflare(driver)
        random_delay(2.0, 4.0)

        wait = WebDriverWait(driver, 20)
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))

        result_elements = driver.find_elements(By.CSS_SELECTOR, ".result-con")
        print(f"  Encontrados {len(result_elements)} matches")

        for elem in result_elements:
            try:
                link = elem.find_element(By.CSS_SELECTOR, "a")
                href = link.get_attribute("href")
                match_id = _parse_match_id_from_url(href)
                if not match_id:
                    continue

                # Teams
                team_elems = elem.find_elements(By.CSS_SELECTOR, ".team")
                team1_name = team_elems[0].text.strip() if len(team_elems) > 0 else None
                team2_name = team_elems[1].text.strip() if len(team_elems) > 1 else None

                # Team IDs from lineup links or team links
                team1_id = None
                team2_id = None
                team_links = elem.find_elements(By.CSS_SELECTOR, "a[href*='/team/']")
                if len(team_links) >= 2:
                    team1_id = _extract_team_id_from_href(team_links[0].get_attribute("href"))
                    team2_id = _extract_team_id_from_href(team_links[1].get_attribute("href"))

                # Scores
                score1 = None
                score2 = None
                try:
                    score_elems = elem.find_elements(By.CSS_SELECTOR, ".result-score span")
                    if len(score_elems) >= 2:
                        score1 = int(score_elems[0].text.strip())
                        score2 = int(score_elems[1].text.strip())
                except Exception:
                    pass

                # Best of
                best_of = None
                try:
                    map_text = elem.find_element(By.CSS_SELECTOR, ".map-text")
                    best_of = _parse_best_of(map_text.text.strip())
                except Exception:
                    pass

                # Date from parent container
                match_date = None
                try:
                    unix = elem.get_attribute("data-zonedgrouping-entry-unix")
                    if unix:
                        match_date = datetime.fromtimestamp(int(unix) / 1000).date()
                except Exception:
                    pass

                # Stars
                stars = 0
                try:
                    star_elems = elem.find_elements(By.CSS_SELECTOR, "i.fa-star")
                    stars = len(star_elems)
                except Exception:
                    pass

                # Winner
                winner_id = None
                if score1 is not None and score2 is not None:
                    if score1 > score2:
                        winner_id = team1_id
                    elif score2 > score1:
                        winner_id = team2_id

                matches.append({
                    'id': match_id,
                    'event_id': event_id,
                    'team1_id': team1_id,
                    'team2_id': team2_id,
                    'team1_name': team1_name,
                    'team2_name': team2_name,
                    'score1': score1,
                    'score2': score2,
                    'best_of': best_of,
                    'date': match_date,
                    'winner_id': winner_id,
                    'stars': stars,
                })
            except Exception as e:
                logger.warning("Erro ao processar match: %s", e)
                continue

        print(f"  {len(matches)} matches coletados")
        return matches

    except Exception as e:
        logger.error("Erro ao buscar matches do evento %d: %s", event_id, e)
        traceback.print_exc()
        return []
    finally:
        if owns_driver:
            driver.quit()


def scrape_match_detail(match_id, headless=True, driver=None):
    """Scrape match detail page for maps, scores, and vetos."""
    owns_driver = driver is None
    if owns_driver:
        driver = create_driver(headless=headless)

    try:
        url = f"https://www.hltv.org/matches/{match_id}/placeholder"
        driver.get(url)
        wait_for_cloudflare(driver)
        random_delay(0.5, 1.5)

        wait = WebDriverWait(driver, 20)
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))

        result = {'match_id': match_id, 'maps': [], 'vetos': []}

        # Team IDs
        team_links = driver.find_elements(By.CSS_SELECTOR, ".team1-gradient a[href*='/team/'], .team2-gradient a[href*='/team/']")
        team_ids = []
        for tl in team_links:
            tid = _extract_team_id_from_href(tl.get_attribute("href"))
            if tid and tid not in team_ids:
                team_ids.append(tid)
        result['team1_id'] = team_ids[0] if len(team_ids) > 0 else None
        result['team2_id'] = team_ids[1] if len(team_ids) > 1 else None

        # Parse vetos
        try:
            veto_boxes = driver.find_elements(By.CSS_SELECTOR, ".veto-box .padding")
            for box in veto_boxes:
                lines = box.text.strip().split('\n')
                for line in lines:
                    parsed = _parse_veto_line(line)
                    if parsed:
                        result['vetos'].append(parsed)
        except Exception:
            pass

        # Parse maps
        map_holders = driver.find_elements(By.CSS_SELECTOR, ".mapholder")
        for idx, mh in enumerate(map_holders, 1):
            try:
                map_data = {'map_number': idx}

                # Map name
                try:
                    name_elem = mh.find_element(By.CSS_SELECTOR, ".mapname")
                    map_data['map_name'] = name_elem.text.strip()
                except Exception:
                    continue

                # Scores
                score_elems = mh.find_elements(By.CSS_SELECTOR, ".results-team-score")
                if len(score_elems) >= 2:
                    s1 = score_elems[0].text.strip()
                    s2 = score_elems[1].text.strip()
                    if s1 != '-' and s2 != '-':
                        map_data['team1_score'] = int(s1)
                        map_data['team2_score'] = int(s2)
                    else:
                        continue  # Unplayed map

                # Half scores
                half_elems = mh.find_elements(By.CSS_SELECTOR, ".results-center-half-score")
                if len(half_elems) >= 2:
                    ct1, t1 = _parse_half_scores(half_elems[0].text.strip())
                    ct2, t2 = _parse_half_scores(half_elems[1].text.strip())
                    map_data['team1_ct_score'] = ct1
                    map_data['team1_t_score'] = t1
                    map_data['team2_ct_score'] = ct2
                    map_data['team2_t_score'] = t2

                # Pick indicator
                try:
                    pick_left = mh.find_elements(By.CSS_SELECTOR, ".results-left.pick")
                    pick_right = mh.find_elements(By.CSS_SELECTOR, ".results-right.pick")
                    if pick_left:
                        map_data['picked_by'] = result.get('team1_id')
                    elif pick_right:
                        map_data['picked_by'] = result.get('team2_id')
                except Exception:
                    pass

                # Winner
                if 'team1_score' in map_data and 'team2_score' in map_data:
                    if map_data['team1_score'] > map_data['team2_score']:
                        map_data['winner_id'] = result.get('team1_id')
                    else:
                        map_data['winner_id'] = result.get('team2_id')

                # Map stats URL (mapstatsid)
                try:
                    stats_link = mh.find_element(By.CSS_SELECTOR, "a[href*='mapstatsid']")
                    href = stats_link.get_attribute("href")
                    stats_match = re.search(r'mapstatsid/(\d+)/', href)
                    if stats_match:
                        map_data['mapstats_id'] = int(stats_match.group(1))
                except Exception:
                    pass

                result['maps'].append(map_data)
            except Exception as e:
                logger.warning("Erro ao processar mapa %d: %s", idx, e)

        print(f"  Match {match_id}: {len(result['maps'])} mapas, {len(result['vetos'])} vetos")
        return result

    except Exception as e:
        logger.error("Erro ao buscar detalhes do match %d: %s", match_id, e)
        traceback.print_exc()
        return None
    finally:
        if owns_driver:
            driver.quit()


def scrape_map_stats(mapstats_id, headless=True, driver=None):
    """Scrape per-player stats for a specific map from /stats/matches/mapstatsid/{id}/."""
    owns_driver = driver is None
    if owns_driver:
        driver = create_driver(headless=headless)

    try:
        url = f"https://www.hltv.org/stats/matches/mapstatsid/{mapstats_id}/placeholder"
        driver.get(url)
        wait_for_cloudflare(driver)
        random_delay(0.5, 1.5)

        wait = WebDriverWait(driver, 20)
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".stats-table")))

        all_stats = []

        # Extract team IDs from /stats/teams/ links on the page (first = team1, second = team2)
        page_team_ids = []
        stats_team_links = driver.find_elements(By.CSS_SELECTOR, 'a[href*="/stats/teams/"]')
        for stl in stats_team_links:
            href = stl.get_attribute("href") or ""
            tid_match = re.search(r'/stats/teams/(\d+)/', href)
            if tid_match:
                tid = int(tid_match.group(1))
                if tid not in page_team_ids:
                    page_team_ids.append(tid)

        # Two visible stats tables (one per team)
        tables = driver.find_elements(By.CSS_SELECTOR, "table.stats-table.totalstats")
        if not tables:
            tables = driver.find_elements(By.CSS_SELECTOR, ".stats-table")

        for table_idx, table in enumerate(tables):
            # Skip hidden/eco-adjusted tables
            try:
                parent = table.find_element(By.XPATH, "..")
                if 'hidden' in (parent.get_attribute("class") or ""):
                    continue
            except Exception:
                pass

            rows = table.find_elements(By.CSS_SELECTOR, "tbody tr")
            for row in rows:
                try:
                    cells = row.find_elements(By.TAG_NAME, "td")
                    if len(cells) < 9:
                        continue

                    # Player ID from link (HLTV uses /stats/players/ID/nick)
                    player_id = None
                    team_id = None
                    try:
                        player_link = row.find_element(By.CSS_SELECTOR, "a[href*='/players/']")
                        href = player_link.get_attribute("href")
                        pid_match = re.search(r'/players/(\d+)/', href)
                        if pid_match:
                            player_id = int(pid_match.group(1))
                    except Exception:
                        continue

                    if not player_id:
                        continue

                    # Assign team ID based on table position (table 0 = team1, table 1 = team2)
                    if table_idx < len(page_team_ids):
                        team_id = page_team_ids[table_idx]

                    stat = {'player_id': player_id, 'team_id': team_id, 'map_id': mapstats_id}

                    # Parse cells by class (skip hidden/eco-adjusted duplicates)
                    for cell in cells:
                        cls = cell.get_attribute("class") or ""
                        if 'hidden' in cls:
                            continue
                        text = cell.text.strip()

                        if not text:
                            continue
                        if 'st-opkd' in cls:
                            stat['opening_kills'], stat['opening_deaths'] = _parse_opening_kd(text)
                        elif 'st-mks' in cls:
                            stat['multi_kill_rounds'] = int(text) if text.isdigit() else 0
                        elif 'st-kast' in cls:
                            try:
                                stat['kast'] = float(text.replace('%', ''))
                            except ValueError:
                                pass
                        elif 'st-clutches' in cls:
                            stat['clutches_won'] = int(text) if text.isdigit() else 0
                        elif 'st-kills' in cls:
                            stat['kills'], stat['headshots'] = _parse_kills_hs(text)
                        elif 'st-assists' in cls:
                            stat['assists'], stat['flash_assists'] = _parse_kills_hs(text)
                        elif 'st-deaths' in cls:
                            stat['deaths'], _ = _parse_kills_hs(text)
                        elif 'st-adr' in cls:
                            try:
                                stat['adr'] = float(text)
                            except ValueError:
                                pass
                        elif 'st-rating' in cls:
                            try:
                                stat['rating'] = float(text)
                            except ValueError:
                                pass

                    all_stats.append(stat)
                except Exception as e:
                    logger.warning("Erro ao processar player stat row: %s", e)

        print(f"    Map {mapstats_id}: {len(all_stats)} player stats")
        return all_stats

    except Exception as e:
        logger.error("Erro ao buscar map stats %d: %s", mapstats_id, e)
        traceback.print_exc()
        return []
    finally:
        if owns_driver:
            driver.quit()
