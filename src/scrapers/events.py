"""Event scraper for HLTV."""

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from datetime import datetime
import time


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


def scrape_events(limit=None, headless=True):
    """
    Scrape events from HLTV events page.
    
    Args:
        limit: Maximum number of events to scrape (None for all)
        headless: Run browser in headless mode
        
    Returns:
        List of event dictionaries
    """
    driver = create_driver(headless=headless)
    events = []
    
    try:
        print("🌐 Acessando HLTV events page...")
        driver.get("https://www.hltv.org/events")
        
        # Wait for events to load
        wait = WebDriverWait(driver, 15)
        wait.until(EC.presence_of_element_located((By.CLASS_NAME, "events-holder")))
        
        time.sleep(2)  # Extra wait for dynamic content
        
        # Find all event containers
        event_elements = driver.find_elements(By.CSS_SELECTOR, ".big-event, .small-event")
        print(f"📋 Encontrados {len(event_elements)} eventos")
        
        if limit:
            event_elements = event_elements[:limit]
        
        for idx, event_elem in enumerate(event_elements, 1):
            try:
                # Extract event ID from link (event_elem is already the <a> tag)
                event_url = event_elem.get_attribute("href")
                event_id = int(event_url.split('/')[-2]) if event_url else None
                
                if not event_id:
                    continue
                
                # Extract event name
                try:
                    name_elem = event_elem.find_element(By.CSS_SELECTOR, ".big-event-name, .small-event-name")
                    name = name_elem.text.strip()
                except NoSuchElementException:
                    # Fallback: get text from the whole element and clean it
                    name = event_elem.text.split('\n')[0].strip()
                
                # Extract dates
                date_elem = event_elem.find_element(By.CSS_SELECTOR, "span[data-unix]")
                start_unix = int(date_elem.get_attribute("data-unix"))
                start_date = datetime.fromtimestamp(start_unix / 1000).date()
                
                # Try to get end date (might not exist for all events)
                end_date = None
                try:
                    date_text = event_elem.find_element(By.CLASS_NAME, "eventdate").text
                    # Could parse end date from text if needed
                except:
                    pass
                
                # Extract location from text-ellipsis span (contains location)
                location = None
                try:
                    # Location is usually in a text-ellipsis span within the event
                    loc_elem = event_elem.find_element(By.CSS_SELECTOR, "span.text-ellipsis")
                    location_text = loc_elem.text.strip()
                    # Filter out date-like text (e.g., "Nov 24th - Nov 27th")
                    if location_text and not any(month in location_text for month in ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']):
                        location = location_text
                except NoSuchElementException:
                    pass

                # Extract event type (big-event = LAN, small-event = Online usually)
                event_type = "LAN" if "big-event" in event_elem.get_attribute("class") else "Online"

                # Extract prize pool - not available on event list page
                # Will be scraped from individual event pages if needed
                prize_pool = None
                
                event_data = {
                    'id': event_id,
                    'name': name,
                    'start_date': start_date,
                    'end_date': end_date or start_date,
                    'location': location,
                    'event_type': event_type,
                    'prize_pool': prize_pool
                }
                
                events.append(event_data)
                print(f"✅ [{idx}/{len(event_elements)}] {name} (ID: {event_id})")
                
            except Exception as e:
                print(f"❌ Erro ao processar evento {idx}: {e}")
                continue
        
        print(f"\n✅ Total de eventos coletados: {len(events)}")
        return events
        
    except Exception as e:
        print(f"❌ Erro ao fazer scraping de eventos: {e}")
        return []
    finally:
        driver.quit()


def get_event_details(event_id, headless=True):
    """
    Get detailed event information (location, prize pool, etc.) from event page.

    Args:
        event_id: HLTV event ID
        headless: Run browser in headless mode

    Returns:
        Dictionary with event details (location, prize_pool)
    """
    driver = create_driver(headless=headless)
    details = {}

    try:
        url = f"https://www.hltv.org/events/{event_id}/a"
        print(f"🌐 Buscando detalhes do evento {event_id}...")
        driver.get(url)

        wait = WebDriverWait(driver, 15)
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        time.sleep(3)

        # Extract location
        try:
            # Look for location in various possible places
            # Method 1: Look for text-ellipsis spans that contain city/country
            location_elems = driver.find_elements(By.CSS_SELECTOR, "span.text-ellipsis")
            for elem in location_elems:
                text = elem.text.strip()
                # Location usually has a comma (City, Country)
                if ',' in text and len(text) > 3:
                    # Check it's not a date or other text
                    if not any(month in text for month in ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']):
                        details['location'] = text
                        break

            # Method 2: Look for flag icons which often indicate location
            if 'location' not in details:
                try:
                    # Sometimes location is near a flag image
                    flag_elems = driver.find_elements(By.CSS_SELECTOR, "img.flag")
                    for flag in flag_elems:
                        parent = flag.find_element(By.XPATH, "..")
                        text = parent.text.strip()
                        if text and len(text) > 2:
                            details['location'] = text
                            break
                except:
                    pass
        except Exception as e:
            print(f"  ⚠️  Não foi possível extrair location: {e}")

        # Extract prize pool
        try:
            # Look for $ signs which indicate prize money
            prize_elems = driver.find_elements(By.XPATH, "//*[contains(text(), '$')]")

            # Find the largest prize amount (usually the total prize pool)
            max_prize = None
            max_amount = 0

            for elem in prize_elems:
                text = elem.text.strip()
                # Extract number from prize text (e.g., "$1,250,000")
                import re
                match = re.search(r'\$([0-9,]+)', text)
                if match:
                    amount_str = match.group(1).replace(',', '')
                    try:
                        amount = int(amount_str)
                        if amount > max_amount:
                            max_amount = amount
                            max_prize = match.group(0)  # Keep the formatted version with $
                    except:
                        pass

            if max_prize:
                details['prize_pool'] = max_prize
        except Exception as e:
            print(f"  ⚠️  Não foi possível extrair prize_pool: {e}")

        print(f"✅ Detalhes: location={details.get('location', 'N/A')}, prize={details.get('prize_pool', 'N/A')}")
        return details

    except Exception as e:
        print(f"❌ Erro ao buscar detalhes do evento {event_id}: {e}")
        import traceback
        traceback.print_exc()
        return {}
    finally:
        driver.quit()


def get_event_teams(event_id, headless=True):
    """
    Get participating teams for a specific event.

    Args:
        event_id: HLTV event ID
        headless: Run browser in headless mode

    Returns:
        List of team IDs
    """
    driver = create_driver(headless=headless)
    teams = []

    try:
        # Use the event URL (HLTV redirects to correct name)
        url = f"https://www.hltv.org/events/{event_id}/a"
        print(f"🌐 Acessando evento {event_id}...")
        driver.get(url)

        # Wait for page to load
        time.sleep(5)

        # Find all links with /team/ in href
        all_links = driver.find_elements(By.TAG_NAME, "a")

        for link in all_links:
            try:
                team_url = link.get_attribute("href")
                if team_url and '/team/' in team_url:
                    parts = team_url.split('/')
                    if len(parts) >= 5 and parts[-3] == 'team':
                        team_id = int(parts[-2])
                        if team_id not in teams:
                            teams.append(team_id)
            except:
                continue

        print(f"✅ Encontrados {len(teams)} times no evento {event_id}")
        return teams

    except Exception as e:
        print(f"❌ Erro ao buscar times do evento {event_id}: {e}")
        import traceback
        traceback.print_exc()
        return []
    finally:
        driver.quit()


def get_event_results(event_id, headless=True):
    """
    Get event results with team placements and prizes.

    Args:
        event_id: HLTV event ID
        headless: Run browser in headless mode

    Returns:
        List of dictionaries with {team_id, placement, prize}
    """
    driver = create_driver(headless=headless)
    results = []

    try:
        url = f"https://www.hltv.org/events/{event_id}/a"
        print(f"🌐 Buscando resultados do evento {event_id}...")
        driver.get(url)

        wait = WebDriverWait(driver, 15)
        # Wait for any content to load
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        time.sleep(3)

        # Try to find placement/prize information
        # HLTV structure varies, common patterns:
        # 1. Look for "placement" or "#1", "#2" text
        # 2. Look for prize money near team names
        # 3. Check for structured results tables

        # Pattern 1: Look for placement indicators (1st, 2nd, 3rd-4th, etc.)
        placement_elements = driver.find_elements(By.XPATH, "//*[contains(text(), '1st') or contains(text(), '2nd') or contains(text(), '3rd') or contains(text(), '4th')]")

        for elem in placement_elements:
            try:
                # Get the placement text
                placement_text = elem.text.strip()

                # Try to find nearby team link
                parent = elem.find_element(By.XPATH, "..")
                team_links = parent.find_elements(By.CSS_SELECTOR, "a[href*='/team/']")

                if team_links:
                    team_url = team_links[0].get_attribute("href")
                    team_id = int(team_url.split('/')[-2])

                    # Parse placement number
                    placement = None
                    if '1st' in placement_text:
                        placement = 1
                    elif '2nd' in placement_text:
                        placement = 2
                    elif '3rd' in placement_text:
                        placement = 3
                    elif '4th' in placement_text:
                        placement = 4

                    # Try to find prize nearby
                    prize = None
                    try:
                        # Look for text with $ sign in nearby elements
                        prize_elems = parent.find_elements(By.XPATH, ".//*[contains(text(), '$')]")
                        if prize_elems:
                            prize = prize_elems[0].text.strip()
                    except:
                        pass

                    results.append({
                        'team_id': team_id,
                        'placement': placement,
                        'prize': prize
                    })
            except:
                continue

        print(f"✅ Encontrados resultados de {len(results)} times")
        return results

    except Exception as e:
        print(f"❌ Erro ao buscar resultados do evento {event_id}: {e}")
        import traceback
        traceback.print_exc()
        return []
    finally:
        driver.quit()
