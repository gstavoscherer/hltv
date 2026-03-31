"""
Discord bot do CartolaCS.
Roda no mesmo processo que o FastAPI.
Rich embeds, role filtering, e comandos de descoberta.
"""

import os
from datetime import datetime, timedelta

import discord
from discord import app_commands

from src.database import session_scope
from src.database.models import (
    Player, Team, PlayerMarket, PlayerPriceHistory, PlayerRole,
    User, UserPortfolio, Transaction, TeamPlayer, TeamMapStats, Match,
)
from sqlalchemy import and_

DISCORD_TOKEN = os.environ.get("DISCORD_BOT_TOKEN", "")
SITE_URL = "https://gustavoscherer.com/hltv/cartola"

# ============================================================================
# VISUAL STYLE
# ============================================================================

COLORS = {
    "info": 0x2F3136,
    "lucro": 0x2ECC71,
    "perda": 0xE74C3C,
    "ranking": 0xF1C40F,
    "role": 0x9B59B6,
    "neutral": 0x3498DB,
}

ROLE_EMOJIS = {
    "awper": "\U0001f3af",    # target
    "igl": "\U0001f9e0",      # brain
    "entry": "\u2694\ufe0f",   # swords
    "rifler": "\U0001f52b",    # gun
    "support": "\U0001f6e1\ufe0f",  # shield
    "lurker": "\U0001f47b",    # ghost
}

TREND_UP = "\U0001f4c8"
TREND_DOWN = "\U0001f4c9"


def _stat_bar(value, max_val=2.0, length=10):
    """Generate a visual stat bar like: ████████░░ 1.24"""
    if value is None:
        return "`??????????` --"
    ratio = min(max(value / max_val, 0), 1.0)
    filled = round(ratio * length)
    bar = "\u2588" * filled + "\u2591" * (length - filled)
    return f"`{bar}` {value:.2f}"


def _price_color(change_pct):
    if change_pct is None or change_pct == 0:
        return COLORS["info"]
    return COLORS["lucro"] if change_pct > 0 else COLORS["perda"]


def _footer(embed):
    embed.set_footer(text=f"CartolaCS \u2022 {datetime.utcnow().strftime('%d/%m %H:%M')} UTC")
    return embed


def _get_player_role(player_id, session):
    """Get role string from TeamPlayer (per-team role)."""
    tp = (
        session.query(TeamPlayer)
        .filter(TeamPlayer.player_id == player_id, TeamPlayer.is_current == True)
        .first()
    )
    return tp.role if tp and tp.role else 'rifler'


def _get_player_role_str(player_id, session):
    role = _get_player_role(player_id, session)
    emoji = ROLE_EMOJIS.get(role, "")
    return f"{emoji} {role.upper()}"


def _get_user_by_discord(discord_id, session):
    return session.query(User).filter(User.discord_id == str(discord_id)).first()


# ============================================================================
# BOT SETUP
# ============================================================================

class CartolaBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        await self.tree.sync()

    async def on_ready(self):
        print(f"Discord bot online: {self.user} (guilds: {len(self.guilds)})")


bot = CartolaBot()


# ============================================================================
# COMANDOS PUBLICOS
# ============================================================================

@bot.tree.command(name="cartola-market", description="Ver mercado de jogadores")
@app_commands.describe(jogador="Nome do jogador (opcional)")
async def market_cmd(interaction: discord.Interaction, jogador: str = None):
    with session_scope() as s:
        if jogador:
            player = s.query(Player).filter(Player.nickname.ilike(f"%{jogador}%")).first()
            if not player:
                await interaction.response.send_message(f"Jogador '{jogador}' nao encontrado", ephemeral=True)
                return
            market = s.query(PlayerMarket).get(player.id)
            if not market:
                await interaction.response.send_message(f"{player.nickname} nao esta no mercado", ephemeral=True)
                return
            team = s.query(Team).get(player.current_team_id) if player.current_team_id else None
            role_str = _get_player_role_str(player.id, s)

            embed = discord.Embed(
                title=f"{player.nickname}",
                description=role_str or "Sem role definida",
                color=_price_color(market.price_change_pct),
            )
            embed.add_field(name="Preco", value=f"**{market.current_price:.2f}**", inline=True)
            change = market.price_change_pct or 0
            emoji = TREND_UP if change >= 0 else TREND_DOWN
            embed.add_field(name="Variacao", value=f"{emoji} {change:+.2f}%", inline=True)
            embed.add_field(name="Time", value=team.name if team else "Free agent", inline=True)
            embed.add_field(name="Rating", value=_stat_bar(player.rating_2_0), inline=False)
            if player.adr:
                embed.add_field(name="ADR", value=_stat_bar(player.adr, max_val=120), inline=True)
            if player.kast:
                embed.add_field(name="KAST", value=_stat_bar(player.kast, max_val=100), inline=True)
            if player.impact:
                embed.add_field(name="Impact", value=_stat_bar(player.impact), inline=True)

            await interaction.response.send_message(embed=_footer(embed))
        else:
            markets = (
                s.query(PlayerMarket, Player)
                .join(Player, PlayerMarket.player_id == Player.id)
                .order_by(PlayerMarket.current_price.desc())
                .limit(10)
                .all()
            )
            embed = discord.Embed(title="Top 10 Mercado CartolaCS", color=COLORS["info"])
            for i, (m, p) in enumerate(markets, 1):
                change = m.price_change_pct or 0
                emoji = TREND_UP if change >= 0 else TREND_DOWN
                role_str = _get_player_role_str(p.id, s)
                team = s.query(Team).get(p.current_team_id) if p.current_team_id else None
                team_name = team.name if team else "FA"
                embed.add_field(
                    name=f"#{i} {p.nickname} ({team_name})",
                    value=f"**{m.current_price:.2f}** {emoji} {change:+.1f}% {role_str}",
                    inline=False,
                )
            await interaction.response.send_message(embed=_footer(embed))


@bot.tree.command(name="cartola-ranking", description="Ranking de jogadores do CartolaCS")
@app_commands.describe(tipo="patrimonio, lucro ou semanal")
@app_commands.choices(tipo=[
    app_commands.Choice(name="Patrimonio", value="patrimonio"),
    app_commands.Choice(name="Lucro", value="lucro"),
    app_commands.Choice(name="Semanal", value="semanal"),
])
async def ranking_cmd(interaction: discord.Interaction, tipo: str = "patrimonio"):
    with session_scope() as s:
        users = s.query(User).all()
        ranking = []
        for u in users:
            items = s.query(UserPortfolio).filter(UserPortfolio.user_id == u.id).all()
            total = u.balance
            for item in items:
                market = s.query(PlayerMarket).get(item.player_id)
                total += market.current_price if market else item.buy_price
            ranking.append({"username": u.username, "total": total, "profit": total - 100.0})

        if tipo == "lucro":
            ranking.sort(key=lambda x: x["profit"], reverse=True)
            title = "\U0001f4b0 Ranking por Lucro"
            field = "profit"
            fmt = "{:+.2f}"
        elif tipo == "semanal":
            ranking.sort(key=lambda x: x["profit"], reverse=True)
            title = "\U0001f4c5 Ranking Semanal"
            field = "profit"
            fmt = "{:+.2f}"
        else:
            ranking.sort(key=lambda x: x["total"], reverse=True)
            title = "\U0001f3c6 Ranking por Patrimonio"
            field = "total"
            fmt = "{:.2f}"

        embed = discord.Embed(title=title, color=COLORS["ranking"])
        medals = ["\U0001f947", "\U0001f948", "\U0001f949"]
        for i, r in enumerate(ranking[:10], 0):
            prefix = medals[i] if i < 3 else f"**#{i+1}**"
            embed.add_field(
                name=f"{prefix} {r['username']}",
                value=fmt.format(r[field]),
                inline=False,
            )
        if not ranking:
            embed.description = "Nenhum jogador cadastrado ainda."

        await interaction.response.send_message(embed=_footer(embed))


# ============================================================================
# COMANDOS AUTENTICADOS
# ============================================================================

@bot.tree.command(name="cartola-link", description="Vincular conta Discord ao CartolaCS")
async def link_cmd(interaction: discord.Interaction):
    with session_scope() as s:
        user = _get_user_by_discord(interaction.user.id, s)
        if user:
            embed = discord.Embed(
                title="\u2705 Conta Vinculada",
                description=f"Ja vinculado como **{user.username}**",
                color=COLORS["lucro"],
            )
            await interaction.response.send_message(embed=_footer(embed), ephemeral=True)
            return
    embed = discord.Embed(
        title="\U0001f517 Vincular Conta",
        description=f"[Clique aqui para vincular]({SITE_URL}/link?discord_id={interaction.user.id})",
        color=COLORS["neutral"],
    )
    await interaction.response.send_message(embed=_footer(embed), ephemeral=True)


@bot.tree.command(name="cartola-portfolio", description="Ver meu time e saldo")
async def portfolio_cmd(interaction: discord.Interaction):
    with session_scope() as s:
        user = _get_user_by_discord(interaction.user.id, s)
        if not user:
            await interaction.response.send_message(
                "Conta nao vinculada. Use `/cartola-link`", ephemeral=True
            )
            return

        items = s.query(UserPortfolio).filter(UserPortfolio.user_id == user.id).all()

        total = user.balance
        lines = []
        for item in items:
            player = s.query(Player).get(item.player_id)
            market = s.query(PlayerMarket).get(item.player_id)
            price = market.current_price if market else item.buy_price
            profit = price - item.buy_price
            total += price
            emoji = TREND_UP if profit >= 0 else TREND_DOWN
            role_str = _get_player_role_str(item.player_id, s)
            nick = player.nickname if player else "Unknown"
            lines.append(
                f"{emoji} **{nick}** {role_str}\n"
                f"Compra: {item.buy_price:.2f} | Atual: **{price:.2f}** | {profit:+.2f}"
            )

        total_profit = total - 100.0
        color = COLORS["lucro"] if total_profit >= 0 else COLORS["perda"]
        embed = discord.Embed(
            title=f"\U0001f4bc Portfolio de {user.username}",
            color=color,
        )
        embed.add_field(name="\U0001f4b5 Saldo", value=f"**{user.balance:.2f}**", inline=True)
        embed.add_field(name="\U0001f3e6 Patrimonio", value=f"**{total:.2f}**", inline=True)
        profit_emoji = TREND_UP if total_profit >= 0 else TREND_DOWN
        embed.add_field(name=f"{profit_emoji} Lucro Total", value=f"**{total_profit:+.2f}**", inline=True)

        if lines:
            embed.add_field(name=f"\U0001f465 Time ({len(items)}/5)", value="\n\n".join(lines), inline=False)
        else:
            embed.add_field(name="\U0001f465 Time (0/5)", value="Nenhum jogador. Use `/cartola-buy`", inline=False)

        await interaction.response.send_message(embed=_footer(embed))


@bot.tree.command(name="cartola-buy", description="Comprar jogador")
@app_commands.describe(jogador="Nome do jogador")
async def buy_cmd(interaction: discord.Interaction, jogador: str):
    with session_scope() as s:
        user = _get_user_by_discord(interaction.user.id, s)
        if not user:
            await interaction.response.send_message("Conta nao vinculada. Use `/cartola-link`", ephemeral=True)
            return

        player = s.query(Player).filter(Player.nickname.ilike(f"%{jogador}%")).first()
        if not player:
            await interaction.response.send_message(f"Jogador '{jogador}' nao encontrado", ephemeral=True)
            return

        market = s.query(PlayerMarket).get(player.id)
        if not market:
            await interaction.response.send_message(f"{player.nickname} nao esta no mercado", ephemeral=True)
            return

        count = s.query(UserPortfolio).filter(UserPortfolio.user_id == user.id).count()
        if count >= 5:
            embed = discord.Embed(title="\u274c Limite Atingido", description="Maximo de 5 jogadores!", color=COLORS["perda"])
            await interaction.response.send_message(embed=_footer(embed), ephemeral=True)
            return

        existing = s.query(UserPortfolio).filter(
            UserPortfolio.user_id == user.id, UserPortfolio.player_id == player.id
        ).first()
        if existing:
            await interaction.response.send_message(f"Voce ja tem {player.nickname}!", ephemeral=True)
            return

        if user.balance < market.current_price:
            embed = discord.Embed(
                title="\u274c Saldo Insuficiente",
                description=f"Precisa: **{market.current_price:.2f}** | Tem: **{user.balance:.2f}**",
                color=COLORS["perda"],
            )
            await interaction.response.send_message(embed=_footer(embed), ephemeral=True)
            return

        user.balance -= market.current_price
        s.add(UserPortfolio(user_id=user.id, player_id=player.id, buy_price=market.current_price))
        s.add(Transaction(user_id=user.id, player_id=player.id, type="buy", price=market.current_price))

        role_str = _get_player_role_str(player.id, s)
        embed = discord.Embed(
            title=f"\u2705 Compra: {player.nickname}",
            description=f"{role_str}\nPreco: **{market.current_price:.2f}**\nSaldo restante: **{user.balance:.2f}**",
            color=COLORS["lucro"],
        )
        await interaction.response.send_message(embed=_footer(embed))


@bot.tree.command(name="cartola-sell", description="Vender jogador")
@app_commands.describe(jogador="Nome do jogador")
async def sell_cmd(interaction: discord.Interaction, jogador: str):
    with session_scope() as s:
        user = _get_user_by_discord(interaction.user.id, s)
        if not user:
            await interaction.response.send_message("Conta nao vinculada. Use `/cartola-link`", ephemeral=True)
            return

        player = s.query(Player).filter(Player.nickname.ilike(f"%{jogador}%")).first()
        if not player:
            await interaction.response.send_message(f"Jogador '{jogador}' nao encontrado", ephemeral=True)
            return

        item = s.query(UserPortfolio).filter(
            UserPortfolio.user_id == user.id, UserPortfolio.player_id == player.id
        ).first()
        if not item:
            await interaction.response.send_message(f"Voce nao tem {player.nickname}!", ephemeral=True)
            return

        market = s.query(PlayerMarket).get(player.id)
        sell_price = market.current_price if market else item.buy_price
        profit = sell_price - item.buy_price

        user.balance += sell_price
        s.delete(item)
        s.add(Transaction(user_id=user.id, player_id=player.id, type="sell", price=sell_price))

        emoji = TREND_UP if profit >= 0 else TREND_DOWN
        color = COLORS["lucro"] if profit >= 0 else COLORS["perda"]
        embed = discord.Embed(
            title=f"\U0001f4b8 Venda: {player.nickname}",
            description=f"Preco: **{sell_price:.2f}**\n{emoji} Lucro: **{profit:+.2f}**\nSaldo: **{user.balance:.2f}**",
            color=color,
        )
        await interaction.response.send_message(embed=_footer(embed))


@bot.tree.command(name="cartola-history", description="Historico de transacoes")
async def history_cmd(interaction: discord.Interaction):
    with session_scope() as s:
        user = _get_user_by_discord(interaction.user.id, s)
        if not user:
            await interaction.response.send_message("Conta nao vinculada. Use `/cartola-link`", ephemeral=True)
            return

        txs = (
            s.query(Transaction)
            .filter(Transaction.user_id == user.id)
            .order_by(Transaction.timestamp.desc())
            .limit(10)
            .all()
        )
        if not txs:
            await interaction.response.send_message("Nenhuma transacao ainda.", ephemeral=True)
            return

        embed = discord.Embed(title=f"\U0001f4dc Historico de {user.username}", color=COLORS["info"])
        for tx in txs:
            player = s.query(Player).get(tx.player_id)
            emoji = "\U0001f7e2" if tx.type == "buy" else "\U0001f534"
            ts = tx.timestamp.strftime("%d/%m %H:%M") if tx.timestamp else ""
            nick = player.nickname if player else "Unknown"
            embed.add_field(
                name=f"{emoji} {tx.type.upper()} {nick}",
                value=f"**{tx.price:.2f}** — {ts}",
                inline=False,
            )
        await interaction.response.send_message(embed=_footer(embed))


# ============================================================================
# NOVOS COMANDOS DE DESCOBERTA
# ============================================================================

@bot.tree.command(name="cartola-top", description="Top jogadores por preco, filtravel por role")
@app_commands.describe(role="Filtrar por role: awper, igl, entry, rifler, support")
@app_commands.choices(role=[
    app_commands.Choice(name="AWPer", value="awper"),
    app_commands.Choice(name="IGL", value="igl"),
    app_commands.Choice(name="Entry", value="entry"),
    app_commands.Choice(name="Rifler", value="rifler"),
    app_commands.Choice(name="Support", value="support"),
])
async def top_cmd(interaction: discord.Interaction, role: str = None):
    with session_scope() as s:
        q = (
            s.query(PlayerMarket, Player)
            .join(Player, PlayerMarket.player_id == Player.id)
        )
        if role:
            q = q.join(TeamPlayer, and_(
                TeamPlayer.player_id == Player.id,
                TeamPlayer.is_current == True,
            )).filter(TeamPlayer.role == role)

        results = q.order_by(PlayerMarket.current_price.desc()).limit(10).all()

        title = f"Top 10 {ROLE_EMOJIS.get(role, '')} {role.upper()}" if role else "Top 10 Mais Caros"
        embed = discord.Embed(title=title, color=COLORS["role"] if role else COLORS["info"])

        for i, (m, p) in enumerate(results, 1):
            change = m.price_change_pct or 0
            emoji = TREND_UP if change >= 0 else TREND_DOWN
            role_str = _get_player_role_str(p.id, s)
            team = s.query(Team).get(p.current_team_id) if p.current_team_id else None
            team_name = team.name if team else "FA"
            rating = f"Rating: {p.rating_2_0:.2f}" if p.rating_2_0 else ""
            embed.add_field(
                name=f"#{i} {p.nickname} ({team_name})",
                value=f"**{m.current_price:.2f}** {emoji} {change:+.1f}% | {rating} {role_str}",
                inline=False,
            )

        if not results:
            embed.description = "Nenhum jogador encontrado."

        await interaction.response.send_message(embed=_footer(embed))


@bot.tree.command(name="cartola-compare", description="Comparar dois jogadores lado a lado")
@app_commands.describe(jogador1="Primeiro jogador", jogador2="Segundo jogador")
async def compare_cmd(interaction: discord.Interaction, jogador1: str, jogador2: str):
    with session_scope() as s:
        p1 = s.query(Player).filter(Player.nickname.ilike(f"%{jogador1}%")).first()
        p2 = s.query(Player).filter(Player.nickname.ilike(f"%{jogador2}%")).first()

        if not p1:
            await interaction.response.send_message(f"Jogador '{jogador1}' nao encontrado", ephemeral=True)
            return
        if not p2:
            await interaction.response.send_message(f"Jogador '{jogador2}' nao encontrado", ephemeral=True)
            return

        m1 = s.query(PlayerMarket).get(p1.id)
        m2 = s.query(PlayerMarket).get(p2.id)

        embed = discord.Embed(
            title=f"\u2694\ufe0f {p1.nickname} vs {p2.nickname}",
            color=COLORS["neutral"],
        )

        def _compare_line(label, v1, v2, fmt=".2f", higher_better=True):
            s1 = f"{v1:{fmt}}" if v1 is not None else "--"
            s2 = f"{v2:{fmt}}" if v2 is not None else "--"
            if v1 is not None and v2 is not None:
                if (v1 > v2) == higher_better:
                    s1 = f"**{s1}**"
                elif (v2 > v1) == higher_better:
                    s2 = f"**{s2}**"
            return f"{label}: {s1} vs {s2}"

        lines = [
            _compare_line("Preco", m1.current_price if m1 else None, m2.current_price if m2 else None),
            _compare_line("Rating", p1.rating_2_0, p2.rating_2_0),
            _compare_line("ADR", p1.adr, p2.adr),
            _compare_line("KAST", p1.kast, p2.kast),
            _compare_line("K/D", p1.kd_ratio, p2.kd_ratio),
            _compare_line("Impact", p1.impact, p2.impact),
        ]

        r1 = _get_player_role_str(p1.id, s)
        r2 = _get_player_role_str(p2.id, s)

        t1 = s.query(Team).get(p1.current_team_id) if p1.current_team_id else None
        t2 = s.query(Team).get(p2.current_team_id) if p2.current_team_id else None

        embed.add_field(
            name=f"{p1.nickname} ({t1.name if t1 else 'FA'})",
            value=r1 or "Sem role",
            inline=True,
        )
        embed.add_field(
            name=f"{p2.nickname} ({t2.name if t2 else 'FA'})",
            value=r2 or "Sem role",
            inline=True,
        )
        embed.add_field(name="\u200b", value="\u200b", inline=True)  # spacer
        embed.add_field(name="Stats", value="\n".join(lines), inline=False)

        await interaction.response.send_message(embed=_footer(embed))


@bot.tree.command(name="cartola-trending", description="Top valorizacoes e desvalorizacoes")
@app_commands.describe(periodo="Periodo: 24h ou 7d")
@app_commands.choices(periodo=[
    app_commands.Choice(name="24 horas", value="24h"),
    app_commands.Choice(name="7 dias", value="7d"),
])
async def trending_cmd(interaction: discord.Interaction, periodo: str = "24h"):
    with session_scope() as s:
        # Get top gainers and losers by price_change_pct
        gainers = (
            s.query(PlayerMarket, Player)
            .join(Player, PlayerMarket.player_id == Player.id)
            .filter(PlayerMarket.price_change_pct.isnot(None))
            .order_by(PlayerMarket.price_change_pct.desc())
            .limit(5)
            .all()
        )
        losers = (
            s.query(PlayerMarket, Player)
            .join(Player, PlayerMarket.player_id == Player.id)
            .filter(PlayerMarket.price_change_pct.isnot(None))
            .order_by(PlayerMarket.price_change_pct.asc())
            .limit(5)
            .all()
        )

        embed = discord.Embed(
            title=f"\U0001f525 Trending ({periodo})",
            color=COLORS["info"],
        )

        gainer_lines = []
        for m, p in gainers:
            change = m.price_change_pct or 0
            if change <= 0:
                continue
            gainer_lines.append(f"{TREND_UP} **{p.nickname}** {change:+.1f}% ({m.current_price:.2f})")
        embed.add_field(
            name="\U0001f4c8 Maiores Altas",
            value="\n".join(gainer_lines) if gainer_lines else "Nenhuma alta",
            inline=False,
        )

        loser_lines = []
        for m, p in losers:
            change = m.price_change_pct or 0
            if change >= 0:
                continue
            loser_lines.append(f"{TREND_DOWN} **{p.nickname}** {change:+.1f}% ({m.current_price:.2f})")
        embed.add_field(
            name="\U0001f4c9 Maiores Baixas",
            value="\n".join(loser_lines) if loser_lines else "Nenhuma baixa",
            inline=False,
        )

        await interaction.response.send_message(embed=_footer(embed))


@bot.tree.command(name="cartola-team", description="Ver roster e info de um time")
@app_commands.describe(time="Nome do time")
async def team_cmd(interaction: discord.Interaction, time: str):
    with session_scope() as s:
        team = s.query(Team).filter(Team.name.ilike(f"%{time}%")).first()
        if not team:
            await interaction.response.send_message(f"Time '{time}' nao encontrado", ephemeral=True)
            return

        roster = (
            s.query(TeamPlayer, Player)
            .join(Player, TeamPlayer.player_id == Player.id)
            .filter(TeamPlayer.team_id == team.id, TeamPlayer.is_current == True)
            .all()
        )

        rank_str = f"#{team.world_rank}" if team.world_rank else "Sem ranking"
        embed = discord.Embed(
            title=f"\U0001f3ae {team.name}",
            description=f"\U0001f30d {team.country or '??'} | {rank_str}",
            color=COLORS["info"],
        )

        roster_lines = []
        for tp, player in sorted(roster, key=lambda x: -(x[1].rating_2_0 or 0)):
            role = tp.role or 'rifler'
            emoji = ROLE_EMOJIS.get(role, "")
            market = s.query(PlayerMarket).get(player.id)
            price_str = f"**{market.current_price:.2f}**" if market else "--"
            rating_str = f"{player.rating_2_0:.2f}" if player.rating_2_0 else "--"
            roster_lines.append(
                f"{emoji} **{player.nickname}** ({role.upper()}) \u2022 "
                f"Rating: {rating_str} \u2022 {price_str}"
            )

        if roster_lines:
            embed.add_field(
                name=f"\U0001f465 Roster ({len(roster)})",
                value="\n".join(roster_lines),
                inline=False,
            )
        else:
            embed.add_field(name="Roster", value="Nenhum jogador encontrado", inline=False)

        # Map pool stats
        map_stats = (
            s.query(TeamMapStats)
            .filter(TeamMapStats.team_id == team.id)
            .order_by(TeamMapStats.times_played.desc())
            .limit(5)
            .all()
        )
        if map_stats:
            map_lines = []
            for ms in map_stats:
                wr = (ms.wins / ms.times_played * 100) if ms.times_played > 0 else 0
                filled = round(wr / 100 * 8)
                bar = "\u2588" * filled + "\u2591" * (8 - filled)
                losses = ms.times_played - ms.wins
                map_lines.append(f"`{ms.map_name:10s}` `{bar}` **{wr:.0f}%** ({ms.wins}W/{losses}L)")
            embed.add_field(
                name="\U0001f5fa\ufe0f Map Pool",
                value="\n".join(map_lines),
                inline=False,
            )

        await interaction.response.send_message(embed=_footer(embed))


@bot.tree.command(name="cartola-scout", description="Encontrar jogadores com melhor custo-beneficio")
@app_commands.describe(role="Filtrar por role", max_preco="Preco maximo")
@app_commands.choices(role=[
    app_commands.Choice(name="AWPer", value="awper"),
    app_commands.Choice(name="IGL", value="igl"),
    app_commands.Choice(name="Entry", value="entry"),
    app_commands.Choice(name="Rifler", value="rifler"),
    app_commands.Choice(name="Support", value="support"),
])
async def scout_cmd(interaction: discord.Interaction, role: str = None, max_preco: float = None):
    with session_scope() as s:
        q = (
            s.query(PlayerMarket, Player)
            .join(Player, PlayerMarket.player_id == Player.id)
            .filter(Player.rating_2_0.isnot(None))
        )
        if role:
            q = q.join(TeamPlayer, and_(
                TeamPlayer.player_id == Player.id,
                TeamPlayer.is_current == True,
            )).filter(TeamPlayer.role == role)
        if max_preco:
            q = q.filter(PlayerMarket.current_price <= max_preco)

        results = q.all()

        # Score = rating / price (higher = better value)
        scored = []
        for m, p in results:
            if m.current_price > 0 and p.rating_2_0:
                score = p.rating_2_0 / m.current_price
                scored.append((score, m, p))

        scored.sort(key=lambda x: x[0], reverse=True)

        title = "\U0001f50d Scout"
        if role:
            title += f" {ROLE_EMOJIS.get(role, '')} {role.upper()}"
        if max_preco:
            title += f" (max {max_preco:.0f})"

        embed = discord.Embed(title=title, color=COLORS["role"])

        for i, (score, m, p) in enumerate(scored[:10], 1):
            role_str = _get_player_role_str(p.id, s)
            team = s.query(Team).get(p.current_team_id) if p.current_team_id else None
            team_name = team.name if team else "FA"
            change = m.price_change_pct or 0
            emoji = TREND_UP if change >= 0 else TREND_DOWN
            embed.add_field(
                name=f"#{i} {p.nickname} ({team_name})",
                value=(
                    f"Preco: **{m.current_price:.2f}** {emoji} {change:+.1f}%\n"
                    f"Rating: **{p.rating_2_0:.2f}** | Valor: {score:.3f} {role_str}"
                ),
                inline=False,
            )

        if not scored:
            embed.description = "Nenhum jogador encontrado com esses filtros."

        await interaction.response.send_message(embed=_footer(embed))


# ============================================================================
# START
# ============================================================================

async def start_bot():
    if not DISCORD_TOKEN:
        print("DISCORD_BOT_TOKEN nao configurado, bot nao iniciado")
        return
    print(f"Iniciando Discord bot (token: {DISCORD_TOKEN[:10]}...)")
    try:
        await bot.start(DISCORD_TOKEN)
    except Exception as e:
        print(f"Erro ao iniciar Discord bot: {e}")
