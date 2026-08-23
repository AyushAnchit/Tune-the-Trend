import os
import pytest
from sqlalchemy import create_engine

# Force DATABASE_URL to a file-based test database in environment variables before imports!
os.environ["DATABASE_URL"] = "sqlite:///test_run.db"
os.environ["LLM_PROVIDER"] = "mock"
os.environ["MUSIC_PROVIDER"] = "mock"
os.environ["DEMO_MODE"] = "True"

# Import database and repo elements after environment variables have been overridden
from tune_the_trend.db.database import Base, engine, SessionLocal, init_db
from tune_the_trend.db.repository import sync_sources


@pytest.fixture(scope="function")
def test_db():
    """Provides a fresh, clean SQLite database session for each test using test_run.db."""
    # Ensure tables are built
    init_db()
    
    db = SessionLocal()
    try:
        # Sync sources for the test run
        sync_sources(db)
        yield db
    finally:
        db.close()
        # Drop all tables to reset state for the next test
        try:
            Base.metadata.drop_all(bind=engine)
        except Exception:
            pass
        # Close all connection pool files
        engine.dispose()
        
        # Clean up database file if possible
        if os.path.exists("test_run.db"):
            try:
                os.remove("test_run.db")
            except Exception:
                pass


@pytest.fixture(scope="function")
def api_client(test_db):
    """Provides a FastAPI test client configured to use the clean test database."""
    from fastapi.testclient import TestClient
    from tune_the_trend.api.main import app
    from tune_the_trend.api.main import get_db

    # Override get_db to return sessions to the same test database
    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()
