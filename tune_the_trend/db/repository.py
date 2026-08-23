from datetime import datetime
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session
from tune_the_trend.config import DEFAULT_SOURCES, log_structured
from tune_the_trend.db.models import (
    DBSource,
    DBScrapeRun,
    DBRawArticle,
    DBTrendSignal,
    DBMusicEvidence,
    DBCreatorProfile,
    DBRecommendation,
    DBCollectorHealthCheck,
    DBSelfHealingRun
)
from tune_the_trend.models import TrendSignal, MusicEvidence, CreatorProfile, Recommendation


def sync_sources(db: Session) -> None:
    """
    Syncs default sources from config to the database.
    Inserts missing sources and updates existing ones.
    """
    for src in DEFAULT_SOURCES:
        db_src = db.query(DBSource).filter(DBSource.source_id == src["source_id"]).first()
        if db_src:
            db_src.name = src["name"]
            db_src.base_url = src["base_url"]
            db_src.source_type = src["source_type"]
            db_src.platform_focus = src["platform_focus"]
            db_src.collector_id = src["collector_id"]
            db_src.enabled = src["enabled"]
            db_src.expected_freshness_hours = src["expected_freshness_hours"]
        else:
            db_src = DBSource(
                source_id=src["source_id"],
                name=src["name"],
                base_url=src["base_url"],
                source_type=src["source_type"],
                platform_focus=src["platform_focus"],
                collector_id=src["collector_id"],
                enabled=src["enabled"],
                expected_freshness_hours=src["expected_freshness_hours"]
            )
            db.add(db_src)
    db.commit()
    log_structured("Sources synchronized in database", {"count": len(DEFAULT_SOURCES)})


def get_enabled_sources(db: Session) -> List[DBSource]:
    """Retrieves all enabled sources from the database."""
    return db.query(DBSource).filter(DBSource.enabled == True).all()


def create_scrape_run(
    db: Session,
    source_id: str,
    status: str,
    scraped_at: datetime,
    records_scraped: int,
    validation_failures: int,
    duplicates_found: int,
    error_message: Optional[str] = None
) -> DBScrapeRun:
    """Creates a new scrape run log record."""
    run = DBScrapeRun(
        source_id=source_id,
        scraped_at=scraped_at,
        status=status,
        records_scraped=records_scraped,
        validation_failures=validation_failures,
        duplicates_found=duplicates_found,
        error_message=error_message
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    log_structured(
        f"Database: Scrape run recorded for {source_id}",
        {"run_id": run.id, "status": status, "records": records_scraped}
    )
    return run


def create_raw_articles(db: Session, scrape_run_id: int, source_id: str, items: List[Dict[str, Any]]) -> None:
    """
    Stores raw article payload for audit/debugging purposes.
    items should be a list of raw dicts directly from the scraper.
    """
    for item in items:
        article_url = item.get("article_url", "")
        article_title = item.get("article_title", "Untitled")
        
        published_at = None
        updated_at = None
        
        def parse_date(date_str):
            if not date_str:
                return None
            try:
                dt = datetime.fromisoformat(str(date_str).replace("Z", "+00:00"))
                return dt.replace(tzinfo=None)
            except ValueError:
                return None

        published_at = parse_date(item.get("published_at"))
        updated_at = parse_date(item.get("updated_at"))
        
        scraped_at_val = datetime.utcnow()
        if "scraped_at" in item:
            parsed_scraped = parse_date(item["scraped_at"])
            if parsed_scraped:
                scraped_at_val = parsed_scraped
                
        raw_art = DBRawArticle(
            scrape_run_id=scrape_run_id,
            source_id=source_id,
            article_url=article_url,
            article_title=article_title,
            raw_content=item,
            published_at=published_at,
            updated_at=updated_at,
            scraped_at=scraped_at_val
        )
        db.add(raw_art)
    db.commit()
    log_structured("Database: Raw articles stored for debug", {"count": len(items), "run_id": scrape_run_id})


def get_all_trend_keys(db: Session) -> List[str]:
    """
    Returns normalized deduplication keys for all existing trends in the database.
    Format: source_id:normalized_url:normalized_title
    """
    trends = db.query(DBTrendSignal.source_id, DBTrendSignal.article_url, DBTrendSignal.normalized_title).all()
    from tune_the_trend.services.validation import normalize_url
    keys = []
    for source_id, article_url, norm_title in trends:
        norm_url = normalize_url(article_url)
        keys.append(f"{source_id}:{norm_url}:{norm_title}")
    return keys


def save_trend_and_music(
    db: Session,
    trend_signal: TrendSignal,
    music_evidence: Optional[MusicEvidence] = None
) -> DBTrendSignal:
    """
    Saves a curated TrendSignal and its associated MusicEvidence.
    If music_evidence is present, it's linked via trend_signal_id.
    """
    db_trend = DBTrendSignal(
        source_id=trend_signal.source_id,
        article_url=trend_signal.article_url,
        trend_title=trend_signal.trend_title,
        normalized_title=trend_signal.normalized_title,
        trend_description=trend_signal.trend_description,
        platform=trend_signal.platform,
        content_format=trend_signal.content_format,
        content_hash=trend_signal.content_hash,
        niches=trend_signal.niches,
        keywords=trend_signal.keywords,
        moods=trend_signal.moods,
        styles=trend_signal.styles,
        scraped_at=trend_signal.scraped_at,
        freshness_status=trend_signal.freshness_status,
        interpreted_at=trend_signal.interpreted_at
    )
    db.add(db_trend)
    db.commit()
    db.refresh(db_trend)
    
    if music_evidence:
        db_music = DBMusicEvidence(
            trend_signal_id=db_trend.id,
            audio_mentioned=music_evidence.audio_mentioned,
            track_title=music_evidence.track_title,
            artist=music_evidence.artist,
            spotify_id=music_evidence.spotify_id,
            spotify_url=music_evidence.spotify_url,
            preview_url=music_evidence.preview_url,
            genres=music_evidence.genres,
            popularity=music_evidence.popularity,
            energy=music_evidence.energy,
            tempo=music_evidence.tempo,
            valence=music_evidence.valence,
            confidence_score=music_evidence.confidence_score,
            source=trend_signal.source_id,
            source_url=trend_signal.article_url,
            scraped_at=trend_signal.scraped_at
        )
        db.add(db_music)
        db.commit()
        db.refresh(db_music)
        
    log_structured(
        f"Database: Saved trend signal",
        {"trend_id": db_trend.id, "has_music": music_evidence is not None}
    )
    return db_trend


def get_all_active_trends_with_music(db: Session) -> List[DBTrendSignal]:
    """Retrieves all trend signals from the DB."""
    return db.query(DBTrendSignal).all()


def get_music_for_trend(db: Session, trend_signal_id: int) -> Optional[DBMusicEvidence]:
    """Retrieves the music evidence linked to a trend signal."""
    return db.query(DBMusicEvidence).filter(DBMusicEvidence.trend_signal_id == trend_signal_id).first()


def save_creator_profile(db: Session, profile: CreatorProfile) -> DBCreatorProfile:
    """Saves a creator profile input."""
    db_profile = DBCreatorProfile(
        content_type=profile.content_type,
        niche=profile.niche,
        desired_music_style=profile.desired_music_style,
        description=profile.description
    )
    db.add(db_profile)
    db.commit()
    db.refresh(db_profile)
    return db_profile


def save_recommendations(
    db: Session,
    creator_profile_id: Optional[int],
    recs: List[Recommendation]
) -> None:
    """Saves recommended results for auditing."""
    for rec in recs:
        db_rec = DBRecommendation(
            creator_profile_id=creator_profile_id,
            trend_signal_id=rec.candidate.trend_signal.id,
            music_evidence_id=rec.candidate.music_evidence.id if rec.candidate.music_evidence else None,
            final_score=rec.final_score,
            evidence_summary=rec.evidence_summary,
            rerank_reasons=rec.rerank_reasons,
            source=rec.candidate.trend_signal.source_id,
            source_url=rec.candidate.trend_signal.article_url,
            scraped_at=rec.candidate.trend_signal.scraped_at
        )
        db.add(db_rec)
    db.commit()
    log_structured("Database: Saved recommendations", {"count": len(recs), "profile_id": creator_profile_id})


def create_health_check(
    db: Session,
    scrape_run_id: Optional[int],
    collector_id: str,
    checked_at: datetime,
    is_healthy: bool,
    record_count: int,
    field_coverages: Dict[str, float],
    reasons: List[str]
) -> DBCollectorHealthCheck:
    """Saves diagnostic health details of a collector run."""
    check = DBCollectorHealthCheck(
        scrape_run_id=scrape_run_id,
        collector_id=collector_id,
        checked_at=checked_at,
        is_healthy=is_healthy,
        record_count=record_count,
        field_coverages=field_coverages,
        reasons=reasons
    )
    db.add(check)
    db.commit()
    db.refresh(check)
    log_structured(
        "Database: Recorded health check result",
        {"collector_id": collector_id, "is_healthy": is_healthy, "check_id": check.id}
    )
    return check


def create_self_healing_run(
    db: Session,
    collector_id: str,
    diagnostic_prompt: str,
    repair_job_id: str,
    status: str
) -> DBSelfHealingRun:
    """Registers the initialization of a self-healing process."""
    run = DBSelfHealingRun(
        collector_id=collector_id,
        diagnostic_prompt=diagnostic_prompt,
        repair_job_id=repair_job_id,
        status=status
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    log_structured(
        "Database: Created self-healing run record",
        {"collector_id": collector_id, "repair_job_id": repair_job_id, "run_id": run.id}
    )
    return run


def update_self_healing_run(
    db: Session,
    run_id: int,
    status: str,
    repaired_at: Optional[datetime] = None,
    success: Optional[bool] = None,
    validation_run_id: Optional[int] = None,
    validation_status: Optional[str] = None,
    error_message: Optional[str] = None,
    repair_job_id: Optional[str] = None
) -> DBSelfHealingRun:
    """Updates status and results of a self-healing process."""
    run = db.query(DBSelfHealingRun).filter(DBSelfHealingRun.id == run_id).first()
    if not run:
        raise ValueError(f"Self healing run not found: {run_id}")
        
    run.status = status
    if repaired_at:
        run.repaired_at = repaired_at
    if success is not None:
        run.success = success
    if validation_run_id is not None:
        run.validation_run_id = validation_run_id
    if validation_status is not None:
        run.validation_status = validation_status
    if error_message is not None:
        run.error_message = error_message
    if repair_job_id is not None:
        run.repair_job_id = repair_job_id
        
    db.commit()
    db.refresh(run)
    log_structured(
        "Database: Updated self-healing run progress",
        {"run_id": run_id, "status": status, "success": success}
    )
    return run


def find_cached_trend(
    db: Session,
    source_id: str,
    article_url: str,
    trend_title: str,
    content_hash: str
) -> Optional[DBTrendSignal]:
    """Looks up a previously processed, identical trend signal from the DB cache."""
    return db.query(DBTrendSignal).filter(
        DBTrendSignal.source_id == source_id,
        DBTrendSignal.article_url == article_url,
        DBTrendSignal.trend_title == trend_title,
        DBTrendSignal.content_hash == content_hash
    ).first()
