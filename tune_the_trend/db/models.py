from datetime import datetime
from typing import Any, Dict, List, Optional
from sqlalchemy import (
    String,
    Boolean,
    DateTime,
    Float,
    Text,
    ForeignKey,
    JSON
)
from sqlalchemy.sql import func
from sqlalchemy.orm import Mapped, mapped_column
from tune_the_trend.db.database import Base


class DBSource(Base):
    """DB table mapping to sources."""
    __tablename__ = "sources"

    source_id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    base_url: Mapped[str] = mapped_column(String, nullable=False)
    source_type: Mapped[str] = mapped_column(String, nullable=False)
    platform_focus: Mapped[str] = mapped_column(String, nullable=False)
    collector_id: Mapped[str] = mapped_column(String, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    expected_freshness_hours: Mapped[int] = mapped_column(default=168)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class DBScrapeRun(Base):
    """DB table mapping to scrape runs."""
    __tablename__ = "scrape_runs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    source_id: Mapped[str] = mapped_column(String, ForeignKey("sources.source_id"), nullable=False)
    scraped_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)  # success, failed
    records_scraped: Mapped[int] = mapped_column(default=0)
    validation_failures: Mapped[int] = mapped_column(default=0)
    duplicates_found: Mapped[int] = mapped_column(default=0)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DBRawArticle(Base):
    """DB table mapping to raw articles for debugging purposes."""
    __tablename__ = "raw_articles"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    scrape_run_id: Mapped[Optional[int]] = mapped_column(ForeignKey("scrape_runs.id"), nullable=True)
    source_id: Mapped[str] = mapped_column(String, nullable=False)
    article_url: Mapped[str] = mapped_column(String, nullable=False)
    article_title: Mapped[str] = mapped_column(String, nullable=False)
    raw_content: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)  # stores raw JSON payload item
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    scraped_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DBTrendSignal(Base):
    """DB table mapping to curated trend signals."""
    __tablename__ = "trend_signals"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    source_id: Mapped[str] = mapped_column(String, ForeignKey("sources.source_id"), nullable=False)
    article_url: Mapped[str] = mapped_column(String, nullable=False)
    trend_title: Mapped[str] = mapped_column(String, nullable=False)
    normalized_title: Mapped[str] = mapped_column(String, nullable=False)
    trend_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    platform: Mapped[str] = mapped_column(String, nullable=False)
    content_format: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    content_hash: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    
    niches: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=list)
    keywords: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=list)
    moods: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=list)
    styles: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=list)
    
    scraped_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    freshness_status: Mapped[str] = mapped_column(String, nullable=False, default="fresh")  # fresh, stale
    interpreted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class DBMusicEvidence(Base):
    """DB table mapping to music evidence associated with a trend signal."""
    __tablename__ = "music_evidence"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    trend_signal_id: Mapped[Optional[int]] = mapped_column(ForeignKey("trend_signals.id"), nullable=True)
    audio_mentioned: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    track_title: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    artist: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    
    # Spotify / Meta details
    spotify_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    spotify_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    preview_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    genres: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=list)
    popularity: Mapped[Optional[int]] = mapped_column(nullable=True)
    
    # Audio features
    energy: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    tempo: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    valence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    confidence_score: Mapped[float] = mapped_column(Float, default=1.0)
    
    # Audit fields required by rules
    source: Mapped[str] = mapped_column(String, nullable=False)  # source_id
    source_url: Mapped[str] = mapped_column(String, nullable=False)  # article_url
    scraped_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class DBCreatorProfile(Base):
    """DB table mapping to creator profiles inputted into the app."""
    __tablename__ = "creator_profiles"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    content_type: Mapped[str] = mapped_column(String, nullable=False)
    niche: Mapped[str] = mapped_column(String, nullable=False)
    desired_music_style: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DBRecommendation(Base):
    """DB table mapping to generated recommendations."""
    __tablename__ = "recommendations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    creator_profile_id: Mapped[Optional[int]] = mapped_column(ForeignKey("creator_profiles.id"), nullable=True)
    trend_signal_id: Mapped[int] = mapped_column(ForeignKey("trend_signals.id"), nullable=False)
    music_evidence_id: Mapped[Optional[int]] = mapped_column(ForeignKey("music_evidence.id"), nullable=True)
    final_score: Mapped[float] = mapped_column(Float, nullable=False)
    evidence_summary: Mapped[str] = mapped_column(Text, nullable=False)
    rerank_reasons: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=list)
    
    # Audit fields required by rules
    source: Mapped[str] = mapped_column(String, nullable=False)
    source_url: Mapped[str] = mapped_column(String, nullable=False)
    scraped_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DBCollectorHealthCheck(Base):
    """DB table mapping to collector health diagnostics."""
    __tablename__ = "collector_health_checks"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    scrape_run_id: Mapped[Optional[int]] = mapped_column(ForeignKey("scrape_runs.id"), nullable=True)
    collector_id: Mapped[str] = mapped_column(String, nullable=False)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_healthy: Mapped[bool] = mapped_column(Boolean, nullable=False)
    record_count: Mapped[int] = mapped_column(nullable=False)
    field_coverages: Mapped[Dict[str, float]] = mapped_column(JSON, nullable=False, default=dict)
    reasons: Mapped[List[str]] = mapped_column(JSON, nullable=False, default=list)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DBSelfHealingRun(Base):
    """DB table mapping to self-healing controller executions."""
    __tablename__ = "self_healing_runs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    collector_id: Mapped[str] = mapped_column(String, nullable=False)
    diagnostic_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    repair_job_id: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)  # running, completed, failed
    repaired_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    success: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    validation_run_id: Mapped[Optional[int]] = mapped_column(ForeignKey("scrape_runs.id"), nullable=True)
    validation_status: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # healthy, unhealthy, pending
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


# Helper to indicate import check passes
DB_MODELS_IMPORTED = True
