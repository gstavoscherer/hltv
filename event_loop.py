import json
from pathlib import Path
from event_scraper import scrape_event_details

def main():
    with open("hltv_events.json", "r", encoding="utf-8") as f:
        events = json.load(f)

    out_dir = Path("data/events")
    out_dir.mkdir(parents=True, exist_ok=True)

    for ev in events:
        try:
            result = scrape_event_details(ev, headless=False)
            event_id = result["event_id"]
            out_file = out_dir / f"{event_id}.json"
            with open(out_file, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"❌ Falha no evento {ev['name']}: {e}")

if __name__ == "__main__":
    main()
