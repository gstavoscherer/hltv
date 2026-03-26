# Estrategia de Syncs

## Frequencias por tipo de dado

| Dado | Frequencia | Motivo |
|---|---|---|
| Matches de eventos ativos | 2x/dia (12h, 00h) | Eventos tem partidas diarias |
| Novos eventos (archive 30 dias) | Diario (3h) | HLTV publica eventos com antecedencia |
| Player stats de carreira | Semanal (domingo 4h) | Rating, ADR, KAST mudam gradualmente |
| Rosters de times | Semanal (domingo 4h) | Transferencias sao esporadicas |
| Rankings de times | Semanal (segunda 6h) | HLTV atualiza ranking toda segunda |

## Scripts necessarios

### sync_active_events.py (2x/dia)
- Detecta eventos "em andamento" (start_date <= hoje <= end_date)
- Synca apenas matches, maps, player_stats e vetos desses eventos
- Rapido — nao refaz times/players/rosters

### sync_new_events.py (diario)
- Busca archive dos ultimos 30 dias (MAJOR + INTLLAN)
- Cria eventos novos que nao existem no banco
- Sync completo (times, players, matches) dos novos

### sync_weekly.py (semanal)
- Atualiza stats de carreira de todos os jogadores no banco
- Atualiza rosters de todos os times
- Atualiza world_rank dos times

## Crons planejados

```cron
# Matches de eventos ativos (2x/dia)
0 0,12 * * * cd /root/hltv && ./run_vps.sh sync_active_events.py >> logs/sync_active.log 2>&1

# Novos eventos (diario 3h)
0 3 * * * cd /root/hltv && ./run_vps.sh sync_new_events.py >> logs/sync_new.log 2>&1

# Stats, rosters, rankings (domingo 4h)
0 4 * * 0 cd /root/hltv && ./run_vps.sh sync_weekly.py >> logs/sync_weekly.log 2>&1
```

## Status

- [ ] sync_active_events.py — nao criado
- [ ] sync_new_events.py — nao criado
- [ ] sync_weekly.py — nao criado
- [ ] crons configurados
- [x] sync_events_archive.py — sync inicial bulk (rodando agora, 48 eventos)
