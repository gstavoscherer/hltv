#!/usr/bin/env python3
"""Script de teste para verificar estrutura HTML do HLTV."""

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

def create_driver(headless=True):
    """Create and configure Chrome driver."""
    options = webdriver.ChromeOptions()
    options.binary_location = '/usr/bin/chromium'

    if headless:
        options.add_argument('--headless')

    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--disable-software-rasterizer')
    options.add_argument('--disable-extensions')
    options.add_argument('--disable-setuid-sandbox')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    options.add_argument('--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

    driver = webdriver.Chrome(options=options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    return driver

def test_player_page():
    """Test player page structure."""
    driver = create_driver(headless=True)

    try:
        # Test with s1mple (7998)
        player_id = 7998
        url = f"https://www.hltv.org/stats/players/{player_id}/s1mple"
        print(f"\n{'='*70}")
        print(f"Testing player page: {player_id}")
        print(f"{'='*70}\n")

        driver.get(url)
        wait = WebDriverWait(driver, 15)
        wait.until(EC.presence_of_element_located((By.CLASS_NAME, "stats-row")))
        time.sleep(3)

        # Test stats-row elements
        print("Stats rows:")
        stats_rows = driver.find_elements(By.CLASS_NAME, "stats-row")
        for i, row in enumerate(stats_rows[:10]):  # First 10 rows
            try:
                spans = row.find_elements(By.TAG_NAME, "span")
                if len(spans) >= 2:
                    label = spans[0].text.strip()
                    value = spans[1].text.strip()
                    print(f"  [{i}] {label}: {value}")
            except:
                pass

        # Test summary stat boxes
        print("\nSummary stat boxes:")
        try:
            stat_boxes = driver.find_elements(By.CSS_SELECTOR, ".statistics .col")
            for i, box in enumerate(stat_boxes):
                try:
                    # Look for value and label
                    value_elem = box.find_element(By.CSS_SELECTOR, ".stats-row span:first-child")
                    label_elem = box.find_element(By.CSS_SELECTOR, ".stats-row span:last-child")
                    print(f"  [{i}] {label_elem.text}: {value_elem.text}")
                except:
                    pass
        except Exception as e:
            print(f"  Error: {e}")

        # Try alternative selectors
        print("\nAlternative stat extraction:")
        try:
            # Look for all elements with class containing 'stat'
            all_stats = driver.find_elements(By.CSS_SELECTOR, "[class*='stat']")
            print(f"  Found {len(all_stats)} elements with 'stat' in class")
        except:
            pass

        # Save page source for inspection
        with open('/home/gst/Workspace/hltv/player_page_source.html', 'w') as f:
            f.write(driver.page_source)
        print("\n✅ Page source saved to player_page_source.html")

    finally:
        driver.quit()

def test_event_page():
    """Test event page structure."""
    driver = create_driver(headless=True)

    try:
        # Test with recent event (PGL Major Copenhagen 2024 - 7148)
        event_id = 7148
        url = f"https://www.hltv.org/events/{event_id}/pgl-major-copenhagen-2024"
        print(f"\n{'='*70}")
        print(f"Testing event page: {event_id}")
        print(f"{'='*70}\n")

        driver.get(url)
        time.sleep(5)

        # Look for event details
        print("Event details:")

        # Try to find location
        try:
            # Try multiple selectors
            selectors = [
                ".location",
                ".event-location",
                "[class*='location']",
                "span.text-ellipsis"
            ]

            for selector in selectors:
                try:
                    elem = driver.find_element(By.CSS_SELECTOR, selector)
                    print(f"  Location ({selector}): {elem.text}")
                    break
                except:
                    pass
        except Exception as e:
            print(f"  Location not found: {e}")

        # Try to find prize pool
        try:
            selectors = [
                ".prizepool",
                ".event-prize",
                "[class*='prize']",
            ]

            for selector in selectors:
                try:
                    elem = driver.find_element(By.CSS_SELECTOR, selector)
                    print(f"  Prize ({selector}): {elem.text}")
                    break
                except:
                    pass
        except Exception as e:
            print(f"  Prize not found: {e}")

        # Look for all divs with text
        print("\nSearching for $ (prize) and location keywords:")
        try:
            all_text = driver.find_elements(By.XPATH, "//*[contains(text(), '$')]")[:5]
            for elem in all_text:
                print(f"  $ found: {elem.text[:100]}")
        except:
            pass

        # Save page source
        with open('/home/gst/Workspace/hltv/event_page_source.html', 'w') as f:
            f.write(driver.page_source)
        print("\n✅ Page source saved to event_page_source.html")

    finally:
        driver.quit()

def test_events_list():
    """Test events list page structure."""
    driver = create_driver(headless=True)

    try:
        url = "https://www.hltv.org/events"
        print(f"\n{'='*70}")
        print(f"Testing events list page")
        print(f"{'='*70}\n")

        driver.get(url)
        wait = WebDriverWait(driver, 15)
        wait.until(EC.presence_of_element_located((By.CLASS_NAME, "events-holder")))
        time.sleep(2)

        # Find first event
        event_elements = driver.find_elements(By.CSS_SELECTOR, ".big-event, .small-event")
        if event_elements:
            first_event = event_elements[0]
            print(f"First event HTML:\n{first_event.get_attribute('outerHTML')[:500]}")

            # Try to find location and prize
            print("\nSearching for location and prize in first event:")

            # Location
            try:
                loc = first_event.find_element(By.CSS_SELECTOR, ".location, .text-ellipsis, [class*='location']")
                print(f"  Location: {loc.text}")
            except:
                print("  Location: Not found")

            # Prize
            try:
                prize = first_event.find_element(By.CSS_SELECTOR, ".prizepool, [class*='prize']")
                print(f"  Prize: {prize.text}")
            except:
                print("  Prize: Not found")

            # All text in event
            print(f"\nAll text in first event:\n{first_event.text}")

    finally:
        driver.quit()

if __name__ == '__main__':
    test_player_page()
    test_event_page()
    test_events_list()
