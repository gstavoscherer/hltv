#!/usr/bin/env python3
"""
event_scraper.py

Faz scraping detalhado de um evento específico usando dados do hltv_events.json.
O evento deve primeiro estar presente no arquivo JSON gerado pelo events.py.

Usage:
    python event_scraper.py [--visible] <event_id>

Example:
    python events.py                        # Primeiro gera hltv_events.json
    python event_scraper.py --visible 8067  # Depois faz scraping do evento 8067
"""

from playwright.sync_api import sync_playwright
from datetime import datetime
import argparse
import time
import json
import re
import ssl

# Fix SSL certificate issues for Selenium
ssl._create_default_https_context = ssl._create_unverified_context

# Try to import Selenium with undetected-chromedriver
try:
    import undetected_chromedriver as uc
    from selenium.webdriver.common.by import By
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False
    print("⚠️  Selenium não disponível. Stats serão extraídos com Playwright (pode falhar no Cloudflare)")


BASE = "https://www.hltv.org"
EVENT_PATH = "/events/{id}"                         # base event page
EVENT_MATCHES = "/events/{id}/matches"              # matches tab (recommended)
EVENT_RESULTS = "/results?event={id}"               # results listing for event
EVENT_STATS = "/stats?event={id}"                   # stats page for event

# tuning
RETRY_ATTEMPTS = 3
DELAY_BETWEEN_NAV = 2.5   # fixed delay (seconds) after opening a page
NAV_TIMEOUT = 60_000


def convert_unix_ms_to_str(unix_ms):
    try:
        return datetime.fromtimestamp(int(unix_ms) / 1000).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return None


def is_cloudflare_page(content: str) -> bool:
    """
    Detecta página de Cloudflare *real* — evita falsos positivos.
    Requer pelo menos 2 sinais fortes para retornar True.
    """
    if not content:
        return False
    text = content.lower()
    challenge_signals = [
        "<title>just a moment...</title>",
        "checking your browser before accessing",
        "cf-browser-verification",
        "wait while we check your browser",
        "please enable javascript and cookies",
        "attention required!",
    ]
    matches = [s for s in challenge_signals if s in text]
    return len(matches) >= 2


def open_page_new_browser(url: str, headless=True, attempt_info="") -> dict:
    """
    Abre um novo navegador/chromium, faz goto(url) e retorna dict:
    { "page": Page, "browser": Browser, "context": Context, "content": str }
    Caller must close browser when done (browser.close()).
    """
    p = sync_playwright().start()
    browser = p.chromium.launch(headless=headless, slow_mo=0)
    context = browser.new_context(
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/118.0.0.0 Safari/537.36"
        )
    )
    page = context.new_page()
    page.set_default_navigation_timeout(NAV_TIMEOUT)
    page.set_default_timeout(NAV_TIMEOUT)
    page.goto(url, timeout=NAV_TIMEOUT)
    # small fixed wait to let JS run (HLTV relies on scripts)
    time.sleep(DELAY_BETWEEN_NAV)
    content = page.content()
    return {"p": p, "browser": browser, "context": context, "page": page, "content": content}


def safe_click_accept_cookies(page):
    try:
        el = page.locator("text=Accept All Cookies")
        if el.count() > 0:
            el.first.click(timeout=3000)
            time.sleep(0.3)
    except Exception:
        pass


def scrape_stats_with_selenium(event_id: int, headless=True) -> dict:
    """
    Scrape stats page using Selenium with undetected-chromedriver to bypass Cloudflare.
    Returns dict with top_players and top_teams.

    Note: headless mode doesn't work well with Cloudflare, so we force headless=False
    """
    stats_data = {
        "top_players": [],
        "top_teams": []
    }

    if not SELENIUM_AVAILABLE:
        print("  ⚠️  Selenium não disponível, pulando stats...")
        return stats_data

    print(f"  🔍 Usando Selenium para extrair stats do evento {event_id}...")

    # Configure undetected Chrome
    # Force headless=False because Cloudflare detects headless mode
    options = uc.ChromeOptions()
    # Don't use headless mode - it gets detected by Cloudflare
    # if headless:
    #     options.add_argument('--headless=new')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1920,1080')

    driver = None
    try:
        # Create driver with undetected-chromedriver (force headless=False for Cloudflare)
        driver = uc.Chrome(options=options, headless=False, use_subprocess=False, version_main=None)
        driver.set_window_size(1920, 1080)

        # Navigate to stats page
        stats_url = f"{BASE}/stats?event={event_id}"
        print(f"  🌐 Navegando para: {stats_url}")
        driver.get(stats_url)

        # Wait for page load
        time.sleep(5)

        # Check if we hit Cloudflare
        page_title = driver.title
        if "Just a moment" in page_title or "Um momento" in page_title:
            print("  ⚠️  Cloudflare detectado! Aguardando...")
            time.sleep(30)  # Aumentado de 20 para 30 segundos
            page_title = driver.title

        if "Just a moment" in page_title or "Um momento" in page_title:
            print("  ❌ Cloudflare ainda presente. Stats não extraídos.")
            return stats_data

        print(f"  ✅ Página carregada: {page_title}")

        # Extract top players
        try:
            player_boxes = driver.find_elements(By.CSS_SELECTOR, ".top-x-box")

            for i, box in enumerate(player_boxes[:8]):
                try:
                    # Check if it's a player box (has .playerPicture)
                    pic_elems = box.find_elements(By.CSS_SELECTOR, ".playerPicture")
                    if not pic_elems:
                        continue

                    # Find player name
                    name_elem = box.find_element(By.CSS_SELECTOR, "a.name")
                    player_name = name_elem.text.strip()
                    player_url = name_elem.get_attribute("href")

                    # Find rating
                    rating_elem = box.find_element(By.CSS_SELECTOR, ".rating .bold")
                    rating = rating_elem.text.strip()

                    # Find maps played (if available)
                    maps = None
                    try:
                        maps_elem = box.find_element(By.CSS_SELECTOR, ".average .bold")
                        maps = maps_elem.text.strip()
                    except:
                        pass

                    player_data = {
                        "name": player_name,
                        "url": player_url,
                        "rating": rating
                    }
                    if maps:
                        player_data["maps"] = maps

                    stats_data["top_players"].append(player_data)
                except Exception:
                    continue
        except Exception as e:
            print(f"  ⚠️  Erro extraindo players: {e}")

        # Extract top teams
        try:
            all_boxes = driver.find_elements(By.CSS_SELECTOR, ".top-x-box")

            for box in all_boxes:
                try:
                    # Check if it's NOT a player box (no .playerPicture)
                    pic_elems = box.find_elements(By.CSS_SELECTOR, ".playerPicture")
                    if pic_elems:
                        continue  # Skip player boxes

                    # Try to find team info
                    name_elem = box.find_element(By.CSS_SELECTOR, "a.name")
                    team_name = name_elem.text.strip()
                    team_url = name_elem.get_attribute("href")

                    # Find logo
                    logo_url = None
                    try:
                        logo_elem = box.find_element(By.CSS_SELECTOR, "img.logo")
                        logo_url = logo_elem.get_attribute("src")
                    except:
                        pass

                    team_data = {
                        "name": team_name,
                        "url": team_url
                    }
                    if logo_url:
                        team_data["logo"] = logo_url

                    stats_data["top_teams"].append(team_data)

                    # Stop after 8 teams
                    if len(stats_data["top_teams"]) >= 8:
                        break

                except Exception:
                    continue
        except Exception as e:
            print(f"  ⚠️  Erro extraindo teams: {e}")

        print(f"  ✅ Stats extraídos: {len(stats_data['top_players'])} players, {len(stats_data['top_teams'])} teams")

    except Exception as e:
        print(f"  ❌ Erro durante scraping com Selenium: {e}")
    finally:
        if driver:
            driver.quit()

    return stats_data


def scrape_overview(event_id: int, event_link: str = None, headless=True):
    """
    event_link: full link from JSON like https://www.hltv.org/events/8067/thunderpick-world-championship-2025
    If not provided, falls back to just the ID (which may not work)
    """
    if event_link:
        url = event_link  # Usa o link completo do JSON
    else:
        url = BASE + EVENT_PATH.format(id=event_id)  # Fallback (pode não funcionar)

    print(f"  🌐 URL overview: {url}")
    for attempt in range(1, RETRY_ATTEMPTS + 1):
        try:
            print(f"  🔄 Tentativa {attempt}/{RETRY_ATTEMPTS}...")
            sess = open_page_new_browser(url, headless=headless, attempt_info=f"overview attempt {attempt}")
            page = sess["page"]
            content = sess["content"]

            # quick cloudflare detection
            if is_cloudflare_page(content):
                print(f"⚠️ Cloudflare detected on {url} (attempt {attempt}/{RETRY_ATTEMPTS}). Closing browser and retrying...")
                sess["browser"].close()
                sess["p"].stop()
                time.sleep(1.0 + attempt)  # backoff
                continue

            safe_click_accept_cookies(page)
            print(f"  ✅ Página carregada, extraindo dados...")

            # DEBUG: salva HTML para inspeção
            with open(f"debug_overview_{event_id}.html", "w", encoding="utf-8") as f:
                f.write(content)
            print(f"  💾 HTML salvo em debug_overview_{event_id}.html")

            overview = {"location": None, "prize_pool": None, "teams": None, "start_date": None, "end_date": None,
                        "map_pool": [], "formats": {}, "related_events": [], "teams_attending": [], "image": None}

            # Event logo/image
            try:
                event_logo = page.query_selector(".event-hub-header-logo img")
                if event_logo:
                    overview["image"] = event_logo.get_attribute("src")
                    print(f"  🖼️  Logo: {overview['image']}")
            except Exception:
                pass

            # Event data box (table) - estrutura real: <table class="info"> com <tbody> <td>
            try:
                # Busca a tabela .info e pega os dados do tbody
                info_table = page.query_selector("table.info")
                print(f"  📊 Tabela .info encontrada: {info_table is not None}")

                if info_table:
                    # Extrai dados das células
                    date_cell = info_table.query_selector("td.eventdate")
                    prize_cell = info_table.query_selector("td.prizepool")
                    teams_cell = info_table.query_selector("td.teamsNumber")
                    location_cell = info_table.query_selector("td.location")

                    if date_cell:
                        # Pega os timestamps Unix dos spans com data-unix
                        date_spans = date_cell.query_selector_all("span[data-unix]")
                        if len(date_spans) >= 2:
                            # Duas datas: start e end
                            overview["start_unix"] = date_spans[0].get_attribute("data-unix")
                            overview["end_unix"] = date_spans[1].get_attribute("data-unix")
                            overview["start_date"] = convert_unix_ms_to_str(overview["start_unix"])
                            overview["end_date"] = convert_unix_ms_to_str(overview["end_unix"])
                            print(f"  📅 Datas: {overview['start_date']} - {overview['end_date']}")
                        elif len(date_spans) == 1:
                            # Uma data só
                            overview["start_unix"] = date_spans[0].get_attribute("data-unix")
                            overview["end_unix"] = overview["start_unix"]
                            overview["start_date"] = convert_unix_ms_to_str(overview["start_unix"])
                            overview["end_date"] = overview["start_date"]
                            print(f"  📅 Data: {overview['start_date']}")
                        else:
                            # Fallback: pega o texto visível
                            date_text = date_cell.inner_text().strip()
                            overview["start_date"] = date_text
                            overview["end_date"] = date_text
                            print(f"  📅 Datas (texto): {date_text}")

                    if prize_cell:
                        prize = prize_cell.inner_text().strip()
                        print(f"  💰 Prize pool: {prize}")
                        overview["prize_pool"] = prize

                    if teams_cell:
                        teams = teams_cell.inner_text().strip()
                        print(f"  👥 Teams: {teams}")
                        overview["teams"] = teams

                    if location_cell:
                        location_span = location_cell.query_selector("span.text-ellipsis")
                        if location_span:
                            location = location_span.inner_text().strip()
                            print(f"  🌍 Location: {location}")
                            overview["location"] = location

                        # Extrair tipo de evento da localização
                        # Formato: "Online Europe" ou "Intl. LAN Sweden" etc
                        location_full = location_cell.inner_text().strip()
                        if "Online" in location_full:
                            overview["type"] = "Online"
                        elif "LAN" in location_full:
                            if "Intl." in location_full:
                                overview["type"] = "LAN"
                            elif "Reg." in location_full:
                                overview["type"] = "Regional"
                            elif "Local" in location_full:
                                overview["type"] = "Local"
                            else:
                                overview["type"] = "LAN"
                        print(f"  🎮 Type: {overview.get('type', 'Unknown')}")

                # Fallback antigo caso a estrutura mude
                rows = page.query_selector_all(".event-data tr")
                print(f"  📊 Fallback: Encontradas {len(rows)} linhas com .event-data tr")
                for r in rows:
                    th = r.query_selector("th")
                    td = r.query_selector("td")
                    if not (th and td):
                        continue
                    key = th.inner_text().strip().lower()
                    val = td.inner_text().strip()
                    if "start date" in key:
                        overview["start_date"] = val
                    elif "end date" in key:
                        overview["end_date"] = val
                    elif "total prize pool" in key or "prize pool" in key:
                        overview["prize_pool"] = val
                    elif key.startswith("teams"):
                        # might be an integer or string
                        try:
                            overview["teams"] = int(re.search(r"\d+", val).group()) if re.search(r"\d+", val) else val
                        except Exception:
                            overview["teams"] = val
                    elif "location" in key:
                        # location cell might contain flag + text
                        overview["location"] = td.inner_text().strip()
            except Exception:
                pass

            # map pool (right column)
            try:
                map_nodes = page.query_selector_all(".map-pool .map")
                if not map_nodes:
                    # alternative
                    map_nodes = page.query_selector_all(".map-pool .img")
                mp = []
                for m in map_nodes:
                    text = m.inner_text().strip()
                    if text:
                        mp.append(text)
                overview["map_pool"] = mp
            except Exception:
                pass

            # related events
            try:
                related = page.query_selector_all(".related-events a")
                for r in related:
                    try:
                        href = r.get_attribute("href")
                        name = r.inner_text().strip()
                        overview["related_events"].append({"name": name, "link": BASE + href if href else None})
                    except Exception:
                        continue
            except Exception:
                pass

            # teams attending
            try:
                teams = page.query_selector_all(".event-teams a")
                if not teams:
                    # different markup
                    teams = page.query_selector_all(".teams div.team")
                for t in teams:
                    try:
                        link = t.get_attribute("href")
                        logo_img = t.query_selector("img")
                        logo = logo_img.get_attribute("src") if logo_img else None
                        name = t.inner_text().strip()
                        # if the <a> contains a nested text we might prefer the 'title' attr
                        if not name and logo_img:
                            name = logo_img.get_attribute("title") or name
                        overview["teams_attending"].append({
                            "name": name,
                            "link": (BASE + link) if link else None,
                            "logo": logo
                        })
                    except Exception:
                        continue
            except Exception:
                pass

            # bracket JSON placeholders (if present) - helpful to know upcoming matches structure
            try:
                slots = page.query_selector_all(".slotted-bracket-placeholder")
                brackets = []
                for s in slots:
                    j = s.get_attribute("data-slotted-bracket-json")
                    if j:
                        # it's HTML-escaped JSON, try unescape quotes
                        try:
                            clean = j
                            clean = clean.replace("&quot;", '"')
                            bracket_json = json.loads(clean)
                            brackets.append(bracket_json)
                        except Exception:
                            # fallback: keep raw
                            brackets.append(j)
                if brackets:
                    overview["brackets"] = brackets
            except Exception:
                pass

            sess["browser"].close()
            sess["p"].stop()
            return overview

        except Exception as exc:
            print(f"⚠️ Overview attempt {attempt} failed: {exc}")
            try:
                sess["browser"].close()
                sess["p"].stop()
            except Exception:
                pass
            time.sleep(1.0 + attempt)
            continue

    # all attempts failed
    return {"error": "failed_to_fetch_overview"}


def scrape_matches_tab(event_id: int, event_link: str = None, headless=True):
    """
    Scrape the /events/<id>/matches page (recommended to get scheduled/upcoming matches).
    event_link: base event link from JSON like https://www.hltv.org/events/8067/thunderpick-world-championship-2025
    """
    if event_link:
        url = event_link + "/matches"  # Adiciona /matches ao link completo
    else:
        url = BASE + EVENT_MATCHES.format(id=event_id)  # Fallback

    print(f"  🌐 URL matches: {url}")
    for attempt in range(1, RETRY_ATTEMPTS + 1):
        try:
            print(f"  🔄 Tentativa {attempt}/{RETRY_ATTEMPTS}...")
            sess = open_page_new_browser(url, headless=headless, attempt_info=f"matches attempt {attempt}")
            page = sess["page"]
            content = sess["content"]

            if is_cloudflare_page(content):
                print(f"⚠️ Cloudflare detected on {url} (attempt {attempt}/{RETRY_ATTEMPTS}). Retrying with new browser...")
                sess["browser"].close()
                sess["p"].stop()
                time.sleep(1.0 + attempt)
                continue

            safe_click_accept_cookies(page)
            print(f"  ✅ Página carregada, procurando partidas...")

            # DEBUG: salva HTML para inspeção
            with open(f"debug_matches_{event_id}.html", "w", encoding="utf-8") as f:
                f.write(content)
            print(f"  💾 HTML salvo em debug_matches_{event_id}.html")

            matches = []
            # HLTV uses blocks with day headers
            day_blocks = page.query_selector_all(".match-day")
            print(f"  📅 Encontrados {len(day_blocks)} blocos de dia com .match-day")
            if not day_blocks:
                # fallback
                day_blocks = page.query_selector_all(".matchDay, .match-day-wrapper, .upcoming-day")
                print(f"  📅 Tentativa alternativa: {len(day_blocks)} blocos")
            for db in day_blocks:
                # try to find header
                header = None
                try:
                    h = db.query_selector(".match-day-header, .date")
                    header = h.inner_text().strip() if h else None
                except Exception:
                    header = None

                items = db.query_selector_all(".match")
                if not items:
                    items = db.query_selector_all(".upcoming-match, .match-row, .a-reset")
                for it in items:
                    try:
                        # link to match page
                        a = it.query_selector("a[href*='/matches/']")
                        href = a.get_attribute("href") if a else None
                        link = BASE + href if href else None

                        # teams
                        t1 = it.query_selector(".matchTeam .matchTeamName, .team1 .team")
                        t2 = it.query_selector(".matchTeam .matchTeamName--away, .team2 .team")
                        team1 = t1.inner_text().strip() if t1 else None
                        team2 = t2.inner_text().strip() if t2 else None

                        # time (some entries contain data-time attr, others text)
                        time_attr = it.get_attribute("data-time") or it.get_attribute("data-zonedgrouping-entry-unix")
                        match_time = None
                        if time_attr and time_attr.isdigit():
                            match_time = convert_unix_ms_to_str(time_attr)
                        else:
                            # try to read clock text
                            try:
                                time_el = it.query_selector(".matchTime, .time")
                                match_time = time_el.inner_text().strip() if time_el else None
                            except Exception:
                                match_time = None

                        # format (bo3/bo5)
                        fmt = None
                        try:
                            fmt_el = it.query_selector(".matchMeta .mapText, .map-text, .matchMeta .format")
                            fmt = fmt_el.inner_text().strip() if fmt_el else None
                        except Exception:
                            fmt = None

                        matches.append({
                            "day": header,
                            "time": match_time,
                            "link": link,
                            "team1": team1,
                            "team2": team2,
                            "format": fmt
                        })
                    except Exception:
                        continue

            sess["browser"].close()
            sess["p"].stop()
            return matches

        except Exception as exc:
            print(f"⚠️ Matches attempt {attempt} failed: {exc}")
            try:
                sess["browser"].close()
                sess["p"].stop()
            except Exception:
                pass
            time.sleep(1.0 + attempt)
            continue

    return []


def scrape_results_tab(event_id: int, headless=True):
    """
    Scrape results?event=<id> page (finalized match results).
    """
    url = BASE + EVENT_RESULTS.format(id=event_id)
    for attempt in range(1, RETRY_ATTEMPTS + 1):
        try:
            sess = open_page_new_browser(url, headless=headless, attempt_info=f"results attempt {attempt}")
            page = sess["page"]
            content = sess["content"]

            if is_cloudflare_page(content):
                print(f"⚠️ Cloudflare detected on {url} (attempt {attempt}/{RETRY_ATTEMPTS}). Retrying with new browser...")
                sess["browser"].close()
                sess["p"].stop()
                time.sleep(1.0 + attempt)
                continue

            safe_click_accept_cookies(page)

            results = []
            # results grouped by .results-sublist
            blocks = page.query_selector_all(".results-sublist")
            if not blocks:
                # fallback to the .results-all grouping
                blocks = page.query_selector_all(".results-all .results-sublist, .results-all .result-con")
            for b in blocks:
                date_label_el = b.query_selector(".standard-headline")
                date_label = date_label_el.inner_text().strip() if date_label_el else None
                # each result-con corresponds to a match row
                rows = b.query_selector_all(".result-con")
                for r in rows:
                    try:
                        a = r.query_selector("a.a-reset")
                        href = a.get_attribute("href") if a else None
                        link = BASE + href if href else None
                        unix = r.get_attribute("data-zonedgrouping-entry-unix")
                        match_time = convert_unix_ms_to_str(unix) if unix else None

                        t1 = r.query_selector(".team1 .team")
                        t2 = r.query_selector(".team2 .team")
                        team1 = t1.inner_text().strip() if t1 else None
                        team2 = t2.inner_text().strip() if t2 else None

                        # logos
                        img1 = r.query_selector(".team1 img")
                        img2 = r.query_selector(".team2 img")
                        logo1 = img1.get_attribute("src") if img1 else None
                        logo2 = img2.get_attribute("src") if img2 else None

                        score_el = r.query_selector(".result-score")
                        score = score_el.inner_text().strip() if score_el else None

                        fmt_el = r.query_selector(".map-text, .map .map-text, .map-and-stars .map-text")
                        fmt = fmt_el.inner_text().strip() if fmt_el else None

                        # winner detection
                        winner = None
                        try:
                            if t1 and "team-won" in (t1.get_attribute("class") or ""):
                                winner = team1
                            elif t2 and "team-won" in (t2.get_attribute("class") or ""):
                                winner = team2
                        except Exception:
                            winner = None

                        results.append({
                            "date": date_label,
                            "time": match_time,
                            "match_link": link,
                            "team1": team1,
                            "team2": team2,
                            "team1_logo": logo1,
                            "team2_logo": logo2,
                            "score": score,
                            "format": fmt,
                            "winner": winner
                        })
                    except Exception:
                        continue

            sess["browser"].close()
            sess["p"].stop()
            return results

        except Exception as exc:
            print(f"⚠️ Results attempt {attempt} failed: {exc}")
            try:
                sess["browser"].close()
                sess["p"].stop()
            except Exception:
                pass
            time.sleep(1.0 + attempt)
            continue

    return []


def scrape_stats_tab(event_id: int, headless=True):
    """
    Scrape stats?event=<id> page (top players/teams and other event stats).
    If Cloudflare triggers, we'll retry with new browsers a few times.
    """
    url = BASE + EVENT_STATS.format(id=event_id)
    print(f"  🌐 URL stats: {url}")
    for attempt in range(1, RETRY_ATTEMPTS + 1):
        try:
            print(f"  🔄 Tentativa {attempt}/{RETRY_ATTEMPTS}...")
            sess = open_page_new_browser(url, headless=headless, attempt_info=f"stats attempt {attempt}")
            page = sess["page"]
            content = sess["content"]

            # Stats page sometimes triggers CF. Use the refined detector.
            if is_cloudflare_page(content):
                print(f"⚠️ Cloudflare detected on {url} (attempt {attempt}/{RETRY_ATTEMPTS}). Closing and retrying...")
                sess["browser"].close()
                sess["p"].stop()
                time.sleep(1.0 + attempt)
                continue

            safe_click_accept_cookies(page)
            print(f"  ✅ Página carregada, extraindo estatísticas...")

            # DEBUG: salva HTML
            with open(f"debug_stats_{event_id}.html", "w", encoding="utf-8") as f:
                f.write(content)
            print(f"  💾 HTML salvo em debug_stats_{event_id}.html")

            stats = {"top_players": [], "top_teams": []}

            # Top players (left column)
            try:
                player_boxes = page.query_selector_all(".columns .col .top-x-box")
                # HLTV uses .top-x-box repeated for players and teams; first column players, second column teams
                # We'll read players from first column (first .col)
                col_nodes = page.query_selector_all(".columns .col")
                print(f"  👥 Encontradas {len(col_nodes)} colunas")
                if col_nodes and len(col_nodes) >= 1:
                    player_boxes = col_nodes[0].query_selector_all(".top-x-box")
                    for pb in player_boxes:
                        try:
                            name_el = pb.query_selector("a.name")
                            name = name_el.inner_text().strip() if name_el else None
                            link = name_el.get_attribute("href") if name_el else None
                            img = pb.query_selector(".playerPicture img, .img")
                            img_src = img.get_attribute("src") if img else None
                            rating_el = pb.query_selector(".rating .bold")
                            rating = rating_el.inner_text().strip() if rating_el else None
                            maps_el = pb.query_selector(".average .bold")
                            maps = maps_el.inner_text().strip() if maps_el else None
                            stats["top_players"].append({
                                "name": name,
                                "link": BASE + link if link else None,
                                "image": img_src,
                                "rating": rating,
                                "maps": maps
                            })
                        except Exception:
                            continue
            except Exception:
                pass

            # Top teams (second column)
            try:
                if col_nodes and len(col_nodes) >= 2:
                    team_boxes = col_nodes[1].query_selector_all(".top-x-box")
                    for tb in team_boxes:
                        try:
                            name_el = tb.query_selector("a.name")
                            name = name_el.inner_text().strip() if name_el else None
                            link = name_el.get_attribute("href") if name_el else None
                            img = tb.query_selector("img.logo, .img")
                            img_src = img.get_attribute("src") if img else None
                            rating_el = tb.query_selector(".rating .bold")
                            rating = rating_el.inner_text().strip() if rating_el else None
                            maps_el = tb.query_selector(".average .bold")
                            maps = maps_el.inner_text().strip() if maps_el else None
                            stats["top_teams"].append({
                                "name": name,
                                "link": BASE + link if link else None,
                                "image": img_src,
                                "rating": rating,
                                "maps": maps
                            })
                        except Exception:
                            continue
            except Exception:
                pass

            sess["browser"].close()
            sess["p"].stop()
            return stats

        except Exception as exc:
            print(f"⚠️ Stats attempt {attempt} failed: {exc}")
            try:
                sess["browser"].close()
                sess["p"].stop()
            except Exception:
                pass
            time.sleep(1.0 + attempt)
            continue

    # couldn't fetch stats
    return {"error": "failed_to_fetch_stats"}


def build_event_payload(event_obj: dict, headless=True):
    """
    event_obj is the event dictionary you already have (from your events fetcher).
    We'll complement it with overview/matches/results/stats.
    Usa os dados do hltv_events.json como base e complementa com scraping.
    """
    event_id = event_obj.get("link", "").rstrip("/").split("/")[-1]
    # sometimes link ends with slug instead of id; prefer using 'start_unix' or user-provided id
    # but in our flow the user passes event_id separately, so prefer that. Here fallback:
    try:
        event_id_int = int(event_obj.get("link", "").split("/events/")[1].split("/")[0])
    except Exception:
        # fallback: try extraction from event_obj
        event_id_int = int(event_obj.get("event_id", 0) or event_obj.get("id", 0))

    event_id_int = int(event_id_int)

    # Usa dados do JSON como base para o overview
    base_overview = {
        "location": None,
        "prize_pool": None,
        "teams": None,
        "start_date": event_obj.get("start_date"),  # Do JSON
        "end_date": event_obj.get("end_date"),      # Do JSON
        "start_unix": event_obj.get("start_unix"),  # Do JSON
        "end_unix": event_obj.get("end_unix"),      # Do JSON
        "type": event_obj.get("type"),              # Do JSON (LAN/Online)
        "image": event_obj.get("image"),            # Do JSON
        "map_pool": [],
        "formats": {},
        "related_events": [],
        "teams_attending": []
    }

    result = {
        "event_id": event_id_int,
        "name": event_obj.get("name"),
        "base_link": event_obj.get("link"),
        "overview": base_overview,  # Já inicializa com dados do JSON
        "matches": [],
        "results": [],
        "stats": {},
        "status": "unknown"
    }

    # Overview adicional (scraping para pegar mais detalhes)
    print("📊 Fazendo scraping do overview...")
    ov_scraped = scrape_overview(event_id_int, event_link=event_obj.get("link"), headless=headless)
    # Merge: dados do JSON têm prioridade, mas scraping adiciona detalhes extras
    if ov_scraped and not ov_scraped.get("error"):
        result["overview"].update({
            "location": ov_scraped.get("location"),
            "prize_pool": ov_scraped.get("prize_pool"),
            "teams": ov_scraped.get("teams"),
            "map_pool": ov_scraped.get("map_pool", []),
            "formats": ov_scraped.get("formats", {}),
            "related_events": ov_scraped.get("related_events", []),
            "teams_attending": ov_scraped.get("teams_attending", []),
            "brackets": ov_scraped.get("brackets", [])
        })

    # Matches
    print("🎮 Fazendo scraping das partidas...")
    matches = scrape_matches_tab(event_id_int, event_link=event_obj.get("link"), headless=headless)
    result["matches"] = matches

    # Results
    print("📋 Fazendo scraping dos resultados...")
    results = scrape_results_tab(event_id_int, headless=headless)
    result["results"] = results

    # Stats - usando Selenium para bypass do Cloudflare
    print("📈 Fazendo scraping das estatísticas...")
    stats = scrape_stats_with_selenium(event_id_int, headless=headless)
    result["stats"] = stats

    # status: derive from results presence and bracket completeness
    try:
        if stats and isinstance(stats, dict) and stats.get("top_players"):
            # stats present indicates event likely finished or at least has aggregated stats
            result["status"] = "finished_or_stats_available"
        elif results and len(results) > 0:
            result["status"] = "ongoing_or_some_results"
        else:
            result["status"] = "upcoming"
    except Exception:
        result["status"] = "unknown"

    return result


def load_events_from_json(filename="hltv_events.json"):
    """Carrega eventos do arquivo JSON gerado pelo events.py"""
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"❌ Arquivo {filename} não encontrado. Execute 'python events.py' primeiro.")
        return []
    except json.JSONDecodeError as e:
        print(f"❌ Erro ao ler JSON: {e}")
        return []


def find_event_by_id(events, event_id):
    """Encontra um evento pelo ID extraído do link"""
    for event in events:
        if event.get("link"):
            try:
                # Extrai o ID do link: https://www.hltv.org/events/8067/nome-evento
                link_id = int(event["link"].split("/events/")[1].split("/")[0])
                if link_id == event_id:
                    return event
            except (IndexError, ValueError):
                continue
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("event_id", nargs="?", type=int, help="Event ID (e.g. 8067)")
    parser.add_argument("--visible", action="store_true", help="Show browser windows (headful)")
    ns = parser.parse_args()

    if not ns.event_id:
        print("Usage: python event_scraper.py [--visible] <event_id>")
        return

    headless = not ns.visible

    # Carrega eventos do JSON
    events = load_events_from_json()
    if not events:
        return

    # Busca o evento pelo ID
    event_obj = find_event_by_id(events, ns.event_id)
    if not event_obj:
        print(f"❌ Evento com ID {ns.event_id} não encontrado no hltv_events.json")
        print("Eventos disponíveis:")
        for event in events[:10]:  # Mostra só os primeiros 10
            try:
                link_id = int(event["link"].split("/events/")[1].split("/")[0])
                print(f"  ID {link_id}: {event['name']}")
            except (IndexError, ValueError):
                continue
        return

    print(f"🔍 Coletando evento: {event_obj['name']} (ID: {ns.event_id})")
    print(f"🔗 Link: {event_obj['link']}")

    payload = build_event_payload(event_obj, headless=headless)

    out_file = f"hltv_event_{ns.event_id}_full.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    print(f"✅ Feito. Salvou em {out_file}")


if __name__ == "__main__":
    main()
