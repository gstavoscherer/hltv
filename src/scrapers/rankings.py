"""
Scraper de ranking HLTV.
Pagina: https://www.hltv.org/ranking/teams/YYYY/month/DD
"""

import re
import logging
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from src.scrapers.selenium_helpers import create_driver, wait_for_cloudflare, random_delay

logger = logging.getLogger(__name__)


def scrape_rankings(date_str=None, headless=True, driver=None):
    """
    Scrape HLTV team rankings.
    date_str: formato 'YYYY/month/DD' (ex: '2026/march/23')
              se None, usa a pagina default (ranking mais recente)
    Retorna lista de dicts: [{'rank': 1, 'team_id': 4608, 'team_name': 'Navi', 'points': 923}, ...]
    """
    own_driver = driver is None
    if own_driver:
        driver = create_driver(headless=headless)

    try:
        if date_str:
            url = f"https://www.hltv.org/ranking/teams/{date_str}"
        else:
            url = "https://www.hltv.org/ranking/teams"

        print(f"Buscando ranking HLTV: {url}")
        driver.get(url)
        wait_for_cloudflare(driver)
        random_delay(3.0, 5.0)

        wait = WebDriverWait(driver, 20)
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".ranked-team")))

        teams = []
        ranked_elements = driver.find_elements(By.CSS_SELECTOR, ".ranked-team")
        print(f"  {len(ranked_elements)} times encontrados no ranking")

        for elem in ranked_elements:
            try:
                # Rank number
                rank_elem = elem.find_element(By.CSS_SELECTOR, ".position")
                rank_text = rank_elem.text.strip().replace('#', '')
                rank = int(rank_text) if rank_text.isdigit() else None

                # Team name
                name_elem = elem.find_element(By.CSS_SELECTOR, ".name")
                team_name = name_elem.text.strip()

                # Team ID from link
                team_id = None
                try:
                    link = elem.find_element(By.CSS_SELECTOR, "a.moreLink")
                    href = link.get_attribute("href") or ""
                    m = re.search(r'/team/(\d+)/', href)
                    if m:
                        team_id = int(m.group(1))
                except Exception:
                    pass

                # Points
                points = None
                try:
                    points_elem = elem.find_element(By.CSS_SELECTOR, ".points")
                    points_text = points_elem.text.strip()
                    points_match = re.search(r'(\d+)', points_text)
                    if points_match:
                        points = int(points_match.group(1))
                except Exception:
                    pass

                if rank and team_name:
                    teams.append({
                        'rank': rank,
                        'team_id': team_id,
                        'team_name': team_name,
                        'points': points,
                    })

            except Exception as e:
                continue

        print(f"  {len(teams)} times com ranking extraido")
        return teams

    except Exception as e:
        logger.error("Erro ao buscar ranking: %s", e)
        return []
    finally:
        if own_driver:
            driver.quit()
