# Event Scraper — README

Objetivo
--------
Script `event_scraper.py` para coletar dados detalhados de um evento HLTV (overview, matches, results, stats).

Pré-requisitos
--------------
- Python 3.10+
- Playwright + browsers
  - Instalar dependências:
    ```
    python -m pip install -r requirements.txt
    playwright install
    ```
  - `requirements.txt` deve conter pelo menos:
    playwright
    (ou instale via `pip install playwright`)

Como rodar
---------
Exemplo:
python event_scraper.py 8067

Para abrir navegadores visíveis (útil para debug/evitar Cloudflare):
python event_scraper.py --visible 8067

O script cria `hltv_event_<ID>_full.json` com a estrutura:
- event_id, name, base_link
- overview: location, prize_pool, teams, start/end, map_pool, formats, related_events, teams_attending, brackets (quando aplicável)
- matches: itens agendados (da aba /matches)
- results: resultados consolidados (da rota /results?event=)
- stats: top_players, top_teams (da rota /stats?event=)
- status: heurística simples ("upcoming", "ongoing_or_some_results", "finished_or_stats_available")

Comportamento e notas
---------------------
- O scraper abre um novo Chromium para cada aba (overview, matches, results, stats). Isso evita ser bloqueado por navegações internas (hl tv bloqueia navegações prolongadas).
- Existe um detector de Cloudflare refinado (`is_cloudflare_page`) que evita falsos positivos removendo gatilhos simples — somente considera realidade se 2+ sinais fortes aparecerem.
- Se Cloudflare for detectado ao acessar `/stats`, o scraper tenta abrir novamente até `RETRY_ATTEMPTS` vezes com um pequeno backoff.
- Delays fixos entre carregamentos (`DELAY_BETWEEN_NAV`) ajudam o JS do site a rodar e reduzem a chance de bloqueio.
- Se quiser integrar isso em um pipeline:
  - Rode o `events.py` para coletar eventos (você já tem esse JSON).
  - Use `event_scraper.build_event_payload(event_obj)` ou rode `event_scraper.py <id>` para enriquecer o evento.
  - Salve/normalize no banco.

Problemas conhecidos
-------------------
- Cloudflare ainda pode bloquear em ambientes sem headful browsing. Para debug, use `--visible`.
- Seletores do HLTV mudam ocasionalmente; se algo parar de extrair, cheque os seletores (ex.: `.event-data`, `.top-x-box`, `.results-sublist`).
- Bracket JSON às vezes está HTML-escaped; o scraper tenta decodificar `&quot;` para `"`.

Se quiser, eu ajusto:
- output para SQLite direto,
- parallelização controlada (fila / workers),
- rotação de proxies / headers,
- ou transformações adicionais de players/teams/achievements.

