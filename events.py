from playwright.sync_api import sync_playwright
from datetime import datetime
import time
import json

URL = "https://www.hltv.org/events#tab-ALL"

def convert_unix(unix_str):
    """Converte timestamp UNIX em milissegundos → data legível (YYYY-MM-DD)."""
    if not unix_str:
        return None
    try:
        return datetime.fromtimestamp(int(unix_str) / 1000).strftime("%Y-%m-%d")
    except Exception:
        return None


def scrape_events(headless=True):
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
        print("➡️ Acessando HLTV Events...")
        page.goto(URL, timeout=60000)

        # Aceita cookies se aparecer
        try:
            page.locator("text=Accept All Cookies").click(timeout=4000)
            print("✅ Cookies aceitos")
        except Exception:
            pass

        # Garante que estamos na aba ALL
        try:
            page.click('text="All"', timeout=3000)
            print("📑 Aba 'All' ativada")
        except Exception:
            pass

        # Espera até que os eventos realmente estejam no DOM
        for i in range(60):
            cards = page.query_selector_all(".ongoing-events-holder a.ongoing-event")
            if len(cards) > 0:
                print(f"📦 Encontrados {len(cards)} eventos no DOM")
                break
            time.sleep(1)
        else:
            raise TimeoutError("⏰ Nenhum evento encontrado após 60 segundos")

        events = []
        print("🔍 Extraindo dados de eventos...")

        for card in cards:
            try:
                link = card.get_attribute("href")
                full_link = f"https://www.hltv.org{link}" if link else None

                img = card.query_selector("img.logo")
                img_src = img.get_attribute("src") if img else None
                title = img.get_attribute("alt") if img else None

                # nome e tipo (LAN / Online)
                name_div = card.query_selector(".event-name-small .text-ellipsis")
                name = name_div.inner_text().strip() if name_div else title or "Unknown"
                lan_marker = card.query_selector(".event-name-small .lan-marker")
                event_type = "LAN" if lan_marker else "Online"

                # datas
                date_cells = card.query_selector_all(".eventDetails td span[data-unix]")
                if len(date_cells) >= 2:
                    start_unix = date_cells[0].get_attribute("data-unix")
                    end_unix = date_cells[1].get_attribute("data-unix")
                else:
                    start_unix = end_unix = None

                start_date = convert_unix(start_unix)
                end_date = convert_unix(end_unix)

                events.append({
                    "name": name,
                    "type": event_type,
                    "link": full_link,
                    "image": img_src,
                    "start_unix": start_unix,
                    "end_unix": end_unix,
                    "start_date": start_date,
                    "end_date": end_date,
                })
            except Exception as e:
                print(f"⚠️ Erro ao processar evento: {e}")
                continue

        print(f"✅ Total coletado: {len(events)} eventos")
        browser.close()
        return events


if __name__ == "__main__":
    events = scrape_events(headless=False)

    print(json.dumps(events[:3], indent=2, ensure_ascii=False))

    with open("hltv_events.json", "w", encoding="utf-8") as f:
        json.dump(events, f, indent=2, ensure_ascii=False)

    print("💾 Salvo em hltv_events.json")
