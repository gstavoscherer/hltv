"""
Role classifier for CS2 players based on stats.

Classifies players into: awper, igl, entry, support, rifler.
Role is per team_player (same player can have different roles in different teams).
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.database import session_scope
from src.database.models import Player, TeamPlayer, PlayerRole


# Hybrid AWPers whose HS% is too high for automatic detection
KNOWN_AWPERS = {
    'ZywOo', 'm0NESY', 's1mple', 'w0nderful', 'broky', 'hallzerk',
}


def classify_role(player, is_igl=False, force_awper=False):
    """Classify a player's role based on their career stats."""
    if is_igl:
        return 'igl'
    if force_awper:
        return 'awper'

    hs = player.headshot_percentage or 50
    impact = player.impact or 1.0
    kpr = player.kpr or 0.67
    kast = player.kast or 70
    rating = player.rating_2_0 or 1.0

    # AWPer: low HS% (primary <36%, hybrid 36-42% with high rating)
    if hs < 36:
        return 'awper'
    if hs < 42 and rating > 1.10:
        return 'awper'

    # Entry: high impact + high KPR (aggressive fraggers)
    if impact > 1.15 and kpr > 0.72:
        return 'entry'

    # Support: high KAST but low impact
    if kast > 72 and impact < 1.0:
        return 'support'

    return 'rifler'


def update_all_roles():
    """Classify and update roles for all current team_players."""
    with session_scope() as s:
        igl_ids = set(
            r.player_id for r in s.query(PlayerRole).filter(PlayerRole.role == 'igl').all()
        )

        team_players = (
            s.query(TeamPlayer, Player)
            .join(Player, TeamPlayer.player_id == Player.id)
            .filter(TeamPlayer.is_current == True)
            .filter(Player.rating_2_0.isnot(None))
            .all()
        )

        counts = {}
        for tp, player in team_players:
            force_awp = player.nickname in KNOWN_AWPERS
            role = classify_role(player, is_igl=(player.id in igl_ids), force_awper=force_awp)
            tp.role = role
            counts[role] = counts.get(role, 0) + 1

        # Players without stats
        no_stats = (
            s.query(TeamPlayer)
            .join(Player, TeamPlayer.player_id == Player.id)
            .filter(TeamPlayer.is_current == True)
            .filter(Player.rating_2_0.is_(None))
            .all()
        )
        for tp in no_stats:
            if tp.player_id in igl_ids:
                tp.role = 'igl'
                counts['igl'] = counts.get('igl', 0) + 1
            else:
                tp.role = 'rifler'
                counts['rifler'] = counts.get('rifler', 0) + 1

        total = len(team_players) + len(no_stats)
        print(f'Roles classificadas para {total} jogadores:')
        for role, count in sorted(counts.items()):
            print(f'  {role}: {count}')

    return counts


if __name__ == '__main__':
    update_all_roles()
