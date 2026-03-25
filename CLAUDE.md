# HLTV Scraper - Contexto do Projeto

## O que e

Scraper completo de dados competitivos de CS2 do HLTV.org. Coleta eventos, times, jogadores, stats de carreira, placements e premiacoes. Armazena tudo num SQLite local.

## Stack

- Python 3.10, Selenium, `undetected-chromedriver` (bypass Cloudflare)
- SQLAlchemy ORM + SQLite (`hltv_data.db`)
- xvfb pra rodar Chrome "nao-headless" em VPS sem tela (melhor bypass de Cloudflare)
- Testes com pytest + mocks

## Arquitetura

```
HLTV.org
  |
  v
Selenium (undetected-chromedriver + xvfb)
  |
  v
Scrapers (src/scrapers/)
  ├── events.py     -> lista eventos, teams por evento, placements, detalhes
  ├── teams.py      -> perfil do time + roster
  ├── players.py    -> stats de carreira do jogador
  └── selenium_helpers.py -> DriverPool, create_driver, Cloudflare bypass
  |
  v
SQLAlchemy ORM (src/database/)
  ├── __init__.py   -> init_db, session_scope, get_session
  └── models.py     -> Event, Team, Player, EventTeam, TeamPlayer, EventStats
  |
  v
SQLite (hltv_data.db)
```

## Banco de Dados (6 tabelas)

| Tabela | Campos principais | Descricao |
|---|---|---|
| events | id, name, location, prize_pool, event_type, start/end_date | Torneios |
| teams | id, name, country, world_rank | Times |
| players | id, nickname, real_name, country, age, rating_2_0, kast, kpr, adr, impact, kd_ratio, total_kills/deaths/maps/rounds, headshot_percentage | Jogadores + stats carreira |
| event_teams | event_id, team_id, placement, prize | Participacao + colocacao |
| team_players | team_id, player_id, role, is_current, joined/left_date | Roster atual/historico |
| event_stats | event_id, player_id, rating, maps_played, kd_ratio | Stats por evento (nao populado ainda) |

## Scripts principais

### sync_all.py (ponto de entrada principal)
Sync completo de um ou mais eventos. Fluxo por evento:
1. `get_event_details()` -> location, prize_pool
2. `get_event_teams()` -> lista de team_ids
3. `get_event_results()` -> placements e prizes
4. `scrape_team()` por time -> roster + info (via DriverPool)
5. `scrape_player()` por jogador -> stats carreira (via DriverPool)

```bash
# Sync um evento
./run_vps.sh --event 8504

# Sync todos os eventos
./run_vps.sh

# Com flags
./run_vps.sh --event 8504 --workers 1 --show
```

### cli.py
CLI alternativa com subcomandos individuais:
- `python3 cli.py init` - cria banco
- `python3 cli.py events` - sync eventos
- `python3 cli.py teams <event_id>` - sync times de um evento
- `python3 cli.py players --event <id>` - sync jogadores
- `python3 cli.py status` - mostra contagens do banco

### scrape_players_batch.py
Script batch pra scraping de jogadores do evento 8504. Usa DriverPool, retry automatico dos que falharem. Checa `rating_2_0 IS NULL` pra saber quem falta.

### run_vps.sh
Wrapper pra rodar com xvfb (virtual display):
```bash
xvfb-run --auto-servernum --server-args="-screen 0 1920x1080x24" python3 sync_all.py --show "$@"
```

## DriverPool (feature principal recente)

Pool de Chrome drivers reutilizaveis. Criado pra resolver:
- Cloudflare bloqueando requests repetidos (novo driver = novo challenge)
- Lentidao de criar/destruir Chrome por request (~3s cada)

### Como funciona
1. `DriverPool(size=N)` cria N drivers upfront
2. Cada driver faz warmup visitando HLTV pra resolver Cloudflare 1x
3. Workers fazem `checkout()` / `checkin()` pra reusar drivers
4. Se driver morrer, `mark_bad()` marca pra substituicao no proximo checkout
5. `_ensure_chromedriver()` patcha o chromedriver 1x pra evitar conflito de versao

### Limitacoes conhecidas
- **Multiplos drivers simultaneos falham neste VPS** — o Chromium snap + undetected-chromedriver nao lida bem com multiplas instancias. O primeiro request de cada driver novo morre com `RemoteDisconnected`. Default e 1 worker.
- O `undetected-chromedriver` faz patch de um binario compartilhado. Sem o `_DRIVER_LOCK`, instancias concorrentes causam conflito de versao (ex: Chrome 146 vs ChromeDriver 147).

## Problemas conhecidos

### Cloudflare
- HLTV usa Cloudflare agressivo. `undetected-chromedriver` com xvfb (nao-headless) e a melhor abordagem
- Com DriverPool e reuso de cookie, a taxa de erro caiu de ~13% pra 0%
- Timeout progressivo: 20s -> 30s -> 45s em retries

### ChromeDriver version mismatch
- O `undetected-chromedriver` as vezes baixa versao errada (147 quando Chrome e 146)
- Fix: `_ensure_chromedriver()` pre-patcha com `uc.Patcher(version_main=N)` antes de criar qualquer driver
- Se persistir: `rm -f ~/.local/share/undetected_chromedriver/undetected_chromedriver`

### event_stats vazio
- A tabela `event_stats` existe mas `scrape_event_stats()` nao e chamada no fluxo principal do sync_all
- Funcionalidade pronta em `players.py`, so precisa integrar

## Estado atual do banco

- 1 evento: **8504** (Budapest, Hungary, $250,000)
- 16 times com placement e prize
- 79 jogadores com stats completos (rating, kast, kpr, adr, impact)
- 0 event_stats

## Performance

| Metrica | Antes (sem pool) | Depois (com pool) |
|---|---|---|
| Tempo total (79 players) | ~40min | ~11min |
| Taxa de erro | ~13% (10/79) | 0% |
| Cloudflare challenges | ~20 por run | 0 (cookie reusado) |
| Chrome criados | 79+ (1 por player) | 1 (reusado) |

## Como rodar testes

```bash
cd /root/hltv
python3 -m pytest tests/ -v
```

54 testes cobrindo models, database, scrapers (com mocks).

## Ambiente

- VPS: Ubuntu, Chromium 146 snap, Python 3.10
- Deps: `pip install -r requirements.txt` + `apt install xvfb`
- Rodar sempre com `PYTHONUNBUFFERED=1` pra ver output em tempo real:
  ```bash
  PYTHONUNBUFFERED=1 ./run_vps.sh --event 8504
  ```

## Convencoes

- Prints do scraper: `Jogador: {nick} | Rating: {rating}` / `Time: {name} | Roster: {N} jogadores`
- Logs via `logging` (INFO/WARNING/ERROR) vao pra stderr
- Banco usa upsert pattern (checa se existe, atualiza ou cria)
- Session scope com context manager pra thread safety
- Codigo e comentarios misturados pt-br/en
