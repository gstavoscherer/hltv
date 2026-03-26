# CartolaCS — Fantasy CS2

## Conceito

Fantasy game inspirado no CartolaFC. Usuario monta time de 5 jogadores de CS2 e lucra/perde moedas com base na performance real dos jogadores em partidas oficiais.

## Mecanica Principal

### Saldo e Compra
- Usuario comeca com **100 moedas**
- Compra ate **5 jogadores** pra montar o time
- Cada jogador tem um preco de mercado (definido por algoritmo + IA)
- Compra e venda livre — lucro vem de comprar barato e vender caro

### Posicoes
- **AWPer** — sniper principal
- **Rifler** — jogador de rifle (pode ter mais de 1 no time)
- **IGL** — in-game leader (chamadas e estrategia)
- **Lurker** — joga separado, flancos
- **Entry Fragger** — primeiro a entrar no bomb site
- **Support** — utility, flashes, smokes

Um jogador pode ter mais de 1 posicao (ex: AWP/IGL como FalleN). O time precisa ter 5 jogadores mas nao precisa cobrir todas as posicoes.

### Valorizacao / Desvalorizacao
- Depois de cada partida oficial, o preco do jogador atualiza
- **Jogou bem** (rating alto, clutches, MVPs) → preco sobe
- **Jogou mal** (rating baixo, muitas mortes, poucos kills) → preco cai
- Preco definido por **algoritmo + IA** considerando:
  - Rating do jogador na partida
  - ADR, KAST, opening duels
  - Importancia da partida (Major pesa mais que qualificatoria)
  - Tendencia recente (forma dos ultimos jogos)
  - Oferta/demanda (quantos usuarios tem o jogador)

### Como o usuario ganha moedas
- **Valorizacao**: compra jogador a 10, ele joga bem, vende a 14 → lucro de 4
- **Pontuacao por rodada**: em cada rodada de evento, o time do usuario pontua baseado na performance dos 5 jogadores. Top N do ranking ganham bonus em moedas
- **Dividendos**: manter jogadores que performam consistentemente gera moedas passivas (opcional)

## Dados necessarios (do HLTV)

### Ja temos
- [x] Stats por mapa por jogador (rating, kills, deaths, ADR, KAST, clutches)
- [x] Matches com datas e eventos
- [x] Rosters atuais dos times

### Falta (ver features.md)
- [ ] Posicao/role do jogador (AWP, IGL, etc) — HLTV mostra em alguns perfis
- [ ] Recent form (stats ultimos 3 meses) — pra calcular tendencia
- [ ] Odds de apostas — referencia pra calibrar precos

### Novo pro CartolaCS
- [ ] Tabela de precos historicos por jogador (price_history)
- [ ] Tabela de portfolios dos usuarios (user_portfolio)
- [ ] Tabela de transacoes (transactions)
- [ ] Motor de precificacao (algoritmo + IA)
- [ ] Sistema de rodadas atrelado a eventos reais

## Modelo de Dados (rascunho)

```
users
  id, username, balance (comeca 100)

user_portfolio
  user_id, player_id, bought_at, buy_price, quantity

transactions
  user_id, player_id, type (buy/sell), price, quantity, timestamp

player_market
  player_id, current_price, previous_price, price_change_pct, last_updated

player_price_history
  player_id, price, timestamp, match_id (evento que causou a mudanca)

player_roles
  player_id, role (awp/rifler/igl/lurker/entry/support), is_primary
```

## Motor de Precificacao (ideias)

### Formula base
```
novo_preco = preco_atual * (1 + variacao)

variacao = w1 * rating_norm + w2 * impact_norm + w3 * clutch_bonus + w4 * demand_factor

onde:
  rating_norm = (rating_partida - 1.0) * fator  # 1.0 e a media
  impact_norm = impacto normalizado
  clutch_bonus = bonus por clutches ganhas
  demand_factor = ajuste por quantos usuarios tem o jogador
```

### Limites
- Variacao maxima por partida: +/- 15%
- Preco minimo: 1 moeda (jogador nunca vale zero)
- Jogador sem jogar por 30 dias: preco decai lentamente

### IA
- Modelo treinado nos dados historicos pra prever "fair price"
- Compara com preco atual pra ajustar gradualmente
- Considera contexto: adversario, mapa, importancia do torneio
