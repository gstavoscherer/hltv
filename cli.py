#!/usr/bin/env python3
"""HLTV Data Scraper CLI."""

import argparse
import logging
import traceback

from src.database import init_db, session_scope
from src.database.models import Event, Team, Player, EventTeam, TeamPlayer, EventStats
from src.scrapers.events import scrape_events, get_event_teams
from src.scrapers.teams import scrape_team
from src.scrapers.players import scrape_player, scrape_event_stats

logger = logging.getLogger(__name__)


def sync_events(limit=None, headless=True):
    """Sync events from HLTV."""
    print("\n" + "="*60)
    print("SINCRONIZANDO EVENTOS")
    print("="*60 + "\n")

    events_data = scrape_events(limit=limit, headless=headless)

    if not events_data:
        print("Nenhum evento encontrado")
        return

    saved_count = 0

    with session_scope() as session:
        for event_data in events_data:
            existing = session.query(Event).filter_by(id=event_data['id']).first()

            if existing:
                for key, value in event_data.items():
                    setattr(existing, key, value)
                print(f"  Atualizado: {event_data['name']}")
            else:
                event = Event(**event_data)
                session.add(event)
                print(f"  Novo: {event_data['name']}")
                saved_count += 1

    print(f"\nSincronizacao completa! {saved_count} novos eventos salvos.")


def sync_event_teams(event_id, headless=True):
    """Sync teams for a specific event."""
    print("\n" + "="*60)
    print(f"SINCRONIZANDO TIMES DO EVENTO {event_id}")
    print("="*60 + "\n")

    with session_scope() as session:
        event = session.query(Event).filter_by(id=event_id).first()
        if not event:
            print(f"Evento {event_id} nao encontrado no banco")
            return

        print(f"Evento: {event.name}\n")

        team_ids = get_event_teams(event_id, headless=headless)

        if not team_ids:
            print("Nenhum time encontrado no evento")
            return

        print(f"\nProcessando {len(team_ids)} times...\n")

        for idx, team_id in enumerate(team_ids, 1):
            print(f"[{idx}/{len(team_ids)}] Time {team_id}...")

            team_data = scrape_team(team_id, headless=headless)

            if not team_data:
                continue

            existing_team = session.query(Team).filter_by(id=team_id).first()

            if existing_team:
                for key, value in team_data['team'].items():
                    setattr(existing_team, key, value)
            else:
                team = Team(**team_data['team'])
                session.add(team)

            event_team = session.query(EventTeam).filter_by(
                event_id=event_id, team_id=team_id
            ).first()

            if not event_team:
                event_team = EventTeam(event_id=event_id, team_id=team_id)
                session.add(event_team)

            for player_data in team_data['roster']:
                player = session.query(Player).filter_by(id=player_data['player_id']).first()

                if not player:
                    player = Player(
                        id=player_data['player_id'],
                        nickname=player_data['nickname'],
                        current_team_id=team_id
                    )
                    session.add(player)

                team_player = session.query(TeamPlayer).filter_by(
                    team_id=team_id, player_id=player_data['player_id']
                ).first()

                if not team_player:
                    team_player = TeamPlayer(
                        team_id=team_id,
                        player_id=player_data['player_id'],
                        is_current=True
                    )
                    session.add(team_player)

        print(f"\nTimes sincronizados com sucesso!")


def sync_players(team_id=None, event_id=None, headless=True):
    """Sync player stats."""
    print("\n" + "="*60)
    print("SINCRONIZANDO JOGADORES")
    print("="*60 + "\n")

    with session_scope() as session:
        player_ids = []

        if team_id:
            players = session.query(Player).filter_by(current_team_id=team_id).all()
            player_ids = [p.id for p in players]
            print(f"Time {team_id}: {len(player_ids)} jogadores")

        elif event_id:
            event_teams = session.query(EventTeam).filter_by(event_id=event_id).all()

            for et in event_teams:
                team_players = session.query(TeamPlayer).filter_by(
                    team_id=et.team_id, is_current=True
                ).all()
                player_ids.extend([tp.player_id for tp in team_players])

            player_ids = list(set(player_ids))
            print(f"Evento {event_id}: {len(player_ids)} jogadores unicos")

        else:
            players = session.query(Player).all()
            player_ids = [p.id for p in players]
            print(f"Total de jogadores no banco: {len(player_ids)}")

        if not player_ids:
            print("Nenhum jogador encontrado")
            return

        print(f"\nProcessando {len(player_ids)} jogadores...\n")

        for idx, pid in enumerate(player_ids, 1):
            print(f"[{idx}/{len(player_ids)}] Jogador {pid}...")

            player_data = scrape_player(pid, headless=headless)

            if not player_data:
                continue

            player = session.query(Player).filter_by(id=pid).first()

            if player:
                for key, value in player_data.items():
                    setattr(player, key, value)

        if event_id:
            print(f"\nBuscando stats do evento {event_id}...\n")
            event_stats_data = scrape_event_stats(event_id, headless=headless)

            for stat_data in event_stats_data:
                existing_stat = session.query(EventStats).filter_by(
                    event_id=event_id, player_id=stat_data['player_id']
                ).first()

                if existing_stat:
                    for key, value in stat_data.items():
                        if key not in ['event_id', 'player_id']:
                            setattr(existing_stat, key, value)
                else:
                    event_stat = EventStats(**stat_data)
                    session.add(event_stat)

            print(f"Stats do evento salvos!")

        print(f"\nJogadores sincronizados com sucesso!")


def show_status():
    """Show database statistics."""
    print("\n" + "="*60)
    print("STATUS DO BANCO DE DADOS")
    print("="*60 + "\n")

    with session_scope() as session:
        events_count = session.query(Event).count()
        teams_count = session.query(Team).count()
        players_count = session.query(Player).count()
        event_stats_count = session.query(EventStats).count()

        print(f"Eventos: {events_count}")
        print(f"Times: {teams_count}")
        print(f"Jogadores: {players_count}")
        print(f"Event Stats: {event_stats_count}")

        if events_count > 0:
            print(f"\nUltimos 5 eventos:")
            recent_events = session.query(Event).order_by(Event.created_at.desc()).limit(5).all()

            for event in recent_events:
                teams_in_event = session.query(EventTeam).filter_by(event_id=event.id).count()
                print(f"  - {event.name} (ID: {event.id}) - {teams_in_event} times")

        print()


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(description="HLTV Data Scraper")

    subparsers = parser.add_subparsers(dest='command', help='Commands')

    subparsers.add_parser('init', help='Initialize database')

    events_parser = subparsers.add_parser('events', help='Sync events from HLTV')
    events_parser.add_argument('--limit', type=int, help='Limit number of events to scrape')
    events_parser.add_argument('--show', action='store_true', help='Show browser (not headless)')

    teams_parser = subparsers.add_parser('teams', help='Sync teams for an event')
    teams_parser.add_argument('event_id', type=int, help='Event ID')
    teams_parser.add_argument('--show', action='store_true', help='Show browser (not headless)')

    players_parser = subparsers.add_parser('players', help='Sync player stats')
    players_parser.add_argument('--team', type=int, help='Team ID to sync players from')
    players_parser.add_argument('--event', type=int, help='Event ID to sync players from')
    players_parser.add_argument('--show', action='store_true', help='Show browser (not headless)')

    subparsers.add_parser('status', help='Show database status')

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

    if args.command == 'init':
        print("Inicializando banco de dados...")
        init_db()
        print("Banco de dados inicializado!")

    elif args.command == 'events':
        sync_events(limit=args.limit, headless=not args.show)

    elif args.command == 'teams':
        sync_event_teams(args.event_id, headless=not args.show)

    elif args.command == 'players':
        sync_players(
            team_id=args.team,
            event_id=args.event,
            headless=not args.show
        )

    elif args.command == 'status':
        show_status()

    else:
        parser.print_help()


if __name__ == '__main__':
    main()
