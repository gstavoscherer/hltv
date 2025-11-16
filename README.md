# HLTV Data Scraper

Sistema completo e otimizado para VPS para coletar TODOS os dados do HLTV (CS2 competitivo).

## 🎯 O que coleta

### ✅ Dados Completos

- **Eventos** - Torneios (nome, datas, localização, prize pool, tipo)
- **Times** - Times participantes (nome, país, world rank)
- **Placements** - Colocação de cada time no evento (1º, 2º, 3º, 4º)
- **Prizes** - Premiação de cada time
- **Jogadores** - Perfil completo (nickname, nome real, país, idade, time atual)
- **Player Stats** - Estatísticas completas:
  - Rating 2.0, KAST, K/D Ratio, ADR
  - Total kills, deaths, headshots, maps played
  - KPR, Impact, Total rounds
- **Histórico** - Histórico de desempenho dos jogadores por evento

## 🚀 Quick Start

### 1. Instalação (VPS/Linux)

```bash
# Instalar Chromium (necessário para scraping)
sudo pacman -S chromium  # Arch Linux
# ou
sudo apt install chromium-browser  # Ubuntu/Debian

# Instalar dependências Python
pip install -r requirements.txt

# Inicializar banco de dados
python cli.py init
```

### 2. Uso Rápido

#### Opção A: Sincronização Completa Automática (RECOMENDADO) ⚡

```bash
# Sincroniza TUDO de UMA VEZ: eventos, times, placements, players, stats
python sync_all.py --limit 3

# Sincronizar apenas um evento específico completo
python sync_all.py --event 8041

# Com browser visível (debug)
python sync_all.py --limit 1 --show
```

#### Opção B: Sincronização Manual (passo a passo)

```bash
# 1. Sincronizar eventos
python cli.py events --limit 5

# 2. Sincronizar times de um evento
python cli.py teams 8041

# 3. Sincronizar jogadores e stats
python cli.py players --event 8041

# Ver status
python cli.py status
```

## 📖 Comandos Disponíveis

### 🔥 `sync_all.py` - Sincronização Completa (NOVO!)

**Este é o comando principal para coletar TODOS os dados.**

```bash
# Sincronizar tudo automaticamente
python sync_all.py --limit 5

# Opções disponíveis:
python sync_all.py --limit 3        # Limitar a 3 eventos (teste)
python sync_all.py --event 8041     # Apenas um evento específico
python sync_all.py --show           # Mostrar browser (debug)
python sync_all.py --init           # Inicializar DB antes de sync
```

**O que faz:**
1. ✅ Busca todos os eventos
2. ✅ Para cada evento:
   - Busca todos os times participantes
   - Busca placements (1º, 2º, 3º, 4º)
   - Busca prizes de cada time
   - Para cada time:
     - Busca roster completo
     - Busca stats completos de cada jogador

### 📋 Comandos CLI individuais

#### `init` - Inicializar banco
```bash
python cli.py init
```

#### `events` - Sincronizar eventos
```bash
python cli.py events --limit 10
```

#### `teams` - Sincronizar times
```bash
python cli.py teams 8041
```

#### `players` - Sincronizar players
```bash
python cli.py players --event 8041
python cli.py players --team 4608
```

#### `status` - Ver status do banco
```bash
python cli.py status
```

## 🔄 Fluxo Completo

```bash
# 1. Buscar eventos
./cli.py events --limit 5

# 2. Ver eventos salvos
./cli.py status

# 3. Sincronizar times do primeiro evento (use o ID do status)
./cli.py teams 8041

# 4. Sincronizar jogadores e stats do evento
./cli.py players --event 8041
```

## 📊 Estrutura do Banco (Completa!)

```
events          → Eventos (id, name, start_date, end_date, location, prize_pool, event_type)
teams           → Times (id, name, country, world_rank)
players         → Jogadores completo:
                  - Perfil: id, nickname, real_name, country, age, current_team_id
                  - Stats: rating_2_0, kast, kd_ratio, headshot_percentage
                  - Detalhes: total_kills, total_deaths, total_maps, total_rounds
                  - Performance: kpr, apr, impact, adr
event_teams     → Relacionamento eventos ↔ times
                  - Com placement (1º, 2º, 3º, 4º)
                  - Com prize (premiação)
team_players    → Histórico de roster dos times
event_stats     → Stats dos jogadores por evento específico
```

## 🏗️ Estrutura do Projeto

```
hltv/
├── cli.py                 # CLI principal
├── src/
│   ├── database/
│   │   ├── __init__.py   # Configuração do banco
│   │   └── models.py     # Models SQLAlchemy
│   └── scrapers/
│       ├── events.py     # Scraper de eventos
│       ├── teams.py      # Scraper de times
│       └── players.py    # Scraper de jogadores
├── hltv_data.db          # Database SQLite
└── requirements.txt
```

## ⚙️ Tecnologias

- **Python 3.10+**
- **Selenium + ChromeDriver** - Web scraping
- **SQLAlchemy** - ORM
- **SQLite** - Database

## 📝 Notas Importantes

### ⚡ Otimizações VPS
- ✅ Configurado para rodar em VPS sem display
- ✅ Modo headless otimizado (--headless antigo, mais estável)
- ✅ Opções anti-detecção configuradas
- ✅ Rate limiting entre requisições (evita bloqueios)
- ✅ Binary location do Chromium configurado automaticamente

### 🔧 Performance
- Por padrão, browser roda em modo headless (invisível)
- Use `--show` para ver o browser em ação (útil para debug)
- Delays configurados entre requisições (2-5s)
- Dados salvos incrementalmente (pode pausar e continuar)

### 📊 Stats Coletados por Jogador
- ✅ Rating 2.0 (métrica principal de performance)
- ✅ KAST (Kill, Assist, Survive, Trade %)
- ✅ K/D Ratio, ADR (Average Damage per Round)
- ✅ Headshot %, Total Kills/Deaths
- ✅ Maps played, Rounds played
- ✅ KPR (Kills per Round), Impact

### 🎯 Use Cases
- Análise de performance de jogadores
- Tracking de histórico de times
- Identificação de talentos
- Análise estatística avançada
- Machine Learning com dados competitivos

## 🚨 Troubleshooting

### Chrome/Chromium não encontrado
```bash
# Instalar Chromium
sudo pacman -S chromium  # Arch
sudo apt install chromium-browser  # Ubuntu/Debian
```

### Erro de timeout
- Use `--show` para verificar se está sendo bloqueado
- Aumentar delays no código se necessário
- HLTV pode ter proteção Cloudflare ativa

### Stats não aparecem
- Verifique se o scraper completou sem erros
- Use `python cli.py status` para ver quantos registros existem
- Re-sync com `python sync_all.py --event <ID>`

---

**Desenvolvido para coleta e análise completa de dados do CS2 competitivo** 🎯

**Sistema otimizado para VPS e produção!** 🚀
