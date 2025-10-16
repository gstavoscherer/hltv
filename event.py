from playwright.sync_api import sync_playwright
from datetime import datetime
import json
import time

BASE_URL = "https://www.hltv.org"
RESULTS_URL = "https://www.hltv.org/results?event={event_id}"

def convert_unix(unix_str):
    """Converte timestamp UNIX ms → datetime legível (YYYY-MM-DD HH:MM)."""
    if not unix_str:
        return None
    try:
        return datetime.fromtimestamp(int(unix_str) / 1000).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return None


def scrape_event_results(event_id: int, headless=True):
    url = RESULTS_URL.format(event_id=event_id)

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

        print(f"➡️ Acessando resultados do evento {event_id}...")
        page.goto(url, timeout=60000)

        # Aceita cookies se aparecer
        try:
            page.locator("text=Accept All Cookies").click(timeout=4000)
            print("✅ Cookies aceitos")
        except Exception:
            pass

        # Espera a tabela principal aparecer
        for i in range(60):
            cards = page.query_selector_all(".result-con")
            if len(cards) > 0:
                print(f"📦 Encontradas {len(cards)} partidas no DOM")
                break
            time.sleep(1)
        else:
            raise TimeoutError("⏰ Nenhuma partida encontrada após 60s")

        matches = []
        print("🔍 Extraindo partidas...")

        # Para separar blocos por data
        date_blocks = page.query_selector_all(".results-sublist")

        for block in date_blocks:
            date_label_el = block.query_selector(".standard-headline")
            date_label = date_label_el.inner_text().strip() if date_label_el else None

            for card in block.query_selector_all(".result-con"):
                try:
                    link_el = card.query_selector("a.a-reset")
                    href = link_el.get_attribute("href") if link_el else None
                    match_link = f"{BASE_URL}{href}" if href else None

                    unix_attr = card.get_attribute("data-zonedgrouping-entry-unix")
                    match_datetime = convert_unix(unix_attr)

                    team1_name = card.query_selector(".team1 .team").inner_text().strip()
                    team2_name = card.query_selector(".team2 .team").inner_text().strip()

                    team1_logo = card.query_selector(".team1 img")
                    team2_logo = card.query_selector(".team2 img")

                    team1_logo = team1_logo.get_attribute("src") if team1_logo else None
                    team2_logo = team2_logo.get_attribute("src") if team2_logo else None

                    # score
                    score_el = card.query_selector(".result-score")
                    score_text = score_el.inner_text().strip() if score_el else "N/A"

                    # vencedor (team-won)
                    winner = None
                    if "team-won" in card.query_selector(".team1 .team").get_attribute("class"):
                        winner = team1_name
                    elif "team-won" in card.query_selector(".team2 .team").get_attribute("class"):
                        winner = team2_name

                    # formato (bo3, bo5, etc.)
                    map_text_el = card.query_selector(".map-text")
                    format_text = map_text_el.inner_text().strip() if map_text_el else None

                    matches.append({
                        "date_label": date_label,
                        "match_datetime": match_datetime,
                        "match_link": match_link,
                        "team1": {
                            "name": team1_name,
                            "logo": team1_logo
                        },
                        "team2": {
                            "name": team2_name,
                            "logo": team2_logo
                        },
                        "score": score_text,
                        "format": format_text,
                        "winner": winner
                    })
                except Exception as e:
                    print(f"⚠️ Erro ao processar partida: {e}")
                    continue

        browser.close()
        print(f"✅ Total de partidas coletadas: {len(matches)}")
        return matches


if __name__ == "__main__":
    EVENT_ID = 8067  # Thunderpick World Championship 2025
    data = scrape_event_results(EVENT_ID, headless=False)

    print(json.dumps(data[:3], indent=2, ensure_ascii=False))

    with open(f"hltv_event_{EVENT_ID}_matches.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"💾 Resultados salvos em hltv_event_{EVENT_ID}_matches.json")
