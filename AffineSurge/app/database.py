from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.config import settings
from models.db_models import Base
from sqlalchemy import text

# sqlite connection URL. We set check_same_thread=False for sqlite multithreaded support.
engine = create_engine(
    settings.DATABASE_URL, 
    connect_args={"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    """Initializes and creates all database tables and handles migrations."""
    Base.metadata.create_all(bind=engine)
    
    # SQLite automatic migration check for existing tables
    from sqlalchemy import inspect
    inspector = inspect(engine)
    if "nodes" in inspector.get_table_names():
        columns = [col["name"] for col in inspector.get_columns("nodes")]
        new_cols = {
            "title": "VARCHAR",
            "section_number": "VARCHAR",
            "body_text": "TEXT",
            "tables": "TEXT",
            "lists": "TEXT",
            "figures": "TEXT"
        }
        with engine.begin() as conn:
            for col_name, col_type in new_cols.items():
                if col_name not in columns:
                    conn.execute(text(f"ALTER TABLE nodes ADD COLUMN {col_name} {col_type}")
)

def get_db():
    """FastAPI dependency to get db session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
