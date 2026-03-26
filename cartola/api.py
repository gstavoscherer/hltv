"""
API endpoints do CartolaCS.
"""

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func

from src.database import session_scope
from src.database.models import (
    Player, Team, PlayerMarket, PlayerPriceHistory, PlayerRole,
    User, UserPortfolio, Transaction, Match, TeamPlayer,
)
from cartola.auth import (
    hash_password, verify_password, create_token, get_current_user,
)
from cartola.analytics import get_h2h, get_roster_stability, get_ranking_trend
from src.scrapers.pistol_stats import get_team_pistol_stats

router = APIRouter(prefix="/api/cartola", tags=["cartola"])


# ============================================================================
# Schemas
# ============================================================================

class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


# ============================================================================
# AUTH
# ============================================================================

@router.post("/auth/register")
def register(req: RegisterRequest):
    with session_scope() as s:
        if s.query(User).filter(User.email == req.email).first():
            raise HTTPException(400, "Email ja cadastrado")
        if s.query(User).filter(User.username == req.username).first():
            raise HTTPException(400, "Username ja em uso")
        user = User(
            username=req.username,
            email=req.email,
            password_hash=hash_password(req.password),
        )
        s.add(user)
        s.flush()
        token = create_token(user.id, user.username)
    return {"token": token, "username": req.username}


@router.post("/auth/login")
def login(req: LoginRequest):
    with session_scope() as s:
        user = s.query(User).filter(User.email == req.email).first()
        if not user or not verify_password(req.password, user.password_hash):
            raise HTTPException(401, "Credenciais invalidas")
        token = create_token(user.id, user.username)
    return {"token": token, "username": user.username}


# ============================================================================
# MARKET
# ============================================================================

@router.get("/market")
def list_market(
    role: str = Query(None),
    sort_by: str = Query("current_price"),
    order: str = Query("desc"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    with session_scope() as s:
        q = (
            s.query(PlayerMarket, Player)
            .join(Player, PlayerMarket.player_id == Player.id)
        )

        if role:
            q = q.join(PlayerRole, PlayerRole.player_id == Player.id).filter(PlayerRole.role == role)

        sort_map = {
            "current_price": PlayerMarket.current_price,
            "price_change_pct": PlayerMarket.price_change_pct,
            "rating": Player.rating_2_0,
        }
        sort_col = sort_map.get(sort_by, PlayerMarket.current_price)
        if order == "asc":
            q = q.order_by(sort_col.asc().nullslast())
        else:
            q = q.order_by(sort_col.desc().nullslast())

        total = q.count()
        results = q.offset(offset).limit(limit).all()

        players = []
        for market, player in results:
            roles = s.query(PlayerRole).filter(PlayerRole.player_id == player.id).all()
            team = s.query(Team).get(player.current_team_id) if player.current_team_id else None
            players.append({
                "id": player.id,
                "nickname": player.nickname,
                "country": player.country,
                "team": {"id": team.id, "name": team.name} if team else None,
                "rating_2_0": player.rating_2_0,
                "roles": [{"role": r.role, "is_primary": r.is_primary} for r in roles],
                "current_price": market.current_price,
                "previous_price": market.previous_price,
                "price_change_pct": market.price_change_pct,
            })

        return {"total": total, "offset": offset, "limit": limit, "players": players}


@router.get("/market/{player_id}")
def get_market_player(player_id: int):
    with session_scope() as s:
        market = s.query(PlayerMarket).get(player_id)
        if not market:
            raise HTTPException(404, "Jogador nao encontrado no mercado")
        player = s.query(Player).get(player_id)
        team = s.query(Team).get(player.current_team_id) if player and player.current_team_id else None
        roles = s.query(PlayerRole).filter(PlayerRole.player_id == player_id).all()

        return {
            "id": player.id,
            "nickname": player.nickname,
            "real_name": player.real_name,
            "country": player.country,
            "age": player.age,
            "team": {"id": team.id, "name": team.name, "world_rank": team.world_rank} if team else None,
            "rating_2_0": player.rating_2_0,
            "kd_ratio": player.kd_ratio,
            "adr": player.adr,
            "kast": player.kast,
            "impact": player.impact,
            "roles": [{"role": r.role, "is_primary": r.is_primary} for r in roles],
            "current_price": market.current_price,
            "previous_price": market.previous_price,
            "price_change_pct": market.price_change_pct,
        }


@router.get("/market/{player_id}/history")
def get_price_history(player_id: int, days: int = Query(30, ge=1, le=365)):
    with session_scope() as s:
        cutoff = datetime.utcnow() - timedelta(days=days)
        history = (
            s.query(PlayerPriceHistory)
            .filter(PlayerPriceHistory.player_id == player_id, PlayerPriceHistory.timestamp >= cutoff)
            .order_by(PlayerPriceHistory.timestamp.asc())
            .all()
        )
        return [
            {"price": h.price, "timestamp": h.timestamp.isoformat(), "match_id": h.match_id}
            for h in history
        ]


# ============================================================================
# PORTFOLIO
# ============================================================================

@router.get("/portfolio")
def get_portfolio(user=Depends(get_current_user)):
    with session_scope() as s:
        u = s.query(User).get(user["sub"])
        if not u:
            raise HTTPException(404, "Usuario nao encontrado")
        items = s.query(UserPortfolio).filter(UserPortfolio.user_id == u.id).all()
        portfolio = []
        total_value = u.balance
        for item in items:
            market = s.query(PlayerMarket).get(item.player_id)
            player = s.query(Player).get(item.player_id)
            team = s.query(Team).get(player.current_team_id) if player and player.current_team_id else None
            current_price = market.current_price if market else item.buy_price
            total_value += current_price
            portfolio.append({
                "player_id": item.player_id,
                "nickname": player.nickname if player else None,
                "team": {"id": team.id, "name": team.name} if team else None,
                "buy_price": item.buy_price,
                "current_price": current_price,
                "profit": round(current_price - item.buy_price, 2),
                "bought_at": item.bought_at.isoformat() if item.bought_at else None,
            })
        return {
            "balance": u.balance,
            "total_value": round(total_value, 2),
            "profit": round(total_value - 100.0, 2),
            "players": portfolio,
        }


@router.post("/portfolio/buy/{player_id}")
def buy_player(player_id: int, user=Depends(get_current_user)):
    with session_scope() as s:
        u = s.query(User).get(user["sub"])
        if not u:
            raise HTTPException(404, "Usuario nao encontrado")

        count = s.query(UserPortfolio).filter(UserPortfolio.user_id == u.id).count()
        if count >= 5:
            raise HTTPException(400, "Limite de 5 jogadores atingido")

        existing = (
            s.query(UserPortfolio)
            .filter(UserPortfolio.user_id == u.id, UserPortfolio.player_id == player_id)
            .first()
        )
        if existing:
            raise HTTPException(400, "Voce ja tem esse jogador")

        market = s.query(PlayerMarket).get(player_id)
        if not market:
            raise HTTPException(404, "Jogador nao encontrado no mercado")

        if u.balance < market.current_price:
            raise HTTPException(400, f"Saldo insuficiente ({u.balance:.2f} < {market.current_price:.2f})")

        u.balance -= market.current_price
        s.add(UserPortfolio(
            user_id=u.id,
            player_id=player_id,
            buy_price=market.current_price,
        ))
        s.add(Transaction(
            user_id=u.id,
            player_id=player_id,
            type="buy",
            price=market.current_price,
        ))

        return {"message": "Compra realizada", "balance": round(u.balance, 2), "price": market.current_price}


@router.post("/portfolio/sell/{player_id}")
def sell_player(player_id: int, user=Depends(get_current_user)):
    with session_scope() as s:
        u = s.query(User).get(user["sub"])
        if not u:
            raise HTTPException(404, "Usuario nao encontrado")

        item = (
            s.query(UserPortfolio)
            .filter(UserPortfolio.user_id == u.id, UserPortfolio.player_id == player_id)
            .first()
        )
        if not item:
            raise HTTPException(404, "Jogador nao esta no seu time")

        market = s.query(PlayerMarket).get(player_id)
        sell_price = market.current_price if market else item.buy_price

        u.balance += sell_price
        s.delete(item)
        s.add(Transaction(
            user_id=u.id,
            player_id=player_id,
            type="sell",
            price=sell_price,
        ))

        return {
            "message": "Venda realizada",
            "balance": round(u.balance, 2),
            "price": sell_price,
            "profit": round(sell_price - item.buy_price, 2),
        }


# ============================================================================
# RANKINGS
# ============================================================================

def _calc_user_total(user, session):
    items = session.query(UserPortfolio).filter(UserPortfolio.user_id == user.id).all()
    total = user.balance
    for item in items:
        market = session.query(PlayerMarket).get(item.player_id)
        total += market.current_price if market else item.buy_price
    return total, len(items)


@router.get("/ranking")
def ranking_patrimony(limit: int = Query(20, ge=1, le=100)):
    with session_scope() as s:
        users = s.query(User).all()
        ranking = []
        for u in users:
            total, count = _calc_user_total(u, s)
            ranking.append({
                "user_id": u.id,
                "username": u.username,
                "total_value": round(total, 2),
                "balance": round(u.balance, 2),
                "players_count": count,
            })
        ranking.sort(key=lambda x: x["total_value"], reverse=True)
        return ranking[:limit]


@router.get("/ranking/profit")
def ranking_profit(limit: int = Query(20, ge=1, le=100)):
    with session_scope() as s:
        users = s.query(User).all()
        ranking = []
        for u in users:
            total, _ = _calc_user_total(u, s)
            profit = total - 100.0
            ranking.append({
                "user_id": u.id,
                "username": u.username,
                "profit": round(profit, 2),
                "profit_pct": round(profit, 2),
            })
        ranking.sort(key=lambda x: x["profit"], reverse=True)
        return ranking[:limit]


@router.get("/ranking/weekly")
def ranking_weekly(limit: int = Query(20, ge=1, le=100)):
    with session_scope() as s:
        week_start = datetime.utcnow() - timedelta(days=datetime.utcnow().weekday())
        week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)

        users = s.query(User).all()
        ranking = []
        for u in users:
            buys = (
                s.query(func.coalesce(func.sum(Transaction.price), 0))
                .filter(Transaction.user_id == u.id, Transaction.type == "buy", Transaction.timestamp >= week_start)
                .scalar()
            )
            sells = (
                s.query(func.coalesce(func.sum(Transaction.price), 0))
                .filter(Transaction.user_id == u.id, Transaction.type == "sell", Transaction.timestamp >= week_start)
                .scalar()
            )
            items = s.query(UserPortfolio).filter(UserPortfolio.user_id == u.id).all()
            valorization = 0
            for item in items:
                market = s.query(PlayerMarket).get(item.player_id)
                if not market:
                    continue
                if item.bought_at and item.bought_at >= week_start:
                    valorization += market.current_price - item.buy_price
                else:
                    hist = (
                        s.query(PlayerPriceHistory)
                        .filter(
                            PlayerPriceHistory.player_id == item.player_id,
                            PlayerPriceHistory.timestamp <= week_start,
                        )
                        .order_by(PlayerPriceHistory.timestamp.desc())
                        .first()
                    )
                    start_price = hist.price if hist else item.buy_price
                    valorization += market.current_price - start_price

            weekly_profit = sells - buys + valorization
            ranking.append({
                "user_id": u.id,
                "username": u.username,
                "weekly_profit": round(weekly_profit, 2),
            })
        ranking.sort(key=lambda x: x["weekly_profit"], reverse=True)
        return ranking[:limit]


# ============================================================================
# ANALYTICS
# ============================================================================

@router.get("/h2h/{team1_id}/{team2_id}")
def head_to_head(team1_id: int, team2_id: int):
    with session_scope() as s:
        team1 = s.query(Team).get(team1_id)
        team2 = s.query(Team).get(team2_id)
        if not team1:
            raise HTTPException(404, f"Time {team1_id} nao encontrado")
        if not team2:
            raise HTTPException(404, f"Time {team2_id} nao encontrado")

        stats = get_h2h(team1_id, team2_id, s)
        stats["team1"] = {"id": team1.id, "name": team1.name}
        stats["team2"] = {"id": team2.id, "name": team2.name}
        return stats


@router.get("/team/{team_id}/stability")
def roster_stability(team_id: int):
    with session_scope() as s:
        team = s.query(Team).get(team_id)
        if not team:
            raise HTTPException(404, f"Time {team_id} nao encontrado")

        stats = get_roster_stability(team_id, s)
        stats["team"] = {"id": team.id, "name": team.name}
        return stats


@router.get("/team/{team_id}/pistol-stats")
def pistol_stats(team_id: int):
    with session_scope() as s:
        team = s.query(Team).get(team_id)
        if not team:
            raise HTTPException(404, f"Time {team_id} nao encontrado")

        stats = get_team_pistol_stats(team_id, s)
        stats["team"] = {"id": team.id, "name": team.name}
        return stats


@router.get("/team/{team_id}/ranking-history")
def ranking_history(team_id: int, weeks: int = Query(8, ge=1, le=52)):
    with session_scope() as s:
        team = s.query(Team).get(team_id)
        if not team:
            raise HTTPException(404, f"Time {team_id} nao encontrado")

        data = get_ranking_trend(team_id, s, weeks=weeks)
        data["team"] = {"id": team.id, "name": team.name}
        return data
