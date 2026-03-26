"""Calculate recent form for players based on existing match data."""

import logging
from datetime import date, timedelta

from sqlalchemy import func as sqla_func

from src.database import session_scope, init_db
from src.database.models import (
    MatchPlayerStats, MatchMap, Match, PlayerMarket, PlayerFormSnapshot
)

logger = logging.getLogger(__name__)


def calculate_player_form(player_id, session, months=3):
    """Calculate a player's recent form from match stats in the last N months.

    Returns a dict with avg rating, adr, kast, kd_ratio, impact, maps_played,
    and the period_start/period_end dates. Returns None if no data found.
    """
    period_end = date.today()
    period_start = period_end - timedelta(days=months * 30)

    rows = (
        session.query(
            MatchPlayerStats.rating,
            MatchPlayerStats.adr,
            MatchPlayerStats.kast,
            MatchPlayerStats.kills,
            MatchPlayerStats.deaths,
            MatchPlayerStats.rating,  # used as impact proxy
        )
        .join(MatchMap, MatchPlayerStats.map_id == MatchMap.id)
        .join(Match, MatchMap.match_id == Match.id)
        .filter(
            MatchPlayerStats.player_id == player_id,
            Match.date >= period_start,
            Match.date <= period_end,
        )
        .all()
    )

    if not rows:
        return None

    maps_played = len(rows)
    total_rating = 0.0
    total_adr = 0.0
    total_kast = 0.0
    total_kills = 0
    total_deaths = 0
    total_impact = 0.0
    counted_rating = 0
    counted_adr = 0
    counted_kast = 0
    counted_impact = 0

    for row in rows:
        if row.rating is not None:
            total_rating += row.rating
            counted_rating += 1
            # Use rating as impact proxy (impact column may be sparse)
            total_impact += row.rating
            counted_impact += 1
        if row.adr is not None:
            total_adr += row.adr
            counted_adr += 1
        if row.kast is not None:
            total_kast += row.kast
            counted_kast += 1
        if row.kills is not None:
            total_kills += row.kills
        if row.deaths is not None:
            total_deaths += row.deaths

    avg_rating = total_rating / counted_rating if counted_rating else None
    avg_adr = total_adr / counted_adr if counted_adr else None
    avg_kast = total_kast / counted_kast if counted_kast else None
    avg_impact = total_impact / counted_impact if counted_impact else None
    kd_ratio = total_kills / total_deaths if total_deaths > 0 else None

    return {
        'player_id': player_id,
        'period_start': period_start,
        'period_end': period_end,
        'rating': round(avg_rating, 2) if avg_rating is not None else None,
        'impact': round(avg_impact, 2) if avg_impact is not None else None,
        'kast': round(avg_kast, 1) if avg_kast is not None else None,
        'adr': round(avg_adr, 1) if avg_adr is not None else None,
        'kd_ratio': round(kd_ratio, 2) if kd_ratio is not None else None,
        'maps_played': maps_played,
    }


def update_all_player_forms(months=3):
    """Calculate and upsert form snapshots for all priced players."""
    init_db()

    with session_scope() as session:
        player_ids = [
            row.player_id
            for row in session.query(PlayerMarket.player_id).all()
        ]

        if not player_ids:
            print("Nenhum jogador no PlayerMarket.")
            return

        print(f"Calculando form para {len(player_ids)} jogadores ({months} meses)...")

        updated = 0
        skipped = 0

        for idx, pid in enumerate(player_ids, 1):
            form = calculate_player_form(pid, session, months=months)

            if form is None:
                skipped += 1
                if idx % 20 == 0 or idx == len(player_ids):
                    print(f"  [{idx}/{len(player_ids)}] sem dados para player {pid}")
                continue

            existing = (
                session.query(PlayerFormSnapshot)
                .filter_by(
                    player_id=pid,
                    period_start=form['period_start'],
                    period_end=form['period_end'],
                )
                .first()
            )

            if existing:
                existing.rating = form['rating']
                existing.impact = form['impact']
                existing.kast = form['kast']
                existing.adr = form['adr']
                existing.kd_ratio = form['kd_ratio']
                existing.maps_played = form['maps_played']
            else:
                snapshot = PlayerFormSnapshot(
                    player_id=form['player_id'],
                    period_start=form['period_start'],
                    period_end=form['period_end'],
                    rating=form['rating'],
                    impact=form['impact'],
                    kast=form['kast'],
                    adr=form['adr'],
                    kd_ratio=form['kd_ratio'],
                    maps_played=form['maps_played'],
                )
                session.add(snapshot)

            updated += 1

            if idx % 20 == 0 or idx == len(player_ids):
                print(
                    f"  [{idx}/{len(player_ids)}] "
                    f"player {pid} | rating={form['rating']} | "
                    f"maps={form['maps_played']}"
                )

        print(f"\nForm atualizado: {updated} jogadores, {skipped} sem dados.")


if __name__ == '__main__':
    update_all_player_forms(months=3)
