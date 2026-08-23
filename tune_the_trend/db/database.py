import os
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from tune_the_trend.config import settings

# Base class for SQLAlchemy models using standard 2.0 DeclarativeBase
class Base(DeclarativeBase):
    pass

# Configure Engine
db_url = settings.DATABASE_URL
# Enable extra parameters for SQLite if needed (e.g. check_same_thread)
connect_args = {}
if db_url.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(db_url, connect_args=connect_args)

# Configure Session
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> None:
    """Initializes the database and creates all tables."""
    from tune_the_trend.db.models import DB_MODELS_IMPORTED  # Ensures models are imported before metadata creation
    Base.metadata.create_all(bind=engine)


def get_db():
    """Dependency for obtaining a database session in FastAPI or standalone scripts."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
