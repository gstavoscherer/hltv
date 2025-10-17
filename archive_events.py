"""
Scraper para eventos arquivados do HLTV.
Página: https://www.hltv.org/events/archive
Total de eventos históricos: ~7,550+
"""

from playwright.sync_api import sync_playwright
from datetime import datetime
import time
import json
import os


def scrape_archive_events(headless=True, max_events=100, offset=0):
    """
    Scrapes archived events from HLTV.

    Args:
        headless: Run browser in headless mode
        max_events: Maximum number of events to scrape (default 100)
        offset: Start from event number (for pagination, default 0)

    Returns:
        List of event dictionaries with id, name, dates, location, prize_pool, teams
    """
    events = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless, slow_mo=50)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/118.0.0.0 Safari/537.36"
            )
        )
        page = context.new_page()

        url = f"https://www.hltv.org/events/archive?offset={offset}"
        print(f"➡️  Acessando HLTV Archive (offset={offset})...")
        page.goto(url, timeout=60000)

        # Aceita cookies se aparecer
        try:
            page.locator("text=Accept All Cookies").click(timeout=4000)
            print("✅ Cookies aceitos")
        except Exception:
            pass

        # Espera eventos carregarem
        time.sleep(2)

        # Busca todos os eventos na página
        # Formato: <a href="/events/8719/..." class="a-reset small-event standard-box">
        event_cards = page.query_selector_all("a.small-event[href*='/events/']")
        print(f"📦 Encontrados {len(event_cards)} eventos na página")

        for idx, card in enumerate(event_cards):
            if len(events) >= max_events:
                break

            try:
                # Extrai o href para pegar o ID
                href = card.get_attribute("href")
                if not href:
                    continue

                # ID está no formato: /events/8769/exort-series-17
                event_id = href.split("/")[2] if len(href.split("/")) > 2 else None

                # Nome do evento - dentro de <div class="text-ellipsis">
                event_name_elem = card.query_selector(".text-ellipsis")
                event_name = event_name_elem.inner_text().strip() if event_name_elem else "Unknown"

                # Estrutura de tabela com dados
                table_cells = card.query_selector_all("td.col-value")

                # Número de times (segunda coluna)
                teams_count = table_cells[1].inner_text().strip() if len(table_cells) > 1 else "0"

                # Prize pool (terceira coluna)
                prize_pool = table_cells[2].inner_text().strip() if len(table_cells) > 2 else "$0"

                # Formato Online/LAN (quarta coluna se existir)
                event_format = table_cells[3].inner_text().strip() if len(table_cells) > 3 else "Unknown"

                # Localização - dentro de eventDetails tr
                details_row = card.query_selector("tr.eventDetails")
                location_elem = details_row.query_selector(".smallCountry .col-desc") if details_row else None
                location = location_elem.inner_text().strip() if location_elem else "Unknown"

                # Datas - dentro dos spans com data-unix
                date_spans = details_row.query_selector_all("span[data-unix]") if details_row else []
                if len(date_spans) >= 2:
                    start_date = date_spans[0].inner_text().strip()
                    end_date = date_spans[1].inner_text().strip()
                    dates = f"{start_date} - {end_date}"
                elif len(date_spans) == 1:
                    dates = date_spans[0].inner_text().strip()
                else:
                    dates = "Unknown"

                event_data = {
                    "id": event_id,
                    "name": event_name,
                    "teams_count": teams_count,
                    "prize_pool": prize_pool,
                    "format": event_format,
                    "location": location,
                    "dates": dates,
                    "url": f"https://www.hltv.org{href}"
                }

                events.append(event_data)
                print(f"  [{idx+1}] {event_name} (ID: {event_id}) - {dates}")

            except Exception as e:
                print(f"  ⚠️  Erro ao processar evento {idx+1}: {e}")
                continue

        browser.close()

    return events


def save_archive_events(events, filename="hltv_archive_events.json"):
    """Save scraped events to JSON file"""
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(events, f, indent=2, ensure_ascii=False)
    print(f"\n✅ {len(events)} eventos salvos em {filename}")


def load_existing_events(filename="hltv_archive_events.json"):
    """Load existing events from JSON file"""
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def scrape_multiple_pages(num_pages=10, events_per_page=50):
    """
    Scrape multiple pages of archived events.

    Args:
        num_pages: Number of pages to scrape (default 10)
        events_per_page: Events per page (HLTV shows ~50 per page)

    Returns:
        List of all scraped events
    """
    all_events = load_existing_events()
    existing_ids = {e["id"] for e in all_events}

    print(f"🔍 Já temos {len(all_events)} eventos salvos")
    print(f"📄 Buscando {num_pages} páginas ({num_pages * events_per_page} eventos)")

    for page_num in range(num_pages):
        offset = page_num * events_per_page
        print(f"\n{'='*60}")
        print(f"📄 PÁGINA {page_num + 1}/{num_pages} (offset={offset})")
        print(f"{'='*60}")

        new_events = scrape_archive_events(
            headless=True,
            max_events=events_per_page,
            offset=offset
        )

        # Remove duplicatas
        unique_new = [e for e in new_events if e["id"] not in existing_ids]

        if unique_new:
            all_events.extend(unique_new)
            existing_ids.update(e["id"] for e in unique_new)
            print(f"✨ +{len(unique_new)} eventos novos (total: {len(all_events)})")
        else:
            print("⚠️  Nenhum evento novo encontrado nesta página")

        # Salva a cada página
        save_archive_events(all_events)

        # Delay entre páginas
        if page_num < num_pages - 1:
            print("⏳ Aguardando 3 segundos...")
            time.sleep(3)

    return all_events


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        # Modo: python archive_events.py 20
        # Scrape N páginas
        num_pages = int(sys.argv[1])
        print(f"🎯 Modo: Scrapear {num_pages} páginas")
        events = scrape_multiple_pages(num_pages=num_pages)
    else:
        # Modo padrão: 10 páginas (500 eventos)
        print("🎯 Modo padrão: 10 páginas (500 eventos)")
        print("💡 Use: python archive_events.py <num_pages> para mais")
        events = scrape_multiple_pages(num_pages=10)

    print(f"\n{'='*60}")
    print(f"🎉 CONCLUÍDO!")
    print(f"📊 Total de eventos únicos: {len(events)}")
    print(f"{'='*60}")
