#!/usr/bin/env python3
"""
Script completo de sincronizacao HLTV.
Coleta TODOS os dados: eventos, times, jogadores, stats, placements, prizes.
"""

import argparse
import logging
import os
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed

from src.database import init_db, get_session, session_scope
from src.database.models import Event, Team, Player, EventTeam, TeamPlayer, Match, MatchMap, MatchPlayerStats, MatchVeto
from src.scrapers.events import scrape_events, get_event_teams, get_event_results, get_event_details
from src.scrapers.teams import scrape_team
from src.scrapers.players import scrape_player
from src.scrapers.matches import scrape_event_matches, scrape_match_detail, scrape_map_stats
from src.scrapers.selenium_helpers import DriverPool, create_driver, random_delay

logger = logging.getLogger(__name__)

_DEFAULT_WORKERS = int(os.getenv("HLTV_WORKERS", "1"))


def _filter_players_needing_stats(session, player_ids, force=False):
    """Return player IDs that don't have stats yet. With force=True, return all."""
    if force or not player_ids:
        return player_ids
    players_without_stats = session.query(Player).filter(
        Player.id.in_(player_ids),
        Player.rating_2_0.is_(None)
    ).all()
    return [p.id for p in players_without_stats]


def sync_full_event(event_id, headless=True, team_workers=3, player_workers=3, force_players=False):
    """
    Sincroniza TODOS os dados de um evento.
    Each database operation uses its own session for thread safety.
    """
    print(f"\n{'='*70}")
    print(f"SINCRONIZANDO EVENTO {event_id} - MODO COMPLETO")
    print(f"{'='*70}\n")

    # Create a shared driver for event-level scraping (details, teams, results)
    event_driver = create_driver(headless=headless)
    try:
        # 0. Buscar detalhes do evento (location, prize_pool)
        print("Etapa 0/5: Buscando detalhes do evento...")
        event_details = get_event_details(event_id, headless=headless, driver=event_driver)
        random_delay(2.0, 4.0)

        # 1. Buscar times do evento
        print("Etapa 1/5: Buscando times do evento...")
        team_ids = get_event_teams(event_id, headless=headless, driver=event_driver)
        random_delay(2.0, 4.0)

        # 2. Buscar placements e prizes
        print("Etapa 2/5: Buscando placements e prizes...")
        results = get_event_results(event_id, headless=headless, driver=event_driver)
    finally:
        event_driver.quit()

    with session_scope() as session:
        event = session.query(Event).filter_by(id=event_id).first()
        if event and event_details:
            if 'location' in event_details:
                event.location = event_details['location']
            if 'prize_pool' in event_details:
                event.prize_pool = event_details['prize_pool']
            if 'start_date' in event_details:
                event.start_date = event_details['start_date']
            if 'end_date' in event_details:
                event.end_date = event_details['end_date']
    print("  Evento atualizado com detalhes\n")

    if not team_ids:
        print(f"  Nenhum time encontrado no evento {event_id}")
        return

    print(f"  Encontrados {len(team_ids)} times\n")
    results_map = {r['team_id']: r for r in results}
    print(f"  {len(results)} times com placement/prize\n")

    # 3. Sincronizar cada time (scraping em paralelo, DB no main thread)
    print("Etapa 3/5: Sincronizando times e rosters...")
    all_player_ids = []

    team_workers = max(1, int(team_workers))
    scraped_teams = {}

    def _scrape_team_pooled(pool, tid):
        driver = pool.checkout()
        for attempt in range(3):
            try:
                result = scrape_team(tid, headless=headless, max_retries=1, driver=driver)
                pool.checkin(driver)
                return result
            except Exception as e:
                logger.warning("Pool team %d attempt %d: %s", tid, attempt + 1, e)
                if attempt < 2:
                    time.sleep(2 * (attempt + 1))
                    # Try to revive driver with a simple navigation
                    try:
                        driver.get("https://www.hltv.org")
                        time.sleep(2)
                    except Exception:
                        # Driver is truly dead, replace it
                        pool.mark_bad(driver)
                        pool.checkin(driver)
                        driver = pool.checkout()
        pool.checkin(driver)
        return None

    with DriverPool(size=team_workers, headless=headless) as pool:
        with ThreadPoolExecutor(max_workers=team_workers) as executor:
            futures = {executor.submit(_scrape_team_pooled, pool, tid): tid for tid in team_ids}

            for future in as_completed(futures):
                tid = futures[future]
                try:
                    team_data = future.result()
                    if team_data:
                        scraped_teams[tid] = team_data
                except Exception as e:
                    logger.warning("Falha ao coletar time %d: %s", tid, e)

    # Save all team data in a single session (thread-safe)
    with session_scope() as session:
        for idx, (tid, team_data) in enumerate(scraped_teams.items(), 1):
            print(f"  [Time {idx}/{len(scraped_teams)}] Salvando time {tid}...")

            existing_team = session.query(Team).filter_by(id=tid).first()
            if existing_team:
                for key, value in team_data['team'].items():
                    setattr(existing_team, key, value)
            else:
                team = Team(**team_data['team'])
                session.add(team)

            event_team = session.query(EventTeam).filter_by(
                event_id=event_id, team_id=tid
            ).first()

            if not event_team:
                event_team = EventTeam(event_id=event_id, team_id=tid)
                session.add(event_team)

            if tid in results_map:
                event_team.placement = results_map[tid].get('placement')
                event_team.prize = results_map[tid].get('prize')

            for player_data in team_data['roster']:
                player_id = player_data['player_id']

                player = session.query(Player).filter_by(id=player_id).first()
                if not player:
                    player = Player(
                        id=player_id,
                        nickname=player_data['nickname'],
                        current_team_id=tid
                    )
                    session.add(player)

                team_player = session.query(TeamPlayer).filter_by(
                    team_id=tid, player_id=player_id
                ).first()

                if not team_player:
                    team_player = TeamPlayer(
                        team_id=tid,
                        player_id=player_id,
                        is_current=True
                    )
                    session.add(team_player)

                all_player_ids.append(player_id)

    # 4. Sincronizar stats de todos os jogadores
    unique_player_ids = list(set(all_player_ids))

    # Filter out players that already have stats
    with session_scope() as session:
        needed_ids = _filter_players_needing_stats(session, unique_player_ids, force=force_players)
    skipped = len(unique_player_ids) - len(needed_ids)
    if skipped:
        print(f"  Pulando {skipped} jogadores que ja tem stats")
    print(f"\nEtapa 4/5: Sincronizando stats de {len(needed_ids)} jogadores...")

    player_workers = max(1, int(player_workers))
    scraped_players = {}

    def _scrape_player_pooled(pool, pid):
        driver = pool.checkout()
        for attempt in range(3):
            try:
                result = scrape_player(pid, headless=headless, max_retries=1, driver=driver)
                pool.checkin(driver)
                return result
            except Exception as e:
                logger.warning("Pool player %d attempt %d: %s", pid, attempt + 1, e)
                if attempt < 2:
                    time.sleep(2 * (attempt + 1))
                    try:
                        driver.get("https://www.hltv.org")
                        time.sleep(2)
                    except Exception:
                        pool.mark_bad(driver)
                        pool.checkin(driver)
                        driver = pool.checkout()
        pool.checkin(driver)
        return None

    if not needed_ids:
        print("  Todos os jogadores ja tem stats. Use --force-players para re-coletar.")
    else:
        with DriverPool(size=player_workers, headless=headless) as pool:
            with ThreadPoolExecutor(max_workers=player_workers) as executor:
                futures = {executor.submit(_scrape_player_pooled, pool, pid): pid for pid in needed_ids}

                for future in as_completed(futures):
                    pid = futures[future]
                    try:
                        player_stats = future.result()
                        if player_stats:
                            scraped_players[pid] = player_stats
                    except Exception as e:
                        logger.warning("Falha ao coletar stats do jogador %d: %s", pid, e)

        # Save all player stats in a single session
        with session_scope() as session:
            for pid, player_stats in scraped_players.items():
                player = session.query(Player).filter_by(id=pid).first()
                if player:
                    for key, value in player_stats.items():
                        if hasattr(player, key):
                            setattr(player, key, value)

    # 5. Sincronizar matches, mapas e stats por mapa
    print(f"\nEtapa 5/5: Sincronizando matches do evento...")

    match_driver = create_driver(headless=headless)
    try:
        match_list = scrape_event_matches(event_id, headless=headless, driver=match_driver)
    except Exception as e:
        logger.error("Erro ao buscar matches: %s", e)
        match_list = []
    finally:
        match_driver.quit()

    if not match_list:
        print("  Nenhum match encontrado")
        print(f"\n{'='*70}")
        print(f"EVENTO {event_id} SINCRONIZADO COM SUCESSO!")
        print(f"{'='*70}\n")
        return

    # Filter out matches already in DB
    with session_scope() as session:
        existing_match_ids = {m.id for m in session.query(Match.id).filter(
            Match.event_id == event_id
        ).all()}
    new_matches = [m for m in match_list if m['id'] not in existing_match_ids]
    if len(match_list) - len(new_matches) > 0:
        print(f"  Pulando {len(match_list) - len(new_matches)} matches ja no banco")
    print(f"  {len(new_matches)} matches novos para processar")

    if not new_matches:
        print(f"\n{'='*70}")
        print(f"EVENTO {event_id} SINCRONIZADO COM SUCESSO!")
        print(f"{'='*70}\n")
        return

    # Resolve team names to IDs for matches missing team_id
    with session_scope() as session:
        for m in new_matches:
            if not m.get('team1_id') and m.get('team1_name'):
                team = session.query(Team).filter(Team.name == m['team1_name']).first()
                if team:
                    m['team1_id'] = team.id
            if not m.get('team2_id') and m.get('team2_name'):
                team = session.query(Team).filter(Team.name == m['team2_name']).first()
                if team:
                    m['team2_id'] = team.id
            # Re-resolve winner
            if m.get('team1_id') and m.get('team2_id') and m.get('score1') is not None and m.get('score2') is not None:
                if m['score1'] > m['score2']:
                    m['winner_id'] = m['team1_id']
                elif m['score2'] > m['score1']:
                    m['winner_id'] = m['team2_id']

    with session_scope() as session:
        for m in new_matches:
            match = Match(
                id=m['id'], event_id=event_id,
                team1_id=m.get('team1_id'), team2_id=m.get('team2_id'),
                score1=m.get('score1'), score2=m.get('score2'),
                best_of=m.get('best_of'), date=m.get('date'),
                winner_id=m.get('winner_id'), stars=m.get('stars'),
            )
            session.merge(match)

    # Scrape each match detail + map stats
    match_driver = create_driver(headless=headless)
    try:
        for idx, m in enumerate(new_matches, 1):
            mid = m['id']
            print(f"  [{idx}/{len(new_matches)}] Match {mid}...")

            detail = scrape_match_detail(mid, headless=headless, driver=match_driver)
            if not detail:
                continue
            random_delay(0.5, 1.5)

            # Save vetos
            with session_scope() as session:
                for v in detail.get('vetos', []):
                    veto_team_id = None
                    if v.get('team_name'):
                        team = session.query(Team).filter(
                            Team.name.ilike(f"%{v['team_name']}%")
                        ).first()
                        if team:
                            veto_team_id = team.id

                    existing = session.query(MatchVeto).filter_by(
                        match_id=mid, veto_number=v['veto_number']
                    ).first()
                    if not existing:
                        session.add(MatchVeto(
                            match_id=mid,
                            veto_number=v['veto_number'],
                            team_id=veto_team_id,
                            action=v['action'],
                            map_name=v['map_name'],
                        ))

            # Save maps and scrape map stats
            for map_data in detail.get('maps', []):
                mapstats_id = map_data.get('mapstats_id')
                if not mapstats_id:
                    continue

                with session_scope() as session:
                    existing_map = session.query(MatchMap).filter_by(id=mapstats_id).first()
                    if existing_map:
                        continue  # Already have this map's data

                    mm = MatchMap(
                        id=mapstats_id,
                        match_id=mid,
                        map_name=map_data.get('map_name', 'Unknown'),
                        map_number=map_data.get('map_number', 0),
                        team1_score=map_data.get('team1_score'),
                        team2_score=map_data.get('team2_score'),
                        team1_ct_score=map_data.get('team1_ct_score'),
                        team1_t_score=map_data.get('team1_t_score'),
                        team2_ct_score=map_data.get('team2_ct_score'),
                        team2_t_score=map_data.get('team2_t_score'),
                        picked_by=map_data.get('picked_by'),
                        winner_id=map_data.get('winner_id'),
                    )
                    session.add(mm)

                # Scrape map player stats
                random_delay(0.5, 1.5)
                player_stats = scrape_map_stats(mapstats_id, headless=headless, driver=match_driver)

                if player_stats:
                    with session_scope() as session:
                        for ps in player_stats:
                            existing = session.query(MatchPlayerStats).filter_by(
                                map_id=mapstats_id, player_id=ps['player_id']
                            ).first()
                            if not existing:
                                session.add(MatchPlayerStats(
                                    map_id=mapstats_id,
                                    player_id=ps['player_id'],
                                    team_id=ps.get('team_id'),
                                    kills=ps.get('kills'),
                                    deaths=ps.get('deaths'),
                                    assists=ps.get('assists'),
                                    headshots=ps.get('headshots'),
                                    flash_assists=ps.get('flash_assists'),
                                    adr=ps.get('adr'),
                                    kast=ps.get('kast'),
                                    rating=ps.get('rating'),
                                    opening_kills=ps.get('opening_kills'),
                                    opening_deaths=ps.get('opening_deaths'),
                                    multi_kill_rounds=ps.get('multi_kill_rounds'),
                                    clutches_won=ps.get('clutches_won'),
                                ))
    finally:
        match_driver.quit()

    # Atualizar precos do CartolaCS
    try:
        from cartola.tasks import update_prices_after_sync
        update_prices_after_sync(event_id)
    except ImportError:
        pass
    except Exception as e:
        logger.warning("Erro ao atualizar precos CartolaCS: %s", e)

    print(f"\n{'='*70}")
    print(f"EVENTO {event_id} SINCRONIZADO COM SUCESSO!")
    print(f"{'='*70}\n")


def retry_failed_players(event_id=None, headless=True, player_workers=1):
    """Retry scraping only players that have no stats (rating_2_0 IS NULL)."""
    print(f"\n{'='*70}")
    print("RETRY: Coletando jogadores sem stats")
    print(f"{'='*70}\n")

    with session_scope() as session:
        query = session.query(Player).filter(Player.rating_2_0.is_(None))
        if event_id:
            # Filter to players from this event's teams
            player_ids_in_event = (
                session.query(TeamPlayer.player_id)
                .join(EventTeam, EventTeam.team_id == TeamPlayer.team_id)
                .filter(EventTeam.event_id == event_id)
                .distinct()
            )
            query = query.filter(Player.id.in_(player_ids_in_event))
        players = query.all()
        needed_ids = [p.id for p in players]

    if not needed_ids:
        print("  Todos os jogadores ja tem stats!")
        return

    print(f"  {len(needed_ids)} jogadores sem stats para coletar\n")

    player_workers = max(1, int(player_workers))
    scraped_players = {}

    def _scrape_player_pooled(pool, pid):
        driver = pool.checkout()
        for attempt in range(3):
            try:
                result = scrape_player(pid, headless=headless, max_retries=1, driver=driver)
                pool.checkin(driver)
                return result
            except Exception as e:
                logger.warning("Retry player %d attempt %d: %s", pid, attempt + 1, e)
                if attempt < 2:
                    time.sleep(2 * (attempt + 1))
                    try:
                        driver.get("https://www.hltv.org")
                        time.sleep(2)
                    except Exception:
                        pool.mark_bad(driver)
                        pool.checkin(driver)
                        driver = pool.checkout()
        pool.checkin(driver)
        return None

    with DriverPool(size=player_workers, headless=headless) as pool:
        with ThreadPoolExecutor(max_workers=player_workers) as executor:
            futures = {executor.submit(_scrape_player_pooled, pool, pid): pid for pid in needed_ids}

            for future in as_completed(futures):
                pid = futures[future]
                try:
                    player_stats = future.result()
                    if player_stats:
                        scraped_players[pid] = player_stats
                except Exception as e:
                    logger.warning("Falha ao coletar stats do jogador %d: %s", pid, e)

    with session_scope() as session:
        for pid, player_stats in scraped_players.items():
            player = session.query(Player).filter_by(id=pid).first()
            if player:
                for key, value in player_stats.items():
                    if hasattr(player, key):
                        setattr(player, key, value)

    failed = len(needed_ids) - len(scraped_players)
    print(f"\n{'='*70}")
    print(f"RETRY COMPLETO: {len(scraped_players)}/{len(needed_ids)} coletados")
    if failed:
        print(f"  {failed} ainda falharam")
    print(f"{'='*70}\n")


def sync_all_events(limit=None, headless=True, team_workers=3, player_workers=3):
    """Sincroniza TODOS OS EVENTOS e seus dados completos."""
    print("\n" + "="*70)
    print("INICIANDO SINCRONIZACAO COMPLETA DE TODOS OS EVENTOS")
    print("="*70 + "\n")

    # 1. Buscar todos os eventos
    print("Buscando lista de eventos...")
    events_data = scrape_events(limit=limit, headless=headless)

    if not events_data:
        print("Nenhum evento encontrado")
        return

    print(f"  {len(events_data)} eventos encontrados\n")

    # 2. Salvar eventos no banco
    print("Salvando eventos no banco...")
    saved_event_ids = []

    with session_scope() as session:
        for event_data in events_data:
            existing = session.query(Event).filter_by(id=event_data['id']).first()

            if existing:
                for key, value in event_data.items():
                    setattr(existing, key, value)
            else:
                event = Event(**event_data)
                session.add(event)

            saved_event_ids.append(event_data['id'])

    print(f"  {len(saved_event_ids)} eventos salvos\n")

    # 3. Sincronizar cada evento completamente
    for idx, event_id in enumerate(saved_event_ids, 1):
        # Re-fetch event name for display
        with session_scope() as session:
            event = session.query(Event).filter_by(id=event_id).first()
            event_name = event.name if event else "Unknown"

        print(f"\n{'#'*70}")
        print(f"EVENTO {idx}/{len(saved_event_ids)}: {event_name} (ID: {event_id})")
        print(f"{'#'*70}")

        try:
            sync_full_event(
                event_id, headless=headless,
                team_workers=team_workers, player_workers=player_workers
            )
        except Exception as e:
            logger.error("ERRO ao sincronizar evento %d: %s", event_id, e)
            traceback.print_exc()
            continue

        print(f"\nPausa de 5s antes do proximo evento...\n")
        time.sleep(5)

    print("\n" + "="*70)
    print("SINCRONIZACAO COMPLETA FINALIZADA!")
    print("="*70)
    print(f"\nTotal de eventos processados: {len(saved_event_ids)}")


def main():
    """Main CLI."""
    parser = argparse.ArgumentParser(
        description="Sincronizacao completa de dados HLTV"
    )

    parser.add_argument('--event', type=int, help='Sincronizar apenas um evento especifico')
    parser.add_argument('--limit', type=int, help='Limite de eventos a processar (para teste)')
    parser.add_argument('--show', action='store_true', help='Mostrar navegador (nao usar headless)')
    parser.add_argument(
        '--workers', type=int, default=_DEFAULT_WORKERS,
        help=f'Numero de threads para scraping concorrente (default: {_DEFAULT_WORKERS})'
    )
    parser.add_argument('--team-workers', type=int, help='Override threads para times')
    parser.add_argument('--player-workers', type=int, help='Override threads para jogadores')
    parser.add_argument('--init', action='store_true', help='Inicializar banco de dados antes de sync')
    parser.add_argument('--force-players', action='store_true',
                        help='Re-scrape players even if they already have stats')
    parser.add_argument('--retry-players', action='store_true',
                        help='Only retry players without stats (skip event/team scraping)')

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

    if args.init:
        print("Inicializando banco de dados...")
        init_db()
        print("Banco inicializado!\n")

    headless = not args.show
    team_workers = args.team_workers or args.workers
    player_workers = args.player_workers or args.workers

    if args.retry_players:
        retry_failed_players(
            event_id=args.event, headless=headless,
            player_workers=player_workers
        )
    elif args.event:
        # Ensure event record exists in DB before syncing
        with session_scope() as session:
            from src.database.models import Event
            if not session.query(Event).filter_by(id=args.event).first():
                session.add(Event(id=args.event, name=f"Event {args.event}"))

        sync_full_event(
            args.event, headless=headless,
            team_workers=team_workers, player_workers=player_workers,
            force_players=args.force_players
        )
    else:
        sync_all_events(
            limit=args.limit, headless=headless,
            team_workers=team_workers, player_workers=player_workers
        )


if __name__ == '__main__':
    main()
