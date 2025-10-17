#!/usr/bin/env python3
"""
Database management CLI tool.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database import init_db, drop_db, test_connection, get_db_session
from database.importer import DataImporter
from database.models import Event, Team, Player, EventStats, TeamPlayer


def show_stats():
    """Show database statistics"""
    print("\n📊 Estatísticas do Banco de Dados")
    print("="*50)

    with get_db_session() as session:
        num_events = session.query(Event).count()
        num_teams = session.query(Team).count()
        num_players = session.query(Player).count()
        num_stats = session.query(EventStats).count()

        print(f"🎯 Eventos: {num_events}")
        print(f"👥 Times: {num_teams}")
        print(f"🎮 Players: {num_players}")
        print(f"📈 Estatísticas: {num_stats}")

        # Players with stats
        players_with_stats = session.query(Player).filter(Player.rating_2_0 != None).count()
        print(f"\n📊 Players com stats: {players_with_stats}/{num_players}")

        # Teams with rosters
        teams_with_roster = session.query(Team).join(TeamPlayer).distinct().count()
        print(f"👥 Times com roster: {teams_with_roster}/{num_teams}")

        # Recent events
        print("\n📅 Últimos eventos:")
        recent_events = session.query(Event).order_by(Event.created_at.desc()).limit(5).all()
        for event in recent_events:
            print(f"  • {event.name} (ID: {event.id})")

    print("="*50)


def import_jsons():
    """Import JSON files into database"""
    importer = DataImporter()
    importer.import_all_json_files()


def clean_debug_files():
    """Clean debug HTML files"""
    import os

    print("\n🧹 Limpando arquivos de debug...")

    # Debug HTML files
    html_files = list(Path(".").glob("debug_*.html"))

    if not html_files:
        print("✅ Nenhum arquivo de debug encontrado.")
        return

    print(f"📁 Encontrados {len(html_files)} arquivos de debug")
    response = input("Deseja deletar todos? (s/N): ")

    if response.lower() == 's':
        for file in html_files:
            try:
                file.unlink()
                print(f"  ✓ Deletado: {file.name}")
            except Exception as e:
                print(f"  ✗ Erro ao deletar {file.name}: {e}")
        print(f"\n✅ {len(html_files)} arquivos deletados!")
    else:
        print("❌ Operação cancelada.")


def migrate_to_production():
    """Helper to migrate SQLite to PostgreSQL"""
    print("\n🔄 Migração SQLite → PostgreSQL")
    print("="*50)
    print("Para migrar para PostgreSQL:")
    print("\n1. Instale PostgreSQL")
    print("2. Crie o banco de dados:")
    print("   createdb hltv_db")
    print("\n3. Configure as variáveis de ambiente:")
    print("   export USE_SQLITE=false")
    print("   export DB_HOST=localhost")
    print("   export DB_PORT=5432")
    print("   export DB_NAME=hltv_db")
    print("   export DB_USER=seu_usuario")
    print("   export DB_PASSWORD=sua_senha")
    print("\n4. Execute:")
    print("   python manage_db.py init")
    print("   python manage_db.py import")
    print("="*50)


def main():
    if len(sys.argv) < 2:
        print("""
🗄️  HLTV Database Manager

Uso: python manage_db.py <comando>

Comandos disponíveis:
  init        - Inicializa o banco de dados (cria tabelas)
  drop        - Deleta todas as tabelas (CUIDADO!)
  test        - Testa a conexão com o banco
  import      - Importa dados dos arquivos JSON
  stats       - Mostra estatísticas do banco
  clean       - Limpa arquivos de debug HTML
  migrate     - Informações sobre migração para PostgreSQL

Exemplos:
  python manage_db.py init
  python manage_db.py import
  python manage_db.py stats
        """)
        return

    command = sys.argv[1].lower()

    if command == "init":
        if not test_connection():
            print("❌ Não foi possível conectar ao banco de dados.")
            return
        init_db()

    elif command == "drop":
        drop_db()

    elif command == "test":
        test_connection()

    elif command == "import":
        if not test_connection():
            print("❌ Não foi possível conectar ao banco de dados.")
            return
        import_jsons()

    elif command == "stats":
        if not test_connection():
            print("❌ Não foi possível conectar ao banco de dados.")
            return
        show_stats()

    elif command == "clean":
        clean_debug_files()

    elif command == "migrate":
        migrate_to_production()

    else:
        print(f"❌ Comando desconhecido: {command}")
        print("Use 'python manage_db.py' para ver os comandos disponíveis.")


if __name__ == "__main__":
    main()
