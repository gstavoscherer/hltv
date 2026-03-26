"""
Discord bot do CartolaCS.
Roda no mesmo processo que o FastAPI.
"""

import os
import discord
from discord import app_commands

from src.database import session_scope
from src.database.models import (
    Player, Team, PlayerMarket, User, UserPortfolio, Transaction,
)

DISCORD_TOKEN = os.environ.get("DISCORD_BOT_TOKEN", "")
SITE_URL = "https://gustavoscherer.com/hltv/cartola"


class CartolaBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        await self.tree.sync()


bot = CartolaBot()


def _get_user_by_discord(discord_id, session):
    return session.query(User).filter(User.discord_id == str(discord_id)).first()


# ============================================================================
# COMANDOS PUBLICOS
# ============================================================================

@bot.tree.command(name="cartola-market", description="Top jogadores do mercado")
async def market_cmd(interaction: discord.Interaction, jogador: str = None):
    with session_scope() as s:
        if jogador:
            player = s.query(Player).filter(Player.nickname.ilike(f"%{jogador}%")).first()
            if not player:
                await interaction.response.send_message(f"Jogador '{jogador}' nao encontrado")
                return
            market = s.query(PlayerMarket).get(player.id)
            if not market:
                await interaction.response.send_message(f"{player.nickname} nao esta no mercado")
                return
            team = s.query(Team).get(player.current_team_id) if player.current_team_id else None
            embed = discord.Embed(
                title=player.nickname,
                color=0x00ff00 if (market.price_change_pct or 0) >= 0 else 0xff0000,
            )
            embed.add_field(name="Preco", value=f"{market.current_price:.2f}", inline=True)
            embed.add_field(name="Variacao", value=f"{market.price_change_pct:+.2f}%", inline=True)
            embed.add_field(name="Time", value=team.name if team else "Free agent", inline=True)
            embed.add_field(name="Rating", value=f"{player.rating_2_0:.2f}" if player.rating_2_0 else "--", inline=True)
            await interaction.response.send_message(embed=embed)
        else:
            markets = (
                s.query(PlayerMarket, Player)
                .join(Player, PlayerMarket.player_id == Player.id)
                .order_by(PlayerMarket.current_price.desc())
                .limit(10)
                .all()
            )
            embed = discord.Embed(title="Top 10 Mercado CartolaCS", color=0x1a1a2e)
            for m, p in markets:
                change = f"{m.price_change_pct:+.2f}%" if m.price_change_pct else "0%"
                embed.add_field(name=p.nickname, value=f"{m.current_price:.2f} ({change})", inline=False)
            await interaction.response.send_message(embed=embed)


@bot.tree.command(name="cartola-ranking", description="Ranking de jogadores")
@app_commands.describe(tipo="patrimonio ou lucro")
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

        if tipo in ("lucro", "profit"):
            ranking.sort(key=lambda x: x["profit"], reverse=True)
            title = "Ranking por Lucro"
            field = "profit"
        else:
            ranking.sort(key=lambda x: x["total"], reverse=True)
            title = "Ranking por Patrimonio"
            field = "total"

        embed = discord.Embed(title=title, color=0x1a1a2e)
        for i, r in enumerate(ranking[:10], 1):
            embed.add_field(name=f"#{i} {r['username']}", value=f"{r[field]:.2f}", inline=False)
        await interaction.response.send_message(embed=embed)


# ============================================================================
# COMANDOS AUTENTICADOS
# ============================================================================

@bot.tree.command(name="cartola-link", description="Vincular conta Discord ao CartolaCS")
async def link_cmd(interaction: discord.Interaction):
    with session_scope() as s:
        user = _get_user_by_discord(interaction.user.id, s)
        if user:
            await interaction.response.send_message(f"Ja vinculado como **{user.username}**!", ephemeral=True)
            return
    await interaction.response.send_message(
        f"Acesse o site pra vincular sua conta:\n{SITE_URL}/link?discord_id={interaction.user.id}",
        ephemeral=True,
    )


@bot.tree.command(name="cartola-portfolio", description="Ver meu time")
async def portfolio_cmd(interaction: discord.Interaction):
    with session_scope() as s:
        user = _get_user_by_discord(interaction.user.id, s)
        if not user:
            await interaction.response.send_message("Conta nao vinculada. Use `/cartola-link`", ephemeral=True)
            return

        items = s.query(UserPortfolio).filter(UserPortfolio.user_id == user.id).all()
        embed = discord.Embed(title=f"Portfolio de {user.username}", color=0x1a1a2e)
        embed.add_field(name="Saldo", value=f"{user.balance:.2f}", inline=False)

        total = user.balance
        for item in items:
            player = s.query(Player).get(item.player_id)
            market = s.query(PlayerMarket).get(item.player_id)
            price = market.current_price if market else item.buy_price
            profit = price - item.buy_price
            total += price
            emoji = "\U0001f4c8" if profit >= 0 else "\U0001f4c9"
            embed.add_field(
                name=f"{emoji} {player.nickname if player else 'Unknown'}",
                value=f"Compra: {item.buy_price:.2f} | Atual: {price:.2f} | {profit:+.2f}",
                inline=False,
            )

        embed.add_field(name="Patrimonio Total", value=f"{total:.2f}", inline=False)
        await interaction.response.send_message(embed=embed)


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
            await interaction.response.send_message(f"Jogador '{jogador}' nao encontrado")
            return

        market = s.query(PlayerMarket).get(player.id)
        if not market:
            await interaction.response.send_message(f"{player.nickname} nao esta no mercado")
            return

        count = s.query(UserPortfolio).filter(UserPortfolio.user_id == user.id).count()
        if count >= 5:
            await interaction.response.send_message("Limite de 5 jogadores!")
            return

        existing = s.query(UserPortfolio).filter(
            UserPortfolio.user_id == user.id, UserPortfolio.player_id == player.id
        ).first()
        if existing:
            await interaction.response.send_message(f"Voce ja tem {player.nickname}!")
            return

        if user.balance < market.current_price:
            await interaction.response.send_message(f"Saldo insuficiente ({user.balance:.2f} < {market.current_price:.2f})")
            return

        user.balance -= market.current_price
        s.add(UserPortfolio(user_id=user.id, player_id=player.id, buy_price=market.current_price))
        s.add(Transaction(user_id=user.id, player_id=player.id, type="buy", price=market.current_price))

        await interaction.response.send_message(
            f"Compra realizada! **{player.nickname}** por {market.current_price:.2f}. Saldo: {user.balance:.2f}"
        )


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
            await interaction.response.send_message(f"Jogador '{jogador}' nao encontrado")
            return

        item = s.query(UserPortfolio).filter(
            UserPortfolio.user_id == user.id, UserPortfolio.player_id == player.id
        ).first()
        if not item:
            await interaction.response.send_message(f"Voce nao tem {player.nickname}!")
            return

        market = s.query(PlayerMarket).get(player.id)
        sell_price = market.current_price if market else item.buy_price
        profit = sell_price - item.buy_price

        user.balance += sell_price
        s.delete(item)
        s.add(Transaction(user_id=user.id, player_id=player.id, type="sell", price=sell_price))

        emoji = "\U0001f4c8" if profit >= 0 else "\U0001f4c9"
        await interaction.response.send_message(
            f"Venda! **{player.nickname}** por {sell_price:.2f}. {emoji} Lucro: {profit:+.2f}. Saldo: {user.balance:.2f}"
        )


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
            await interaction.response.send_message("Nenhuma transacao ainda.")
            return

        embed = discord.Embed(title=f"Historico de {user.username}", color=0x1a1a2e)
        for tx in txs:
            player = s.query(Player).get(tx.player_id)
            emoji = "\U0001f7e2" if tx.type == "buy" else "\U0001f534"
            ts = tx.timestamp.strftime('%d/%m %H:%M') if tx.timestamp else ''
            embed.add_field(
                name=f"{emoji} {tx.type.upper()} {player.nickname if player else 'Unknown'}",
                value=f"{tx.price:.2f} — {ts}",
                inline=False,
            )
        await interaction.response.send_message(embed=embed)


# ============================================================================
# START
# ============================================================================

async def start_bot():
    if not DISCORD_TOKEN:
        print("DISCORD_BOT_TOKEN nao configurado, bot nao iniciado")
        return
    await bot.start(DISCORD_TOKEN)
