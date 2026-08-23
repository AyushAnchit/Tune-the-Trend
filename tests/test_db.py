from datetime import datetime
from tune_the_trend.db.models import DBSource, DBScrapeRun, DBRawArticle, DBTrendSignal, DBMusicEvidence
from tune_the_trend.db.repository import (
    sync_sources,
    get_enabled_sources,
    create_scrape_run,
    create_raw_articles,
    get_all_trend_keys,
    save_trend_and_music,
    get_music_for_trend
)
from tune_the_trend.models import TrendSignal, MusicEvidence


def test_sync_sources(test_db):
    # Default conftest fixture runs sync_sources. Let's verify sources exist
    sources = test_db.query(DBSource).all()
    assert len(sources) == 6
    
    source_ids = [s.source_id for s in sources]
    assert "later_instagram" in source_ids
    assert "hootsuite_social" in source_ids


def test_create_scrape_run(test_db):
    now = datetime.utcnow()
    run = create_scrape_run(
        db=test_db,
        source_id="later_instagram",
        status="success",
        scraped_at=now,
        records_scraped=5,
        validation_failures=0,
        duplicates_found=2
    )
    
    assert run.id is not None
    assert run.status == "success"
    assert run.records_scraped == 5
    
    # Query database directly to verify
    db_run = test_db.query(DBScrapeRun).filter(DBScrapeRun.id == run.id).first()
    assert db_run is not None
    assert db_run.duplicates_found == 2


def test_create_raw_articles(test_db):
    now = datetime.utcnow()
    run = create_scrape_run(
        db=test_db,
        source_id="later_instagram",
        status="running",
        scraped_at=now,
        records_scraped=0,
        validation_failures=0,
        duplicates_found=0
    )
    
    raw_payload_item = {
        "source_id": "later_instagram",
        "article_url": "https://later.com/blog/test",
        "article_title": "Test Title",
        "trend_title": "Espresso Dance",
        "published_at": "2026-08-20T12:00:00Z",
        "scraped_at": now.isoformat()
    }
    
    create_raw_articles(test_db, run.id, "later_instagram", [raw_payload_item])
    
    raw_arts = test_db.query(DBRawArticle).filter(DBRawArticle.scrape_run_id == run.id).all()
    assert len(raw_arts) == 1
    assert raw_arts[0].article_title == "Test Title"
    # Ensure JSON payload can be loaded
    assert raw_arts[0].raw_content["trend_title"] == "Espresso Dance"


def test_save_trend_and_music(test_db):
    now = datetime.utcnow()
    
    trend = TrendSignal(
        source_id="later_instagram",
        article_url="https://later.com/blog/trends",
        trend_title="Lofi Study Beats",
        normalized_title="lofi study beats",
        platform="instagram",
        niches=["study", "music"],
        scraped_at=now,
        freshness_status="fresh"
    )
    
    music = MusicEvidence(
        track_title="Chill Study Track",
        artist="Study Kid",
        spotify_id="spotify_id_123",
        genres=["lo-fi"],
        popularity=60,
        energy=0.2,
        tempo=70.0,
        valence=0.3
    )
    
    db_trend = save_trend_and_music(test_db, trend, music)
    assert db_trend.id is not None
    
    # Verify trend is in DB
    query_trend = test_db.query(DBTrendSignal).filter(DBTrendSignal.id == db_trend.id).first()
    assert query_trend is not None
    assert query_trend.trend_title == "Lofi Study Beats"
    assert "study" in query_trend.niches
    
    # Verify music is in DB and linked
    query_music = get_music_for_trend(test_db, db_trend.id)
    assert query_music is not None
    assert query_music.track_title == "Chill Study Track"
    assert query_music.spotify_id == "spotify_id_123"
    assert query_music.source == "later_instagram"
    
    # Verify deduplication key extraction
    keys = get_all_trend_keys(test_db)
    assert f"later_instagram:https://later.com/blog/trends:lofi study beats" in keys
