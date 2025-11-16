#!/usr/bin/env python3
"""HLTV Data Scraper CLI - Clean version."""

import argparse
from sqlalchemy.orm import Session
from src.database import init_db, get_session
from src.database.models import Event, Team, Player, EventTeam, TeamPlayer, EventStats
from src.scrapers.events import scrape_events, get_event_teams
from src.scrapers.teams import scrape_team
from src.scrapers.players import scrape_player, scrape_event_stats


def sync_events(limit=None, headless=True):
    """Sync events from HLTV."""
    print("\n" + "="*60)
    print("🎯 SINCRONIZANDO EVENTOS")
    print("="*60 + "\n")
    
    events_data = scrape_events(limit=limit, headless=headless)
    
    if not events_data:
        print("❌ Nenhum evento encontrado")
        return
    
    session = get_session()
    saved_count = 0
    
    try:
        for event_data in events_data:
            # Check if event already exists
            existing = session.query(Event).filter_by(id=event_data['id']).first()
            
            if existing:
                # Update existing event
                for key, value in event_data.items():
                    setattr(existing, key, value)
                print(f"♻️  Atualizado: {event_data['name']}")
            else:
                # Create new event
                event = Event(**event_data)
                session.add(event)
                print(f"➕ Novo: {event_data['name']}")
                saved_count += 1
        
        session.commit()
        print(f"\n✅ Sincronização completa! {saved_count} novos eventos salvos.")
        
    except Exception as e:
        session.rollback()
        print(f"\n❌ Erro ao salvar eventos: {e}")
    finally:
        session.close()


def sync_event_teams(event_id, headless=True):
    """Sync teams for a specific event."""
    print("\n" + "="*60)
    print(f"🎯 SINCRONIZANDO TIMES DO EVENTO {event_id}")
    print("="*60 + "\n")
    
    session = get_session()
    
    try:
        # Check if event exists
        event = session.query(Event).filter_by(id=event_id).first()
        if not event:
            print(f"❌ Evento {event_id} não encontrado no banco")
            return
        
        print(f"📋 Evento: {event.name}\n")
        
        # Get team IDs from event page
        team_ids = get_event_teams(event_id, headless=headless)
        
        if not team_ids:
            print("❌ Nenhum time encontrado no evento")
            return
        
        print(f"\n🔍 Processando {len(team_ids)} times...\n")
        
        for idx, team_id in enumerate(team_ids, 1):
            print(f"[{idx}/{len(team_ids)}] Time {team_id}...")
            
            # Scrape team data
            team_data = scrape_team(team_id, headless=headless)
            
            if not team_data:
                continue
            
            # Save/update team
            existing_team = session.query(Team).filter_by(id=team_id).first()
            
            if existing_team:
                for key, value in team_data['team'].items():
                    setattr(existing_team, key, value)
                team = existing_team
            else:
                team = Team(**team_data['team'])
                session.add(team)
            
            # Link team to event
            event_team = session.query(EventTeam).filter_by(
                event_id=event_id,
                team_id=team_id
            ).first()
            
            if not event_team:
                event_team = EventTeam(event_id=event_id, team_id=team_id)
                session.add(event_team)
            
            # Save roster
            for player_data in team_data['roster']:
                # Check if player exists
                player = session.query(Player).filter_by(id=player_data['player_id']).first()
                
                if not player:
                    # Create minimal player entry (will be enriched later)
                    player = Player(
                        id=player_data['player_id'],
                        nickname=player_data['nickname'],
                        current_team_id=team_id
                    )
                    session.add(player)
                
                # Link player to team
                team_player = session.query(TeamPlayer).filter_by(
                    team_id=team_id,
                    player_id=player_data['player_id']
                ).first()
                
                if not team_player:
                    team_player = TeamPlayer(
                        team_id=team_id,
                        player_id=player_data['player_id'],
                        is_current=True
                    )
                    session.add(team_player)
            
            session.commit()
        
        print(f"\n✅ Times sincronizados com sucesso!")
        
    except Exception as e:
        session.rollback()
        print(f"\n❌ Erro ao sincronizar times: {e}")
        import traceback
        traceback.print_exc()
    finally:
        session.close()


def sync_players(team_id=None, event_id=None, headless=True):
    """Sync player stats. If event_id provided, syncs event stats."""
    print("\n" + "="*60)
    print("🎯 SINCRONIZANDO JOGADORES")
    print("="*60 + "\n")
    
    session = get_session()
    player_ids = []
    
    try:
        if team_id:
            # Get players from specific team
            players = session.query(Player).filter_by(current_team_id=team_id).all()
            player_ids = [p.id for p in players]
            print(f"📋 Time {team_id}: {len(player_ids)} jogadores")
            
        elif event_id:
            # Get players from all teams in event
            event_teams = session.query(EventTeam).filter_by(event_id=event_id).all()
            
            for et in event_teams:
                team_players = session.query(TeamPlayer).filter_by(
                    team_id=et.team_id,
                    is_current=True
                ).all()
                player_ids.extend([tp.player_id for tp in team_players])
            
            player_ids = list(set(player_ids))  # Remove duplicates
            print(f"📋 Evento {event_id}: {len(player_ids)} jogadores únicos")
        
        else:
            # Get all players
            players = session.query(Player).all()
            player_ids = [p.id for p in players]
            print(f"📋 Total de jogadores no banco: {len(player_ids)}")
        
        if not player_ids:
            print("❌ Nenhum jogador encontrado")
            return
        
        print(f"\n🔍 Processando {len(player_ids)} jogadores...\n")
        
        for idx, player_id in enumerate(player_ids, 1):
            print(f"[{idx}/{len(player_ids)}] Jogador {player_id}...")
            
            player_data = scrape_player(player_id, headless=headless)
            
            if not player_data:
                continue
            
            # Update player
            player = session.query(Player).filter_by(id=player_id).first()
            
            if player:
                for key, value in player_data.items():
                    setattr(player, key, value)
            
            session.commit()
        
        # If event_id provided, also scrape event stats
        if event_id:
            print(f"\n🔍 Buscando stats do evento {event_id}...\n")
            event_stats_data = scrape_event_stats(event_id, headless=headless)
            
            for stat_data in event_stats_data:
                # Check if stat already exists
                existing_stat = session.query(EventStats).filter_by(
                    event_id=event_id,
                    player_id=stat_data['player_id']
                ).first()
                
                if existing_stat:
                    for key, value in stat_data.items():
                        if key not in ['event_id', 'player_id']:
                            setattr(existing_stat, key, value)
                else:
                    event_stat = EventStats(**stat_data)
                    session.add(event_stat)
            
            session.commit()
            print(f"✅ Stats do evento salvos!")
        
        print(f"\n✅ Jogadores sincronizados com sucesso!")
        
    except Exception as e:
        session.rollback()
        print(f"\n❌ Erro ao sincronizar jogadores: {e}")
        import traceback
        traceback.print_exc()
    finally:
        session.close()


def show_status():
    """Show database statistics."""
    print("\n" + "="*60)
    print("📊 STATUS DO BANCO DE DADOS")
    print("="*60 + "\n")
    
    session = get_session()
    
    try:
        events_count = session.query(Event).count()
        teams_count = session.query(Team).count()
        players_count = session.query(Player).count()
        event_stats_count = session.query(EventStats).count()
        
        print(f"📅 Eventos: {events_count}")
        print(f"👥 Times: {teams_count}")
        print(f"🎮 Jogadores: {players_count}")
        print(f"📈 Event Stats: {event_stats_count}")
        
        # Show recent events
        if events_count > 0:
            print(f"\n📋 Últimos 5 eventos:")
            recent_events = session.query(Event).order_by(Event.created_at.desc()).limit(5).all()
            
            for event in recent_events:
                teams_in_event = session.query(EventTeam).filter_by(event_id=event.id).count()
                print(f"  • {event.name} (ID: {event.id}) - {teams_in_event} times")
        
        print()
        
    except Exception as e:
        print(f"❌ Erro ao buscar status: {e}")
    finally:
        session.close()


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(description="HLTV Data Scraper - Clean Version")
    
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # Init database command
    init_parser = subparsers.add_parser('init', help='Initialize database')
    
    # Sync events command
    events_parser = subparsers.add_parser('events', help='Sync events from HLTV')
    events_parser.add_argument('--limit', type=int, help='Limit number of events to scrape')
    events_parser.add_argument('--show', action='store_true', help='Show browser (not headless)')
    
    # Sync teams command
    teams_parser = subparsers.add_parser('teams', help='Sync teams for an event')
    teams_parser.add_argument('event_id', type=int, help='Event ID')
    teams_parser.add_argument('--show', action='store_true', help='Show browser (not headless)')
    
    # Sync players command
    players_parser = subparsers.add_parser('players', help='Sync player stats')
    players_parser.add_argument('--team', type=int, help='Team ID to sync players from')
    players_parser.add_argument('--event', type=int, help='Event ID to sync players from')
    players_parser.add_argument('--show', action='store_true', help='Show browser (not headless)')
    
    # Status command
    status_parser = subparsers.add_parser('status', help='Show database status')
    
    args = parser.parse_args()
    
    if args.command == 'init':
        print("🔧 Inicializando banco de dados...")
        init_db()
        print("✅ Banco de dados inicializado!")
    
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
