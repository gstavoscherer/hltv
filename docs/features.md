# Dados para Predicao de Mercado

## Ja temos

- Stats de carreira por jogador (rating, ADR, KAST, impact, KPR)
- Stats por mapa por jogador (kills, deaths, opening duels, clutches)
- Veto sequence (pick/ban revela preferencias)
- Scores por lado (CT/T) por mapa
- Rosters com datas de entrada/saida
- World rank atual (HLTV ranking, scraper dedicado)
- Matches com scores, best_of, datas

### Features implementadas

| Feature | Descricao | Arquivos | Status |
|---|---|---|---|
| Z-score normalization | Stats normalizadas por distribuicao real | `cartola/pricing.py` | **FEITO** |
| Role-aware scoring | Pesos por role (AWP, entry, etc) | `cartola/pricing.py` | **FEITO** |
| IGL bonus | +8-20% baseado em WR, placements | `cartola/pricing.py` | **FEITO** |
| H2H aggregado | Win rate time A vs B | `cartola/analytics.py`, API `/h2h/{t1}/{t2}` | **FEITO** |
| Roster stability | Tenure, mudancas recentes | `cartola/analytics.py`, API `/team/{id}/stability` | **FEITO** |
| is_lan flag | Campo no Event model | `src/database/models.py` | **FEITO** |
| Backtesting | Simula precos em matches historicos | `cartola/backtest.py` | **FEITO** |
| Map pool stats | Win rate por mapa por time | `src/scrapers/team_maps.py`, `TeamMapStats` | **FEITO** (308 registros) |
| Odds de apostas | Odds das casas na pagina do match | `src/scrapers/matches.py`, `MatchOdds` | **FEITO** (scraper pronto, popula nos proximos syncs) |
| Recent form | Stats ultimos 3 meses | `src/scrapers/player_form.py`, `PlayerFormSnapshot` | **FEITO** (272 snapshots) |
| Historical rankings | Evolucao semanal do ranking | `sync_rankings.py`, `TeamRankingHistory`, API `/team/{id}/ranking-history` | **FEITO** (popula no proximo sync semanal) |
| Role scraper | Detecta role na pagina do jogador | `src/scrapers/players.py` | **FEITO** (detecta no proximo sync de players) |
| Pistol round win rate | Win rate de pistol rounds por time | `src/scrapers/pistol_stats.py`, `matches.py`, API `/team/{id}/pistol-stats` | **FEITO** (popula nos proximos syncs) |

## Como rodar

```bash
# Map pool stats (calcula dos matches existentes)
PYTHONPATH=/root/hltv python3 src/scrapers/team_maps.py

# Player form (ultimos 3 meses)
PYTHONPATH=/root/hltv python3 src/scrapers/player_form.py

# Backtest
python3 cartola/backtest.py

# Rankings (scrapa HLTV + salva historico)
python3 sync_rankings.py
```

## Integracao nos syncs

- **sync_daily.py**: novos eventos + decay + market init
- **sync_weekly.py**: rankings HLTV + rosters + player stats (detecta roles) + map stats + form snapshots + precos
- **sync_active_matches.py**: matches ativos + odds (automatico)

## Pistol round win rate

**FEITO** — Implementado via campos `team1_pistol_wins` / `team2_pistol_wins` no `MatchMap`. O scraper de match detail (`src/scrapers/matches.py`) extrai pistol round wins da pagina do match. Stats agregadas por time disponivel em `src/scrapers/pistol_stats.py` e via API `GET /api/cartola/team/{id}/pistol-stats`.

Dados populam automaticamente nos proximos syncs de matches. Para ver stats atuais:
```bash
PYTHONPATH=/root/hltv python3 src/scrapers/pistol_stats.py
```
