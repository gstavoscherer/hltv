"""Team scraper for HLTV with retry system."""

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    WebDriverException
)
import time


# ==========================
# DRIVER CREATOR
# ==========================
def create_driver(headless=True):
    """Create and configure Chrome driver."""
    options = webdriver.ChromeOptions()

    if headless:
        options.add_argument('--headless=new')

    # Essential options for VPS/headless environments
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--disable-software-rasterizer')
    options.add_argument('--disable-extensions')
    options.add_argument('--disable-setuid-sandbox')
    options.add_argument('--single-process')
    options.add_argument('--remote-debugging-port=9222')

    # Anti-detection options
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)

    # Set user agent to avoid detection
    options.add_argument('--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

    driver = webdriver.Chrome(options=options)
    driver.execute_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    )

    return driver


# ==========================
# SCRAPE TEAM (WITH RETRIES)
# ==========================
def scrape_team(team_id, headless=True, max_retries=3):

    attempt = 0
    last_error = None

    while attempt < max_retries:
        attempt += 1
        print(f"\n🌐 Tentativa {attempt}/{max_retries} para time {team_id}...")

        driver = None
        try:
            driver = create_driver(headless=headless)

            url = f"https://www.hltv.org/team/{team_id}/placeholder"
            driver.get(url)

            wait = WebDriverWait(driver, 10)
            wait.until(EC.presence_of_element_located((By.CLASS_NAME, "teamProfile")))

            time.sleep(1)

            # Team name
            name_elem = driver.find_element(By.CLASS_NAME, "profile-team-name")
            name = name_elem.text.strip()

            # Country
            try:
                country_elem = driver.find_element(By.CSS_SELECTOR, ".team-country")
                country = country_elem.get_attribute("title") or country_elem.text.strip()
            except NoSuchElementException:
                country = None

            # World Rank
            try:
                rank_elem = driver.find_element(By.CSS_SELECTOR, ".profile-team-stat .right")
                txt = rank_elem.text.strip().replace("#", "")
                world_rank = int(txt) if txt.isdigit() else None
            except:
                world_rank = None

            # Team data
            team_data = {
                "id": team_id,
                "name": name,
                "country": country,
                "world_rank": world_rank,
            }

            # ---------------------------
            # Roster
            # ---------------------------
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
                    except:
                        continue

                print(f"✅ Time: {name} | Roster: {len(roster)} jogadores")

            except Exception as e:
                print(f"⚠️ Erro ao buscar roster de {team_id}: {e}")

            return {"team": team_data, "roster": roster}

        except Exception as e:
            last_error = e
            print(f"❌ Erro na tentativa {attempt} do time {team_id}: {e}")
            print("🔁 Reiniciando navegador e tentando novamente...")

            time.sleep(2)  # rest DNS, evitar flood
            if driver:
                try:
                    driver.quit()
                except:
                    pass

        finally:
            if driver:
                try:
                    driver.quit()
                except:
                    pass

    print(f"\n❌ Falha final ao coletar time {team_id} após {max_retries} tentativas.")
    print(f"Último erro: {last_error}")
    return None


# ==========================
# SCRAPE MULTIPLE TEAMS
# ==========================
def scrape_teams(team_ids, headless=True):
    results = []

    for idx, team_id in enumerate(team_ids, 1):
        print(f"\n[{idx}/{len(team_ids)}] Processando time {team_id}...")

        data = scrape_team(team_id, headless=headless)

        if data:
            results.append(data)

        time.sleep(1.5)

    print(f"\n🏁 Finalizado — Times coletados: {len(results)}")
    return results
