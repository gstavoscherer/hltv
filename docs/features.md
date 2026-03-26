# Dados para Predicao de Mercado

## Ja temos

- Stats de carreira por jogador (rating, ADR, KAST, impact, KPR)
- Stats por mapa por jogador (kills, deaths, opening duels, clutches)
- Veto sequence (pick/ban revela preferencias)
- Scores por lado (CT/T) por mapa
- Rosters com datas de entrada/saida
- World rank atual
- Matches com scores, best_of, datas

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
- Fonte: `/ranking/teams/{date}` no HLTV
- Impacto: alto — tendencia importa mais que rank absoluto
- Esforco: baixo (1 pagina por semana)

### 5. LAN vs Online flag (prioridade 3)
- Times performam diferente em LAN vs online
- Fonte: campo `is_lan` no event (HLTV mostra tipo do evento)
- Impacto: medio
- Esforco: baixo (campo simples no model)

### 6. Pistol round win rate (prioridade 3)
- Ganha pistol round, ganha o half na maioria dos casos
- Fonte: pagina de stats do time no HLTV
- Impacto: medio
- Esforco: medio (scraper novo)

### 7. H2H aggregado (prioridade 3)
- Win rate time A vs time B, maps jogados entre eles
- Fonte: query nos dados existentes (matches + match_maps)
- Impacto: medio
- Esforco: zero (so SQL/API endpoint)

### 8. Roster stability (prioridade 3)
- Tempo junto como squad — time estavel vs recem-formado
- Fonte: query nos dados existentes (team_players.joined_date)
- Impacto: medio
- Esforco: zero (so SQL/API endpoint)

## Resumo de esforco

| Dado | Scraping novo? | Tabela nova? |
|---|---|---|
| Map pool stats | Sim | Sim (team_map_stats) |
| Odds | Sim (pagina do match) | Sim (match_odds) |
| Recent form | Sim (stats filtrado) | Sim (player_form_snapshots) |
| Historical rankings | Sim (ranking page) | Sim (team_ranking_history) |
| LAN vs Online | Nao (ja tem event_type) | Nao (campo no event) |
| Pistol rounds | Sim | Sim (team_stats ou campo extra) |
| H2H aggregado | Nao | Nao (query) |
| Roster stability | Nao | Nao (query) |
