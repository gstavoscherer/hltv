"""
Database configuration and connection management.
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.pool import QueuePool
from contextlib import contextmanager
from .models import Base

# Database configuration
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': os.getenv('DB_PORT', '5432'),
    'database': os.getenv('DB_NAME', 'hltv_db'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', 'postgres'),
}

# SQLite for development (easier to start)
USE_SQLITE = os.getenv('USE_SQLITE', 'true').lower() == 'true'

if USE_SQLITE:
    # SQLite for development
    DATABASE_URL = f"sqlite:///hltv_data.db"
    ENGINE_ARGS = {
        'connect_args': {'check_same_thread': False},
        'echo': False,  # Set to True to see SQL queries
    }
else:
    # PostgreSQL for production
    DATABASE_URL = (
        f"postgresql://{DB_CONFIG['user']}:{DB_CONFIG['password']}"
        f"@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}"
    )
    ENGINE_ARGS = {
        'poolclass': QueuePool,
        'pool_size': 10,
        'max_overflow': 20,
        'pool_pre_ping': True,
        'echo': False,
    }

# Create engine
engine = create_engine(DATABASE_URL, **ENGINE_ARGS)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Thread-safe session
Session = scoped_session(SessionLocal)


def init_db():
    """Initialize database - create all tables"""
    print(f"🗄️  Inicializando banco de dados...")
    print(f"📍 URL: {DATABASE_URL.split('@')[-1] if '@' in DATABASE_URL else DATABASE_URL}")

    Base.metadata.create_all(bind=engine)

    print("✅ Tabelas criadas com sucesso!")
    print(f"📊 Tabelas: {', '.join(Base.metadata.tables.keys())}")


def drop_db():
    """Drop all tables - USE WITH CAUTION!"""
    print("⚠️  ATENÇÃO: Deletando todas as tabelas...")
    response = input("Tem certeza? Digite 'SIM' para confirmar: ")

    if response == "SIM":
        Base.metadata.drop_all(bind=engine)
        print("✅ Todas as tabelas foram deletadas.")
    else:
        print("❌ Operação cancelada.")


def get_db():
    """Get database session - for dependency injection"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_session():
    """Context manager for database session"""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()


def test_connection():
    """Test database connection"""
    try:
        from sqlalchemy import text
        with get_db_session() as session:
            session.execute(text("SELECT 1"))
        print("✅ Conexão com banco de dados OK!")
        return True
    except Exception as e:
        print(f"❌ Erro ao conectar no banco: {e}")
        return False


if __name__ == "__main__":
    # Test connection
    test_connection()

    # Initialize database
    init_db()
