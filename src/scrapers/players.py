"""Player scraper for HLTV."""

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import time
import re


def create_driver(headless=True):
    """Create and configure Chrome driver."""
    options = webdriver.ChromeOptions()

    # Explicitly set Chromium binary location
    options.binary_location = '/usr/bin/chromium'

    if headless:
        options.add_argument('--headless')  # Using old headless mode for VPS compatibility

    # Essential options for VPS/headless environments
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--disable-software-rasterizer')
    options.add_argument('--disable-extensions')
    options.add_argument('--disable-setuid-sandbox')

    # Anti-detection options
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)

    # Set user agent to avoid detection
    options.add_argument('--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

    driver = webdriver.Chrome(options=options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

    return driver


def parse_stat_value(text):
    """Parse stat value from text, handling various formats."""
    if not text:
        return None
    
    # Remove commas and whitespace
    text = text.strip().replace(',', '')
    
    # Try to extract number
    match = re.search(r'[\d.]+', text)
    if match:
        try:
            value = float(match.group())
            return value
        except:
            return None
    return None


def scrape_player(player_id, headless=True):
    """
    Scrape player information and career stats from HLTV.

    Args:
        player_id: HLTV player ID
        headless: Run browser in headless mode

    Returns:
        Dictionary with player data and career stats
    """
    driver = create_driver(headless=headless)

    try:
        url = f"https://www.hltv.org/stats/players/{player_id}/placeholder"
        print(f"🌐 Acessando jogador {player_id}...")
        driver.get(url)

        # Wait for stats-row elements to load
        wait = WebDriverWait(driver, 15)
        wait.until(EC.presence_of_element_located((By.CLASS_NAME, "stats-row")))

        time.sleep(3)  # Extra wait for JavaScript to fully load

        player_data = {'id': player_id}

        # Extract nickname and real name from page title
        title = driver.title
        nickname_match = re.search(r"'([^']+)'", title)
        if nickname_match:
            player_data['nickname'] = nickname_match.group(1)

        name_match = re.search(r'^([^\']+)\s+\'', title)
        if name_match:
            player_data['real_name'] = name_match.group(1).strip()

        # Extract country from player summary flag
        try:
            country_elem = driver.find_element(By.CSS_SELECTOR, ".player-summary-stat-box-left-flag .flag")
            player_data['country'] = country_elem.get_attribute("title")
        except:
            pass

        # Extract age from player summary
        try:
            age_elem = driver.find_element(By.CSS_SELECTOR, ".player-summary-stat-box-left-player-age")
            age_text = age_elem.text.strip()
            age_match = re.search(r'(\d+)', age_text)
            if age_match:
                player_data['age'] = int(age_match.group(1))
        except:
            pass

        try:
            team_elem = driver.find_element(By.CSS_SELECTOR, ".playerTeam a")
            team_url = team_elem.get_attribute("href")
            if team_url and '/team/' in team_url:
                player_data['current_team_id'] = int(team_url.split('/')[-2])
        except:
            pass

        # Extract career stats from stats-row elements
        stats_rows = driver.find_elements(By.CLASS_NAME, "stats-row")

        for row in stats_rows:
            try:
                spans = row.find_elements(By.TAG_NAME, "span")
                if len(spans) >= 2:
                    label = spans[0].text.strip().lower()
                    value = spans[1].text.strip()

                    # Map labels to database fields
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
            except:
                continue

        # Extract Rating 2.0 and KAST from summary stat boxes
        try:
            # Find all stat box data wrappers
            stat_wrappers = driver.find_elements(By.CSS_SELECTOR, ".player-summary-stat-box-data-wrapper")

            for wrapper in stat_wrappers:
                try:
                    # Get the label (what stat this is)
                    label_elem = wrapper.find_element(By.CSS_SELECTOR, ".player-summary-stat-box-data-text")
                    label = label_elem.text.strip().lower()

                    # Get the value
                    value_elem = wrapper.find_element(By.CSS_SELECTOR, ".player-summary-stat-box-data")
                    value_text = value_elem.text.strip().replace('%', '').replace(',', '')

                    if not value_text or value_text == 'N/A':
                        continue

                    # Map the stat to database field
                    if 'kast' in label:
                        player_data['kast'] = float(value_text)
                    elif 'kpr' in label or 'kills per round' in label:
                        player_data['kpr'] = float(value_text)
                    elif 'adr' in label or 'average damage' in label:
                        player_data['adr'] = float(value_text)
                    elif 'impact' in label:
                        player_data['impact'] = float(value_text)
                except:
                    continue
        except:
            pass

        # Extract Rating 1.0 from the rating box (use as fallback for rating_2_0)
        try:
            rating_elem = driver.find_element(By.CSS_SELECTOR, ".player-summary-stat-box-rating-data-text")
            rating_text = rating_elem.text.strip()
            if rating_text and rating_text != 'N/A':
                player_data['rating_2_0'] = float(rating_text)
        except:
            pass

        nickname = player_data.get('nickname', 'Unknown')
        rating = player_data.get('rating_2_0', 'N/A')
        print(f"✅ Jogador: {nickname} | Rating: {rating}")

        return player_data

    except Exception as e:
        print(f"❌ Erro ao fazer scraping do jogador {player_id}: {e}")
        import traceback
        traceback.print_exc()
        return None
    finally:
        driver.quit()


def scrape_players(player_ids, headless=True):
    """
    Scrape multiple players.
    
    Args:
        player_ids: List of HLTV player IDs
        headless: Run browser in headless mode
        
    Returns:
        List of player data dictionaries
    """
    results = []
    
    for idx, player_id in enumerate(player_ids, 1):
        print(f"\n[{idx}/{len(player_ids)}] Processando jogador {player_id}...")
        
        player_data = scrape_player(player_id, headless=headless)
        
        if player_data:
            results.append(player_data)
        
        # Delay between requests
        if idx < len(player_ids):
            time.sleep(2)
    
    print(f"\n✅ Total de jogadores coletados: {len(results)}")
    return results


def scrape_event_stats(event_id, headless=True):
    """
    Scrape player statistics for a specific event.
    
    Args:
        event_id: HLTV event ID
        headless: Run browser in headless mode
        
    Returns:
        List of player stats for the event
    """
    driver = create_driver(headless=headless)
    
    try:
        url = f"https://www.hltv.org/stats/events/{event_id}/placeholder"
        print(f"🌐 Acessando stats do evento {event_id}...")
        driver.get(url)
        
        wait = WebDriverWait(driver, 10)
        wait.until(EC.presence_of_element_located((By.CLASS_NAME, "stats-table")))
        
        time.sleep(2)
        
        stats = []
        
        # Find player rows in stats table
        player_rows = driver.find_elements(By.CSS_SELECTOR, ".stats-table tbody tr")
        
        for row in player_rows:
            try:
                # Get player ID
                player_link = row.find_element(By.CSS_SELECTOR, "td.playerCol a")
                player_url = player_link.get_attribute("href")
                
                if not player_url or '/player/' not in player_url:
                    continue
                
                player_id = int(player_url.split('/')[-2])
                
                # Get stats from columns
                cells = row.find_elements(By.TAG_NAME, "td")
                
                stat_data = {
                    'player_id': player_id,
                    'event_id': event_id
                }
                
                # Parse stats based on column positions (adjust as needed)
                if len(cells) >= 3:
                    # Usually: Player | Maps | Rating | K-D
                    try:
                        stat_data['maps_played'] = int(parse_stat_value(cells[1].text) or 0)
                        stat_data['rating'] = parse_stat_value(cells[2].text)
                        
                        if len(cells) >= 4:
                            kd_text = cells[3].text.strip()
                            stat_data['kd_ratio'] = parse_stat_value(kd_text)
                    except:
                        pass
                
                stats.append(stat_data)
                
            except Exception as e:
                continue
        
        print(f"✅ Stats do evento {event_id}: {len(stats)} jogadores")
        return stats
        
    except Exception as e:
        print(f"❌ Erro ao buscar stats do evento {event_id}: {e}")
        return []
    finally:
        driver.quit()
