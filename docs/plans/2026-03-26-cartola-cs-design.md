# CartolaCS — Design Document

## Conceito

Fantasy game de CS2 inspirado no CartolaFC. Usuarios montam time de 5 jogadores, compram e vendem com base na performance real em partidas oficiais. Mercado continuo (sem rodadas), precos atualizam automaticamente pos-partida.

## Decisoes de Design

| Aspecto | Decisao |
|---|---|
| Multi-usuario | Sim, com auth |
| Interfaces | Web (React) + Discord bot |
| Auth | Email/senha + Discord OAuth2 |
| Mercado | Continuo, sem rodadas |
| Supply | Sem limite (todos podem ter o mesmo jogador) |
| Stack | FastAPI + SQLite, mesmo repo HLTV |
| Bot Discord | Mesmo processo FastAPI |
| Rankings | Patrimonio total + lucro + semanal |

---

## 1. Modelo de Dados

Novas tabelas no `hltv_data.db`:

```
users
  id (PK), username, email, password_hash, discord_id (nullable, unique),
  balance (default 100.0), created_at

player_roles
  id (PK), player_id (FK players), role (awp/rifler/igl/lurker/entry/support),
  is_primary (bool)
  unique(player_id, role)

player_market
  player_id (PK, FK players), current_price, previous_price,
  price_change_pct, last_updated

player_price_history
  id (PK), player_id (FK players), price, match_id (FK matches, nullable),
  timestamp

user_portfolio
  id (PK), user_id (FK users), player_id (FK players),
  buy_price, bought_at
  — cada linha = 1 jogador no time (max 5 por user)

transactions
  id (PK), user_id (FK users), player_id (FK players),
  type (buy/sell), price, timestamp
```

---

## 2. Motor de Precificacao

### Preco inicial

```
base_price = team_factor * player_factor

team_factor:
  top 5   → 5.0
  top 10  → 4.0
  top 20  → 3.0
  top 30  → 2.0
  top 50  → 1.5
  sem rank → 1.0

player_factor = rating_2_0 * 10
```

### Composicao do preco (3 janelas)

```
preco_novo = preco_atual * (1 + variacao_final)

variacao_final =
    0.40 * short_term    (ultima partida)
  + 0.40 * mid_term      (ultimas 10 partidas, media ponderada)
  + 0.20 * long_term     (desvio do fair price baseado em stats carreira)
```

### Short term (ultima partida)

```
short_term = base_perf * opponent_mult * event_weight * bo_weight + win_bonus

base_perf =
    0.40 * rating_diff          # (rating - 1.0) * 0.3
  + 0.25 * adr_diff             # (adr - 80) / 200
  + 0.15 * kast_diff            # (kast - 70) / 100
  + 0.10 * opening_diff         # (opening_kills - opening_deaths) * 0.03
  + 0.10 * clutch_bonus         # clutches_won * 0.02
```

**Multiplos mapas:** media ponderada por rounds jogados em cada mapa.

**Contexto:**

```
opponent_mult:
  adversario top 5   → 1.3x
  adversario top 10  → 1.2x
  adversario top 20  → 1.1x
  adversario top 30  → 1.0x
  adversario top 50  → 0.9x
  adversario sem rank → 0.8x

event_weight:
  Major          → 1.5
  Big event      → 1.2
  Resto          → 1.0

bo_weight:
  bo3/bo5        → 1.0
  bo1            → 0.7

win_bonus:
  vitoria        → +0.03
  derrota        → -0.03
```

### Mid term (ultimas 10 partidas)

Media ponderada dos short_term das ultimas 10 partidas:
```
pesos: [1.0, 0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2, 0.1]
```

### Long term (fair price)

```
fair_price = team_factor * rating_2_0 * 10
long_term = (fair_price - preco_atual) / preco_atual * 0.1
```

Fair price recalcula semanalmente (domingo, junto com sync de stats/rankings).

### Demanda

±3% max baseado em volume de compra/venda nas ultimas 24h. Pouco impacto inicial com poucos usuarios.

### Limites e regras especiais

| Regra | Valor |
|---|---|
| Variacao max por partida | ±15% |
| Variacao max por dia | ±20% |
| Preco minimo | 1 moeda |
| Preco maximo | 200 moedas |
| Decay inatividade | -1%/dia apos 14 dias sem jogar |
| Jogador sai do roster | Crash -30% imediato |
| Update de preco | Imediato pos-sync |
| Multiplas partidas/dia | Update por partida, respeitando cap diario |

### IA (fase 2)

Modelo treinado nos dados historicos pra prever fair price e ajustar pesos automaticamente. Nao faz parte do MVP.

---

## 3. API Endpoints

Prefixo `/api/cartola/`:

### Auth
- `POST /auth/register` — cadastro email/senha
- `POST /auth/login` — retorna JWT
- `GET /auth/discord` — OAuth2 redirect
- `GET /auth/discord/callback` — callback OAuth2

### Mercado
- `GET /market` — lista jogadores com precos, filtro por role, sort
- `GET /market/{player_id}` — detalhe com preco, historico, stats
- `GET /market/{player_id}/history` — historico de precos

### Portfolio
- `GET /portfolio` — meu time + saldo
- `POST /portfolio/buy/{player_id}` — compra (max 5)
- `POST /portfolio/sell/{player_id}` — vende

### Rankings
- `GET /ranking` — patrimonio total
- `GET /ranking/profit` — lucro
- `GET /ranking/weekly` — semanal

Auth via JWT, expira em 7 dias.

---

## 4. Frontend

Novas paginas em `/hltv/cartola/`:

### Publicas
- `/cartola/` — landing com ranking top 10, valorizacoes do dia
- `/cartola/market` — lista de jogadores com preco, variacao, sparkline 7d
- `/cartola/market/:id` — detalhe: grafico de preco, stats, partidas
- `/cartola/ranking` — ranking completo com tabs

### Autenticadas
- `/cartola/login` — email/senha + Discord
- `/cartola/register` — cadastro
- `/cartola/portfolio` — meu time (5 slots), saldo, lucro
- `/cartola/portfolio/history` — historico de transacoes

### Componentes
- `PlayerMarketCard` — card com preco, variacao, role badge, sparkline
- `PriceChart` — grafico historico (recharts)
- `PortfolioSlot` — slot do time
- `RankingTable` — tabela com tabs
- `AuthProvider` — context de auth com JWT

---

## 5. Discord Bot

Roda no mesmo processo via `discord.py`, slash commands:

### Publicos
- `/cartola market` — top 10 por preco
- `/cartola market <jogador>` — preco e stats
- `/cartola ranking` — top 10 patrimonio
- `/cartola ranking profit` — top 10 lucro
- `/cartola ranking weekly` — top 10 semanal

### Autenticados
- `/cartola link` — gera link pra vincular conta
- `/cartola portfolio` — meu time e saldo
- `/cartola buy <jogador>` — compra
- `/cartola sell <jogador>` — vende
- `/cartola history` — ultimas 10 transacoes

### Notificacoes (canal configuravel)
- Update de precos pos-partida
- Top 3 valorizacoes/desvalorizacoes diarias
- Alerta de jogador saindo do roster

### Vinculacao
`/cartola link` → bot gera link unico → usuario clica logado no site → discord_id vinculado

---

## 6. Estrutura de Arquivos

```
/root/hltv/
├── api/main.py                        # FastAPI existente + include_router(cartola)
├── cartola/
│   ├── __init__.py
│   ├── models.py                      # Users, PlayerMarket, Portfolio, Transactions
│   ├── auth.py                        # JWT, bcrypt, Discord OAuth2
│   ├── pricing.py                     # Motor de precificacao completo
│   ├── api.py                         # Endpoints /api/cartola/*
│   ├── bot.py                         # Discord bot
│   └── tasks.py                       # Update precos, decay, fair price semanal
├── frontend/src/
│   ├── pages/cartola/                 # Market, Portfolio, Ranking, Login, Register
│   └── components/cartola/            # PlayerMarketCard, PriceChart, PortfolioSlot
└── ...
```

### Dependencias novas
- `discord.py` — bot
- `PyJWT` — tokens
- `bcrypt` — senhas
- `recharts` (npm) — graficos

### Integracao
- `api/main.py` monta router do `cartola/api.py`
- `cartola/models.py` usa mesmo `Base` do SQLAlchemy
- Bot inicia no startup do FastAPI
- `sync_all.py` chama `cartola.tasks.update_prices()` ao finalizar matches
