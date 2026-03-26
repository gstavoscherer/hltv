"""
Tasks do CartolaCS: atualizacao de precos pos-sync, decay, inicializacao.
"""

from cartola.pricing import (
    update_prices_for_match, apply_decay, initialize_market,
)
from src.database import session_scope
from src.database.models import Match
from datetime import datetime


def update_prices_after_sync(event_id):
    """Chamada apos sync de um evento. Atualiza precos de todas as partidas."""
    # Inicializa mercado pra jogadores novos
    initialize_market()

    with session_scope() as s:
        matches = (
            s.query(Match)
            .filter(Match.event_id == event_id)
            .order_by(Match.date.asc().nullslast())
            .all()
        )
        match_ids = [m.id for m in matches]

    print(f"  CartolaCS: atualizando precos pra {len(match_ids)} partidas...")
    for mid in match_ids:
        update_prices_for_match(mid)


def daily_maintenance():
    apply_decay()
    print(f"Manutencao diaria concluida: {datetime.utcnow().isoformat()}")


def weekly_maintenance():
    print(f"Manutencao semanal concluida: {datetime.utcnow().isoformat()}")
