"""
Service to import JSON data into the database.
Handles data transformation and relationships.
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from .models import (
    Event, Team, Player, EventStats,
    EventTeam, TeamPlayer
)
from . import get_db_session


class DataImporter:
    """Import scraped JSON data into database"""

    def __init__(self, session: Session = None):
        self.session = session
        self.teams_cache = {}  # Cache to avoid duplicate team lookups
        self.players_cache = {}

    def extract_team_id_from_url(self, url: str) -> Optional[int]:
        """Extract team ID from HLTV URL"""
        if not url:
            return None
        try:
            # URL format: /team/5973/liquid or /stats/teams/5973/liquid
            parts = url.split('/')
            for i, part in enumerate(parts):
                if part in ['team', 'teams'] and i + 1 < len(parts):
                    return int(parts[i + 1])
            return None
        except (ValueError, IndexError):
            return None

    def extract_player_id_from_url(self, url: str) -> Optional[int]:
        """Extract player ID from HLTV URL"""
        if not url:
            return None
        try:
            # URL format: /player/16848/hades or /stats/players/16848/hades
            parts = url.split('/')
            for i, part in enumerate(parts):
                if part in ['player', 'players'] and i + 1 < len(parts):
                    return int(parts[i + 1])
            return None
        except (ValueError, IndexError):
            return None

    def get_or_create_team(self, team_data: Dict, session: Session) -> Optional[Team]:
        """Get existing team or create new one"""
        if not team_data:
            return None

        # Extract team ID
        team_id = self.extract_team_id_from_url(
            team_data.get('url') or team_data.get('profileURL') or team_data.get('profile_url')
        )

        if not team_id:
            # Try to get from team_id field directly
            team_id = team_data.get('team_id') or team_data.get('id')

        if not team_id:
            print(f"  ⚠️  Não consegui extrair ID do time: {team_data}")
            return None

        # Check cache
        if team_id in self.teams_cache:
            return self.teams_cache[team_id]

        # Check database
        team = session.query(Team).filter(Team.id == team_id).first()

        if not team:
            # Create new team
            team = Team(
                id=team_id,
                name=team_data.get('name'),
                logo_url=team_data.get('logo') or team_data.get('logo_url'),
                profile_url=team_data.get('url') or team_data.get('profileURL') or team_data.get('profile_url'),
            )
            session.add(team)
            try:
                session.flush()
                print(f"  ✓ Novo time criado: {team.name} (ID: {team.id})")
            except IntegrityError:
                session.rollback()
                team = session.query(Team).filter(Team.id == team_id).first()

        # Cache it
        self.teams_cache[team_id] = team
        return team

    def get_or_create_player(self, player_data: Dict, session: Session) -> Optional[Player]:
        """Get existing player or create new one"""
        if not player_data:
            return None

        # Extract player ID
        player_id = self.extract_player_id_from_url(player_data.get('url') or player_data.get('link'))

        if not player_id:
            print(f"  ⚠️  Não consegui extrair ID do player: {player_data}")
            return None

        # Check cache
        if player_id in self.players_cache:
            return self.players_cache[player_id]

        # Check database
        player = session.query(Player).filter(Player.id == player_id).first()

        if not player:
            # Create new player
            player = Player(
                id=player_id,
                nickname=player_data.get('name'),
                profile_url=player_data.get('url') or player_data.get('link'),
                image_url=player_data.get('image'),
            )
            session.add(player)
            try:
                session.flush()
                print(f"  ✓ Novo player criado: {player.nickname} (ID: {player.id})")
            except IntegrityError:
                session.rollback()
                player = session.query(Player).filter(Player.id == player_id).first()

        # Cache it
        self.players_cache[player_id] = player
        return player

    def import_event(self, event_data: Dict, session: Session) -> Event:
        """Import event data"""
        event_id = event_data.get('event_id')

        print(f"\n📊 Importando evento {event_id}: {event_data.get('name')}")

        # Check if event already exists
        event = session.query(Event).filter(Event.id == event_id).first()

        overview = event_data.get('overview', {})

        # Parse event type - SIMPLIFIED (just store as string)
        event_type = overview.get('type') or 'Online'

        # Parse dates
        start_date = None
        end_date = None
        if overview.get('start_date'):
            try:
                start_date = datetime.strptime(overview['start_date'], '%Y-%m-%d').date()
            except:
                pass
        if overview.get('end_date'):
            try:
                end_date = datetime.strptime(overview['end_date'], '%Y-%m-%d').date()
            except:
                pass

        # Extract slug from link
        base_link = event_data.get('base_link', '')
        slug = base_link.split('/')[-1] if base_link else f"event-{event_id}"

        if event:
            # Update existing event
            print(f"  ⚠️  Evento {event_id} já existe, atualizando...")
            event.name = event_data.get('name')
            event.start_date = start_date
            event.end_date = end_date
            event.location = overview.get('location')
            event.event_type = event_type
            event.prize_pool = overview.get('prize_pool')
            event.updated_at = datetime.utcnow()
        else:
            # Create new event
            event = Event(
                id=event_id,
                name=event_data.get('name'),
                start_date=start_date,
                end_date=end_date,
                location=overview.get('location'),
                event_type=event_type,
                prize_pool=overview.get('prize_pool'),
            )
            session.add(event)
            print(f"  ✓ Evento criado: {event.name}")

        session.flush()

        # Import stats
        stats_data = event_data.get('stats', {})
        if stats_data:
            self.import_stats(stats_data, event, session)

        session.flush()
        return event


    def import_stats(self, stats_data: Dict, event: Event, session: Session):
        """Import event statistics (ONLY PLAYERS, not teams)"""
        # Import player stats ONLY
        top_players = stats_data.get('top_players', [])
        if top_players:
            print(f"  📈 Importando {len(top_players)} player stats...")
            for idx, player_data in enumerate(top_players, 1):
                player = self.get_or_create_player(player_data, session)
                if not player:
                    continue

                # Check if stats already exist
                stat = session.query(EventStats).filter(
                    EventStats.event_id == event.id,
                    EventStats.player_id == player.id
                ).first()

                # Parse rating
                rating = None
                if player_data.get('rating'):
                    try:
                        rating = float(player_data['rating'])
                    except:
                        pass

                # Parse maps
                maps_played = None
                if player_data.get('maps'):
                    try:
                        maps_played = int(player_data['maps'])
                    except:
                        pass

                if stat:
                    # Update
                    stat.rating = rating
                    stat.maps_played = maps_played
                    stat.rank = idx
                    stat.stats_json = player_data
                else:
                    # Create
                    stat = EventStats(
                        event_id=event.id,
                        player_id=player.id,
                        rating=rating,
                        maps_played=maps_played,
                        rank=idx,
                        stats_json=player_data,
                    )
                    session.add(stat)

        # NOTE: Team stats are NOT imported anymore - EventStats is ONLY for players
        # Teams can be found via event_teams relationship table

    def import_from_json_file(self, json_file: Path):
        """Import data from a JSON file"""
        print(f"\n{'='*80}")
        print(f"📁 Processando arquivo: {json_file.name}")
        print(f"{'='*80}")

        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            with get_db_session() as session:
                self.session = session
                event = self.import_event(data, session)
                session.commit()

                print(f"\n✅ Evento {event.id} importado com sucesso!")
                return event

        except Exception as e:
            print(f"\n❌ Erro ao importar {json_file.name}: {e}")
            import traceback
            traceback.print_exc()
            return None

    def import_all_json_files(self, directory: Path = None):
        """Import all JSON files from directory"""
        if directory is None:
            directory = Path("data/events")

        json_files = list(directory.glob("hltv_event_*_full.json"))

        if not json_files:
            print(f"❌ Nenhum arquivo JSON encontrado em {directory}")
            return

        print(f"\n🚀 Importando {len(json_files)} arquivos JSON...")
        print(f"📁 Diretório: {directory}")

        success = 0
        failed = 0

        for json_file in sorted(json_files):
            event = self.import_from_json_file(json_file)
            if event:
                success += 1
            else:
                failed += 1

        print(f"\n{'='*80}")
        print(f"🏁 IMPORTAÇÃO CONCLUÍDA")
        print(f"{'='*80}")
        print(f"✅ Sucesso: {success}/{len(json_files)} arquivos")
        print(f"❌ Falhas: {failed}/{len(json_files)} arquivos")
        print(f"{'='*80}\n")


if __name__ == "__main__":
    from . import init_db, test_connection

    # Test connection
    if not test_connection():
        exit(1)

    # Initialize database
    init_db()

    # Import data
    importer = DataImporter()
    importer.import_all_json_files()
