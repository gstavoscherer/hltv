# Dados para Predicao de Mercado

## Ja temos

- Stats de carreira por jogador (rating, ADR, KAST, impact, KPR)
- Stats por mapa por jogador (kills, deaths, opening duels, clutches)
- Veto sequence (pick/ban revela preferencias)
- Scores por lado (CT/T) por mapa
- Rosters com datas de entrada/saida
- World rank atual (HLTV ranking, scraper dedicado)
- Matches com scores, best_of, datas
- **Z-score normalization** — stats individuais normalizadas por distribuicao real dos jogadores
- **Role-aware scoring** — pesos diferentes por role (AWP, entry, support, lurker, rifler)
- **IGL bonus** — bonus de 8-20% baseado em round win rate, match win rate, event placements
- **H2H aggregado** — `GET /api/cartola/h2h/{t1}/{t2}` (matches, maps, rounds)
- **Roster stability** — `GET /api/cartola/team/{id}/stability` (tenure, changes)
- **is_lan flag** — campo no Event model
- **Backtesting** — `python3 cartola/backtest.py` simula precos em matches historicos

## Falta implementar

### 1. Map pool stats por time (prioridade 1)
- Win rate por mapa, vezes jogado, CT/T side win rates
- Fonte: `/stats/teams/maps/{id}/{name}` no HLTV
- Impacto: altissimo — saber que time tem 80% win rate em Mirage muda predicao quando aparece no veto
- Esforco: medio (scraper novo)

### 2. Odds de apostas (prioridade 1)
- Odds das casas na pagina do match
- Fonte: pagina do match no HLTV ja mostra odds
- Impacto: altissimo — captura expectativa do mercado, permite identificar value bets
- Esforco: baixo (ta na mesma pagina que ja scrapamos)

### 3. Recent form / stats por janela temporal (prioridade 2)
- Stats dos ultimos 3 meses pesam mais que carreira inteira
- Fonte: `/stats/players/{id}?startDate=...&endDate=...`
- Impacto: alto — jogador em boa fase vs ma fase e crucial
- Esforco: medio (snapshots mensais ou por evento)

### 4. Historical rankings (prioridade 2)
- Evolucao semanal do ranking mostra tendencia (subindo vs caindo)
- Fonte: `/ranking/teams/{date}` no HLTV (ja temos scraper)
- Impacto: alto — tendencia importa mais que rank absoluto
- Esforco: baixo (salvar historico no sync semanal, tabela nova team_ranking_history)

### 5. Pistol round win rate (prioridade 3)
- Ganha pistol round, ganha o half na maioria dos casos
- Fonte: pagina de stats do time no HLTV
- Impacto: medio
- Esforco: medio (scraper novo)

### 6. Scraper automatico de roles (prioridade 2)
- Player roles (IGL, AWP, entry, etc) populados automaticamente
- Fonte: pagina do jogador no HLTV ou roster page do time
- Impacto: alto — sem roles, z-score e IGL bonus dependem de dados manuais
- Esforco: medio (adicionar no scraper existente de players)

## Resumo de esforco

| Dado | Status | Scraping novo? | Tabela nova? |
|---|---|---|---|
| Z-score normalization | **FEITO** | Nao | Nao |
| Role-aware scoring | **FEITO** | Nao | Nao (usa player_roles) |
| IGL bonus | **FEITO** | Nao | Nao (usa player_roles) |
| H2H aggregado | **FEITO** | Nao | Nao (query + API) |
| Roster stability | **FEITO** | Nao | Nao (query + API) |
| LAN vs Online | **FEITO** | Nao | Nao (campo is_lan) |
| Backtesting | **FEITO** | Nao | Nao (simulacao in-memory) |
| Map pool stats | Pendente | Sim | Sim (team_map_stats) |
| Odds | Pendente | Sim (pagina do match) | Sim (match_odds) |
| Recent form | Pendente | Sim (stats filtrado) | Sim (player_form_snapshots) |
| Historical rankings | Pendente | Sim (ranking page) | Sim (team_ranking_history) |
| Pistol rounds | Pendente | Sim | Sim |
| Role scraper | Pendente | Sim (pagina do player) | Nao (popula player_roles) |
