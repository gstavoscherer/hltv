# Discord Bot Redesign — Design

## Goal
Redesign CartolaCS Discord bot with rich embeds, role-based filtering, and new discovery commands.

## Scope

### 1. Role Scraping
- Scrape roles from HLTV team page (`/team/X/name`) lineup section
- Save to `TeamPlayer.role` (per-team, not per-player)
- Roles: `awper`, `igl`, `entry`, `rifler`, `support`
- Integrate into `sync_weekly.py`

### 2. Visual Style
- Colors: info `0x2f3136`, lucro `0x2ecc71`, perda `0xe74c3c`, ranking `0xf1c40f`, role `0x9b59b6`
- Role emojis: AWP, IGL, Entry, Rifler, Support
- Stat bars: `████████░░ 1.24`
- Footer: `CartolaCS * atualizado ha X min`

### 3. Commands

**Existing (visual redesign):** market, portfolio, ranking, buy, sell, history, link

**New:**
- `/cartola-top [role]` — top 10 by price, filterable by role
- `/cartola-compare jogador1 jogador2` — side-by-side stats
- `/cartola-trending [periodo]` — top movers (24h/7d)
- `/cartola-team [time]` — roster + roles + rank + map pool
- `/cartola-scout [role] [max_preco]` — best value players

### 4. Files
- `cartola/bot.py` — full rewrite
- `src/scrapers/teams.py` — role scraping from lineup
- `sync_weekly.py` — integrate role scraping
