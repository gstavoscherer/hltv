from playwright.sync_api import sync_playwright
from datetime import datetime
import json
import re

BASE_URL = "https://www.hltv.org"


def convert_unix(unix_str):
    if not unix_str:
        return None
    try:
        return datetime.fromtimestamp(int(unix_str) / 1000).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return None


def scrape_match(match_url: str, headless=True):
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
        print(f"➡️ Acessando partida: {match_url}")
        page.goto(match_url, timeout=60000)

        # Aceita cookies
        try:
            page.locator("text=Accept All Cookies").click(timeout=4000)
        except Exception:
            pass

        page.wait_for_selector(".teamsBox", timeout=20000)

        # Times — usa .first para evitar strict mode
        team1 = page.locator(".team1 .teamName").first.inner_text().strip()
        team2 = page.locator(".team2 .teamName").first.inner_text().strip()

        team1_logo = page.locator(".team1 img").first.get_attribute("src")
        team2_logo = page.locator(".team2 img").first.get_attribute("src")

        score1 = (
            page.locator(".team1 .team1-score").first.inner_text().strip()
            if page.locator(".team1 .team1-score").count() > 0
            else None
        )
        score2 = (
            page.locator(".team2 .team2-score").first.inner_text().strip()
            if page.locator(".team2 .team2-score").count() > 0
            else None
        )

        # Mapa a mapa
        maps = []
        for m in page.query_selector_all(".mapholder"):
            try:
                map_name = m.query_selector(".mapname").inner_text().strip()
                result = m.query_selector(".results").inner_text().strip()
                maps.append({"map_name": map_name, "result": result})
            except:
                continue

        # Estatísticas gerais
        print("📊 Coletando estatísticas gerais...")
        stats_url = match_url + "#tab-statistics"
        page.goto(stats_url, timeout=60000)
        page.wait_for_selector(".stats-content", timeout=20000)

        # Pega apenas as tabelas visíveis (sem 'hidden')
        tables = [
            t for t in page.query_selector_all(".stats-content table.totalstats")
            if "hidden" not in (t.get_attribute("class") or "")
        ][:2]

        players_data = []
        for t in tables:
            try:
                team_header_el = t.query_selector(".teamName")
                team_header = team_header_el.inner_text().strip() if team_header_el else "Unknown Team"

                rows = t.query_selector_all("tr")[1:]
                for row in rows:
                    cols = row.query_selector_all("td")
                    if len(cols) < 6:
                        continue

                    player_el = cols[0].query_selector("a")
                    player_link = BASE_URL + player_el.get_attribute("href") if player_el else None
                    player_flag = cols[0].query_selector("img.flag")
                    country = player_flag.get_attribute("title") if player_flag else None
                    nickname_el = cols[0].query_selector(".player-nick")
                    player_nick = nickname_el.inner_text().strip() if nickname_el else cols[0].inner_text().strip()

                    kd = cols[1].inner_text().strip()
                    plus_minus = cols[2].inner_text().strip()
                    adr = cols[3].inner_text().strip()
                    swing = cols[4].inner_text().strip()
                    rating = cols[5].inner_text().strip()

                    players_data.append({
                        "team": team_header,
                        "player": player_nick,
                        "country": country,
                        "link": player_link,
                        "kd": kd,
                        "+/-": plus_minus,
                        "adr": adr,
                        "swing": swing,
                        "rating": rating
                    })
            except Exception as e:
                print(f"⚠️ Erro ao processar tabela: {e}")
                continue

        match_data = {
            "match_url": match_url,
            "team1": {"name": team1, "logo": team1_logo, "score": score1},
            "team2": {"name": team2, "logo": team2_logo, "score": score2},
            "maps": maps,
            "players": players_data
        }

        print(f"✅ Coletado {len(players_data)} jogadores (somente totalstats)")
        browser.close()
        return match_data


if __name__ == "__main__":
    MATCH_URL = "https://www.hltv.org/matches/2386801/og-vs-9z-thunderpick-world-championship-2025"
    data = scrape_match(MATCH_URL, headless=False)

    print(json.dumps(data, indent=2, ensure_ascii=False))
    match_id = re.search(r"/matches/(\d+)/", MATCH_URL).group(1)
    with open(f"hltv_match_{match_id}.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"💾 Salvo em hltv_match_{match_id}.json")
