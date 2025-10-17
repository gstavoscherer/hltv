# HLTV Data Scraper# HLTV Complete Data Scraper



Sistema completo de scraping e armazenamento de dados do HLTV (CS2).## 🎯 Sistema Completo de Coleta e Sincronização de Dados HLTV



## 📋 Estrutura do ProjetoSistema automatizado para coletar e manter atualizado um banco de dados completo de:

- ✅ Eventos (overview, matches, results, stats)

```- ✅ Times (detalhes, rosters, rankings)

hltv/- ✅ Jogadores (perfis, estatísticas, histórico)

├── database/           # SQLAlchemy models e configuração- ✅ Relacionamentos (times por evento, jogadores por time)

│   ├── __init__.py

│   ├── models.py      # Modelos: Event, Team, Player, EventStats, etc---

│   ├── importer.py    # Importador de dados JSON

│   └── queries.py     # Queries úteis## 🚀 Quick Start

├── archive_events.py       # Scraper de eventos do archive

├── events.py              # Scraper de eventos atuais### Setup Inicial

├── event_scraper.py       # Scraper completo de evento (overview, stats, etc)```bash

├── team_scraper.py        # Scraper de times e rosters# 1. Instalar dependências

├── player_scraper.py      # Scraper de perfil de playerspip install -r requirements.txt

├── player_stats_scraper.py # Scraper de stats individuais de playersplaywright install

├── import_events.py       # Importa eventos do archive para o banco

├── populate_full_flow.py  # SCRIPT PRINCIPAL - Fluxo completo# 2. Inicializar banco de dados

├── manage_db.py          # Gerenciador do banco de dadospython manage_db.py init

└── requirements.txt      # Dependências

```# 3. Migrar schema (adicionar campos de stats)

python migrate_player_stats.py

## 🚀 Setup

# 4. Processar primeiro evento completo

1. **Instalar dependências:**python process_event_full.py 8040

```bash```

python -m venv .venv

source .venv/bin/activate  # Linux/Mac### Comandos Principais

# ou .venv\Scripts\activate  # Windows

pip install -r requirements.txt#### Sincronização Automática (Recomendado)

``````bash

# Sync completo: eventos + times + players

2. **Instalar Playwright:**python sync_data.py --mode all \

```bash    --events-limit 10 \

playwright install chromium    --teams-limit 20 \

```    --players-limit 50

```

3. **Inicializar banco de dados:**

```bash#### Sync por Componente

python manage_db.py init```bash

```# Apenas eventos novos

python sync_data.py --mode events --events-limit 5

## 💾 Database Schema

# Apenas times sem roster

### Tabelas:python sync_data.py --mode teams --teams-limit 10

- **events**: Eventos (id, name, dates, location, prize_pool, type)

- **teams**: Times (id, name, country, world_rank)# Apenas players sem stats

- **players**: Players (id, nickname, country, stats completas)python sync_data.py --mode players --players-limit 30

- **event_stats**: Stats de players por evento (rating, maps)```

- **event_teams**: Relação Many-to-Many entre eventos e times

- **team_players**: Roster dos times (players por time)#### Ver Estatísticas do Banco

```bash

Schema limpo e minimalista - apenas dados essenciais.python manage_db.py stats

```

## 🔄 Fluxo Completo de População

---

```bash

# Importar eventos do archive## 📊 Dados Coletados

python import_events.py 8040 8393 8718

### Por Jogador:

# Rodar fluxo completo (recomendado)- ✅ Total Kills, Deaths, K/D Ratio

python populate_full_flow.py <num_events> <num_players_with_full_stats>- ✅ Headshot %, Maps played, Rounds played

- ✅ Rating 2.0, KPR, ADR, KAST, Impact (em desenvolvimento)

# Exemplo: 3 eventos, 5 players com stats completas por evento- ✅ Time atual e histórico de times

python populate_full_flow.py 3 5- ✅ Histórico de matches e eventos

```

### Por Time:

### O que o fluxo faz:- ✅ Nome, país, world ranking

- ✅ Logo, URL do perfil

1. **Busca eventos do banco** - Eventos previamente importados- ✅ Roster completo (5 jogadores + coach)

2. **Scrape event stats** - Top players do evento (Selenium/Cloudflare bypass)- ✅ Relacionamento com eventos

3. **Cria players e event_stats** - Players básicos + rating/maps por evento

4. **TODO: Team rosters** - Extrai times e rosters (em implementação)### Por Evento:

5. **Scrape player stats** - Stats individuais completas dos top N players- ✅ Nome, datas, localização, prize pool

- ✅ Times participantes

### Stats coletadas por player:- ✅ Matches e resultados

- Basic: nickname, country- ✅ Estatísticas dos jogadores

- Stats: rating_2_0, kpr, apr, kast, impact, adr

- Totals: total_kills, total_deaths, kd_ratio, headshot_percentage---

- Play: total_maps, total_rounds

## ⚙️ Automação (Cron)

## 🛠️ Comandos Úteis

### Configurar Sync Automático a Cada 2 Horas

```bash

# Ver estatísticas do banco```bash

python manage_db.py stats# 1. Tornar script executável

chmod +x schedule_sync.sh

# Resetar banco (cuidado!)

python manage_db.py drop# 2. Adicionar ao cron

python manage_db.py initcrontab -e



# Importar eventos específicos do archive# 3. Adicionar linha:

python import_events.py <event_id1> <event_id2> ...0 */2 * * * /Users/gustavoscherer/Workspace/hltv/schedule_sync.sh >> /Users/gustavoscherer/Workspace/hltv/sync.log 2>&1

```

# 4. Ver logs

## 🔍 Scrapers Individuaistail -f sync.log

```

### Archive Events

```bash---

python archive_events.py

```## 📚 Documentação Completa

Retorna lista de eventos históricos do HLTV archive.

- **[PROGRESS.md](PROGRESS.md)** - Histórico de desenvolvimento

### Event Scraper- **[PHASE2_TEAMS_PLAYERS.md](PHASE2_TEAMS_PLAYERS.md)** - Sistema de times e rosters

```python- **[PHASE3_ENHANCED_STATS.md](PHASE3_ENHANCED_STATS.md)** - Stats avançadas e sync

from event_scraper import scrape_stats_with_selenium- **[STATUS.md](STATUS.md)** - Status atual do projeto

stats = scrape_stats_with_selenium(8040, headless=True)

```---

Scrape stats de um evento (usa Selenium para bypass do Cloudflare).

## 🎯 Event Scraper (Legacy)

### Team Scraper

```pythonObjetivo

from team_scraper import scrape_team_details--------

team = scrape_team_details(5995, headless=True)  # LiquidScript `event_scraper.py` para coletar dados detalhados de um evento HLTV (overview, matches, results, stats).

```

Scrape detalhes do time + roster atual.Pré-requisitos

--------------

### Player Stats Scraper- Python 3.10+

```python- Playwright + browsers

from player_stats_scraper import scrape_player_full_stats  - Instalar dependências:

stats = scrape_player_full_stats(21167, headless=True)  # donk    ```

```    python -m pip install -r requirements.txt

Scrape stats completas de um player individual.    playwright install

    ```

## ⚙️ Tecnologias  - `requirements.txt` deve conter pelo menos:

    playwright

- **Python 3.13**    (ou instale via `pip install playwright`)

- **SQLAlchemy 2.0** - ORM

- **SQLite** - DatabaseComo rodar

- **Playwright** - Web scraping (páginas normais)---------

- **Selenium + undetected-chromedriver** - Bypass Cloudflare (stats)Exemplo:

- **BeautifulSoup4** - HTML parsingpython event_scraper.py 8067



## 📊 Status AtualPara abrir navegadores visíveis (útil para debug/evitar Cloudflare):

python event_scraper.py --visible 8067

✅ **Completo:**

- Database schema limpoO script cria `hltv_event_<ID>_full.json` com a estrutura:

- Scrapers funcionais- event_id, name, base_link

- Import de eventos- overview: location, prize_pool, teams, start/end, map_pool, formats, related_events, teams_attending, brackets (quando aplicável)

- Event stats + player basic info- matches: itens agendados (da aba /matches)

- Player stats individuais completas- results: resultados consolidados (da rota /results?event=)

- stats: top_players, top_teams (da rota /stats?event=)

⏳ **Em Progresso:**- status: heurística simples ("upcoming", "ongoing_or_some_results", "finished_or_stats_available")

- Extração automática de times do evento

- Team rosters completosComportamento e notas

---------------------

## 🤝 Contribuindo- O scraper abre um novo Chromium para cada aba (overview, matches, results, stats). Isso evita ser bloqueado por navegações internas (hl tv bloqueia navegações prolongadas).

- Existe um detector de Cloudflare refinado (`is_cloudflare_page`) que evita falsos positivos removendo gatilhos simples — somente considera realidade se 2+ sinais fortes aparecerem.

Projeto em desenvolvimento ativo. Sugestões e PRs são bem-vindos!- Se Cloudflare for detectado ao acessar `/stats`, o scraper tenta abrir novamente até `RETRY_ATTEMPTS` vezes com um pequeno backoff.

- Delays fixos entre carregamentos (`DELAY_BETWEEN_NAV`) ajudam o JS do site a rodar e reduzem a chance de bloqueio.

## 📝 Notas- Se quiser integrar isso em um pipeline:

  - Rode o `events.py` para coletar eventos (você já tem esse JSON).

- **Cloudflare**: Stats pages requerem Selenium (undetected-chromedriver)  - Use `event_scraper.build_event_payload(event_obj)` ou rode `event_scraper.py <id>` para enriquecer o evento.

- **Rate Limiting**: 3-5s entre requests para evitar ban  - Salve/normalize no banco.

- **Headless Mode**: Stats scraper pode precisar de headless=False em alguns casos

- **Database**: SQLite para desenvolvimento, pode migrar para PostgreSQL em produçãoProblemas conhecidos

-------------------

---- Cloudflare ainda pode bloquear em ambientes sem headful browsing. Para debug, use `--visible`.

- Seletores do HLTV mudam ocasionalmente; se algo parar de extrair, cheque os seletores (ex.: `.event-data`, `.top-x-box`, `.results-sublist`).

**Desenvolvido para coleta e análise de dados do CS2 competitivo** 🎯- Bracket JSON às vezes está HTML-escaped; o scraper tenta decodificar `&quot;` para `"`.


Se quiser, eu ajusto:
- output para SQLite direto,
- parallelização controlada (fila / workers),
- rotação de proxies / headers,
- ou transformações adicionais de players/teams/achievements.
