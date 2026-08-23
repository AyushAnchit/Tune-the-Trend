from contextlib import asynccontextmanager
from typing import Any, Dict, List
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session

from tune_the_trend.config import log_structured
from tune_the_trend.db.database import init_db, SessionLocal, get_db
from tune_the_trend.db.models import DBScrapeRun, DBRecommendation
from tune_the_trend.db.repository import (
    sync_sources,
    get_enabled_sources,
    get_all_active_trends_with_music,
    get_music_for_trend,
    save_creator_profile,
    save_recommendations
)
from tune_the_trend.services.coordinator import run_pipeline
from tune_the_trend.services.recommendation import RecommendationEngine
from tune_the_trend.models import (
    CreatorProfile,
    Recommendation,
    TrendSignal,
    MusicEvidence,
    SourceMetadata
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handles startup DB initialization and defaults sync."""
    log_structured("API Startup: Initializing database and syncing sources")
    init_db()
    db = SessionLocal()
    try:
        sync_sources(db)
        
        # Auto-seed the database if empty on startup (disabled during test runs)
        import sys
        is_testing = "pytest" in sys.modules
        
        from tune_the_trend.db.models import DBTrendSignal
        count = db.query(DBTrendSignal).count()
        if count == 0 and not is_testing:
            log_structured("API Startup: Database is empty. Running initial ingestion to seed trend data...")
            run_pipeline(db)
            log_structured("API Startup: Seeding complete.")
    except Exception as e:
        log_structured("API Startup Error: Automatic seeding failed", {"error": str(e)}, level=40)
    finally:
        db.close()
    yield
    log_structured("API Shutdown: Lifespan complete")


app = FastAPI(
    title="Tune the Trend MVP API",
    description="Creator-facing Trend Intelligence and Music Recommendation API",
    version="0.1.0",
    lifespan=lifespan
)


@app.get("/health", tags=["Health"])
def health_check() -> Dict[str, str]:
    """Basic health check endpoint."""
    return {"status": "ok", "service": "tune_the_trend"}


@app.get("/sources", response_model=List[SourceMetadata], tags=["Sources"])
def list_sources(db: Session = Depends(get_db)):
    """Lists all sources registered in the system."""
    db_sources = get_enabled_sources(db)
    return [
        SourceMetadata(
            source_id=s.source_id,
            name=s.name,
            base_url=s.base_url,
            source_type=s.source_type,
            platform_focus=s.platform_focus,
            collector_id=s.collector_id,
            enabled=s.enabled,
            expected_freshness_hours=s.expected_freshness_hours
        ) for s in db_sources
    ]


@app.post("/ingest", tags=["Ingest"])
def trigger_ingest(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Triggers the ingest pipeline, which fetches fresh trend reports from
    configured Bright Data collectors, validates/structures the items,
    resolves music metadata, and stores them.
    """
    log_structured("API Request: POST /ingest triggered")
    try:
        sync_sources(db)
        stats = run_pipeline(db)
        return stats
    except Exception as e:
        log_structured(f"API Error: /ingest failed", {"error": str(e)}, level=50)
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")


@app.post("/ingestion/run", tags=["Ingest"])
def run_ingestion_path(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Trigger ingestion run (calls trigger_ingest)."""
    return trigger_ingest(db)


@app.get("/ingestion/runs", tags=["Ingest"])
def get_ingestion_runs(db: Session = Depends(get_db)) -> List[Dict[str, Any]]:
    """Retrieves all logged scrape/ingest runs."""
    db_runs = db.query(DBScrapeRun).all()
    results = []
    for r in db_runs:
        results.append({
            "id": r.id,
            "source_id": r.source_id,
            "scraped_at": r.scraped_at.isoformat() if r.scraped_at else None,
            "status": r.status,
            "records_scraped": r.records_scraped,
            "validation_failures": r.validation_failures,
            "duplicates_found": r.duplicates_found,
            "error_message": r.error_message,
            "created_at": r.created_at.isoformat() if r.created_at else None
        })
    return results


@app.get("/trends", tags=["Trends"])
def get_trends(db: Session = Depends(get_db)) -> List[Dict[str, Any]]:
    """Retrieves all stored trend signals with their resolved music evidence."""
    db_trends = get_all_active_trends_with_music(db)
    results = []
    
    for dt in db_trends:
        db_music = get_music_for_trend(db, dt.id)
        
        music_dict = None
        if db_music:
            music_dict = {
                "id": db_music.id,
                "audio_mentioned": db_music.audio_mentioned,
                "track_title": db_music.track_title,
                "artist": db_music.artist,
                "spotify_id": db_music.spotify_id,
                "spotify_url": db_music.spotify_url,
                "preview_url": db_music.preview_url,
                "genres": db_music.genres,
                "popularity": db_music.popularity,
                "energy": db_music.energy,
                "tempo": db_music.tempo,
                "valence": db_music.valence,
                "confidence_score": db_music.confidence_score
            }
            
        results.append({
            "trend_signal": {
                "id": dt.id,
                "source_id": dt.source_id,
                "article_url": dt.article_url,
                "trend_title": dt.trend_title,
                "normalized_title": dt.normalized_title,
                "trend_description": dt.trend_description,
                "platform": dt.platform,
                "content_format": dt.content_format,
                "niches": dt.niches,
                "keywords": dt.keywords,
                "moods": dt.moods,
                "styles": dt.styles,
                "scraped_at": dt.scraped_at.isoformat(),
                "freshness_status": dt.freshness_status,
                "interpreted_at": dt.interpreted_at.isoformat()
            },
            "music_evidence": music_dict
        })
        
    return results


@app.post("/recommend", response_model=List[Recommendation], tags=["Recommendation"])
def get_recommendations(profile: CreatorProfile, allow_broader: bool = True, db: Session = Depends(get_db)):
    """
    Submits a creator profile containing platform, niche, music style,
    and description. Generates, scores, and reranks candidate trends/songs,
    returning structured evidence-backed recommendations.
    Saves profiles and recommended results to database for audit history.
    """
    log_structured("API Request: POST /recommend triggered")
    try:
        # 1. Save creator profile to DB
        db_profile = save_creator_profile(db, profile)
        
        # 2. Run recommendation engine
        engine = RecommendationEngine(db)
        recs = engine.generate_recommendations(profile, allow_broader=allow_broader)
        
        if not recs:
            raise HTTPException(status_code=404, detail="Not enough evidence yet")
            
        # 3. Save recommendations for auditing
        save_recommendations(db, db_profile.id, recs)
        
        return recs
    except HTTPException:
        raise
    except Exception as e:
        log_structured(f"API Error: /recommend failed", {"error": str(e)}, level=50)
        raise HTTPException(status_code=500, detail=f"Recommendation failed: {str(e)}")


@app.get("/recommendations/{id}", tags=["Recommendation"])
def get_recommendations_by_profile(id: int, db: Session = Depends(get_db)):
    """Retrieves all saved recommendations for a given creator profile ID."""
    db_recs = db.query(DBRecommendation).filter(DBRecommendation.creator_profile_id == id).all()
    if not db_recs:
        raise HTTPException(status_code=404, detail=f"No recommendations found for profile ID {id}")
        
    results = []
    for r in db_recs:
        results.append({
            "id": r.id,
            "creator_profile_id": r.creator_profile_id,
            "trend_signal_id": r.trend_signal_id,
            "music_evidence_id": r.music_evidence_id,
            "final_score": r.final_score,
            "evidence_summary": r.evidence_summary,
            "rerank_reasons": r.rerank_reasons,
            "source": r.source,
            "source_url": r.source_url,
            "scraped_at": r.scraped_at.isoformat() if r.scraped_at else None
        })
    return results


@app.post("/admin/self-heal/{source_id}", tags=["Admin"])
def trigger_self_healing_manually(source_id: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Triggers manual diagnostic and self-healing workflow on a source collector
    for demonstration/hackathon purposes.
    """
    log_structured(f"API Request: POST /admin/self-heal/{source_id} triggered")
    from tune_the_trend.db.repository import get_enabled_sources
    db_sources = get_enabled_sources(db)
    source = next((s for s in db_sources if s.source_id == source_id), None)
    if not source:
        raise HTTPException(status_code=404, detail=f"Source {source_id} not found or disabled")
        
    from tune_the_trend.services.scraper import BrightDataClient, CollectorRunner, ScrapeHealthChecker, SelfHealingController
    
    client = BrightDataClient()
    runner = CollectorRunner(client)
    checker = ScrapeHealthChecker()
    checker.MIN_RECORDS = 1  # type: ignore
    controller = SelfHealingController(client, runner, checker)
    
    # Simulate a degraded run diagnostic for self-healing demo
    mock_records = [{"trend_title": None, "platform": "instagram"}]
    mock_coverages = {"trend_title": 0.0, "platform": 1.0}
    mock_reasons = ["Null values found in compulsory field trend_title"]
    
    from tune_the_trend.config import settings
    prev_min_rec = settings.MIN_RECORDS_THRESHOLD
    settings.MIN_RECORDS_THRESHOLD = 1
    
    try:
        success = controller.handle_repair(
            db_session=db,
            collector_id=source.collector_id,
            source_id=source.source_id,
            records=mock_records,
            reasons=mock_reasons,
            coverages=mock_coverages
        )
    finally:
        settings.MIN_RECORDS_THRESHOLD = prev_min_rec
    
    return {
        "source_id": source_id,
        "collector_id": source.collector_id,
        "self_healing_status": "repaired" if success else "failed",
        "details": {
            "reasons": mock_reasons,
            "coverages": mock_coverages
        }
    }
