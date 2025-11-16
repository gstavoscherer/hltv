#!/usr/bin/env python3
"""
Script completo de sincronização HLTV.
Coleta TODOS os dados: eventos, times, jogadores, stats, placements, prizes.
"""

import argparse
import time
from sqlalchemy.orm import Session
from src.database import init_db, get_session
from src.database.models import Event, Team, Player, EventTeam, TeamPlayer, EventStats
from src.scrapers.events import scrape_events, get_event_teams, get_event_results, get_event_details
from src.scrapers.teams import scrape_team
from src.scrapers.players import scrape_player


def sync_full_event(event_id, session, headless=True):
    """
    Sincroniza TODOS os dados de um evento:
    - Detalhes do evento (location, prize_pool)
    - Times participantes
    - Placements e prizes
    - Jogadores de cada time
    - Stats de todos os jogadores
    """
    print(f"\n{'='*70}")
    print(f"🎯 SINCRONIZANDO EVENTO {event_id} - MODO COMPLETO")
    print(f"{'='*70}\n")

    # 0. Buscar detalhes do evento (location, prize_pool)
    print("📍 Etapa 0/5: Buscando detalhes do evento...")
    event_details = get_event_details(event_id, headless=headless)

    # Atualizar evento com detalhes
    event = session.query(Event).filter_by(id=event_id).first()
    if event and event_details:
        if 'location' in event_details:
            event.location = event_details['location']
        if 'prize_pool' in event_details:
            event.prize_pool = event_details['prize_pool']
        session.commit()
        print(f"✅ Evento atualizado com detalhes\n")

    # 1. Buscar times do evento
    print("📋 Etapa 1/5: Buscando times do evento...")
    team_ids = get_event_teams(event_id, headless=headless)

    if not team_ids:
        print(f"❌ Nenhum time encontrado no evento {event_id}")
        return

    print(f"✅ Encontrados {len(team_ids)} times\n")

    # 2. Buscar placements e prizes
    print("🏆 Etapa 2/5: Buscando placements e prizes...")
    results = get_event_results(event_id, headless=headless)
    results_map = {r['team_id']: r for r in results}
    print(f"✅ {len(results)} times com placement/prize\n")

    # 3. Sincronizar cada time
    print("👥 Etapa 3/5: Sincronizando times e rosters...")
    all_player_ids = []

    for idx, team_id in enumerate(team_ids, 1):
        print(f"\n[Time {idx}/{len(team_ids)}] Processando time {team_id}...")

        # Scrape team data
        team_data = scrape_team(team_id, headless=headless)

        if not team_data:
            print(f"⚠️  Falha ao coletar time {team_id}")
            continue

        # Save/update team
        existing_team = session.query(Team).filter_by(id=team_id).first()

        if existing_team:
            for key, value in team_data['team'].items():
                setattr(existing_team, key, value)
        else:
            team = Team(**team_data['team'])
            session.add(team)

        # Link team to event with placement/prize
        event_team = session.query(EventTeam).filter_by(
            event_id=event_id,
            team_id=team_id
        ).first()

        if not event_team:
            event_team = EventTeam(event_id=event_id, team_id=team_id)
            session.add(event_team)

        # Add placement and prize if available
        if team_id in results_map:
            event_team.placement = results_map[team_id].get('placement')
            event_team.prize = results_map[team_id].get('prize')
            print(f"  📊 Placement: {event_team.placement}, Prize: {event_team.prize}")

        # Save roster
        for player_data in team_data['roster']:
            player_id = player_data['player_id']

            # Check if player exists
            player = session.query(Player).filter_by(id=player_id).first()

            if not player:
                # Create minimal player entry
                player = Player(
                    id=player_id,
                    nickname=player_data['nickname'],
                    current_team_id=team_id
                )
                session.add(player)

            # Link player to team
            team_player = session.query(TeamPlayer).filter_by(
                team_id=team_id,
                player_id=player_id
            ).first()

            if not team_player:
                team_player = TeamPlayer(
                    team_id=team_id,
                    player_id=player_id,
                    is_current=True
                )
                session.add(team_player)

            all_player_ids.append(player_id)

        session.commit()
        time.sleep(1)  # Rate limiting

    # 4. Sincronizar stats de todos os jogadores
    print(f"\n⚡ Etapa 4/5: Sincronizando stats de {len(set(all_player_ids))} jogadores únicos...")

    unique_player_ids = list(set(all_player_ids))

    for idx, player_id in enumerate(unique_player_ids, 1):
        print(f"[Player {idx}/{len(unique_player_ids)}] Coletando stats do jogador {player_id}...")

        player_stats = scrape_player(player_id, headless=headless)

        if not player_stats:
            print(f"⚠️  Falha ao coletar stats do jogador {player_id}")
            continue

        # Update player with full stats
        player = session.query(Player).filter_by(id=player_id).first()

        if player:
            for key, value in player_stats.items():
                if hasattr(player, key):
                    setattr(player, key, value)

        session.commit()
        time.sleep(2)  # Rate limiting between players

    print(f"\n{'='*70}")
    print(f"✅ EVENTO {event_id} SINCRONIZADO COM SUCESSO!")
    print(f"{'='*70}\n")


def sync_all_events(limit=None, headless=True):
    """
    Sincroniza TODOS OS EVENTOS e seus dados completos.
    """
    print("\n" + "="*70)
    print("🌐 INICIANDO SINCRONIZAÇÃO COMPLETA DE TODOS OS EVENTOS")
    print("="*70 + "\n")

    session = get_session()

    try:
        # 1. Buscar todos os eventos
        print("📋 Buscando lista de eventos...")
        events_data = scrape_events(limit=limit, headless=headless)

        if not events_data:
            print("❌ Nenhum evento encontrado")
            return

        print(f"✅ {len(events_data)} eventos encontrados\n")

        # 2. Salvar eventos no banco
        print("💾 Salvando eventos no banco...")
        saved_events = []

        for event_data in events_data:
            existing = session.query(Event).filter_by(id=event_data['id']).first()

            if existing:
                for key, value in event_data.items():
                    setattr(existing, key, value)
                saved_events.append(existing)
            else:
                event = Event(**event_data)
                session.add(event)
                saved_events.append(event)

        session.commit()
        print(f"✅ {len(saved_events)} eventos salvos\n")

        # 3. Sincronizar cada evento completamente
        for idx, event in enumerate(saved_events, 1):
            print(f"\n{'#'*70}")
            print(f"EVENTO {idx}/{len(saved_events)}: {event.name} (ID: {event.id})")
            print(f"{'#'*70}")

            try:
                sync_full_event(event.id, session, headless=headless)
            except Exception as e:
                print(f"\n❌ ERRO ao sincronizar evento {event.id}: {e}")
                import traceback
                traceback.print_exc()
                continue

            print(f"\n⏸️  Pausa de 5s antes do próximo evento...\n")
            time.sleep(5)

        print("\n" + "="*70)
        print("🎉 SINCRONIZAÇÃO COMPLETA FINALIZADA!")
        print("="*70)
        print(f"\nTotal de eventos processados: {len(saved_events)}")

    except Exception as e:
        session.rollback()
        print(f"\n❌ ERRO GERAL: {e}")
        import traceback
        traceback.print_exc()
    finally:
        session.close()


def main():
    """Main CLI."""
    parser = argparse.ArgumentParser(
        description="Sincronização completa de dados HLTV"
    )

    parser.add_argument(
        '--event',
        type=int,
        help='Sincronizar apenas um evento específico'
    )
    parser.add_argument(
        '--limit',
        type=int,
        help='Limite de eventos a processar (para teste)'
    )
    parser.add_argument(
        '--show',
        action='store_true',
        help='Mostrar navegador (não usar headless)'
    )
    parser.add_argument(
        '--init',
        action='store_true',
        help='Inicializar banco de dados antes de sync'
    )

    args = parser.parse_args()

    if args.init:
        print("🔧 Inicializando banco de dados...")
        init_db()
        print("✅ Banco inicializado!\n")

    headless = not args.show
    session = get_session()

    try:
        if args.event:
            # Sync apenas um evento
            sync_full_event(args.event, session, headless=headless)
        else:
            # Sync todos os eventos
            sync_all_events(limit=args.limit, headless=headless)
    finally:
        session.close()


if __name__ == '__main__':
    main()
