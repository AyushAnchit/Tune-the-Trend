import traceback
import hashlib
from datetime import datetime
from typing import Dict, Any, List
from sqlalchemy.orm import Session
from tune_the_trend.config import log_structured
from tune_the_trend.db.repository import (
    get_enabled_sources,
    create_scrape_run,
    create_raw_articles,
    get_all_trend_keys,
    save_trend_and_music
)
from tune_the_trend.services.scraper import BrightDataScraper
from tune_the_trend.services.llm import get_llm_provider
from tune_the_trend.services.music import get_music_provider
from tune_the_trend.services.validation import (
    process_and_deduplicate,
    normalize_url,
    normalize_title,
    calculate_freshness,
    validate_raw_item
)
from tune_the_trend.models import TrendSignal, MusicEvidence


def run_pipeline(db: Session) -> Dict[str, Any]:
    """
    Triggers and runs the ingest pipeline for all enabled sources.
    Collects raw articles, interprets trends via LLM, enriches music metadata,
    deduplicates trends, and stores curated results in SQLite.
    """
    log_structured("Pipeline Start: Executing ingest pipeline")
    
    # 1. Fetch enabled sources
    sources = get_enabled_sources(db)
    if not sources:
        log_structured("Pipeline Info: No active/enabled sources found", level=30)
        return {"status": "success", "processed_sources": 0}
        
    scraper = BrightDataScraper()
    llm = get_llm_provider()
    music_resolver = get_music_provider()
    
    summary_stats: Dict[str, Any] = {
        "status": "success",
        "processed_sources": len(sources),
        "details": {}
    }
    
    # Retrieve existing deduplication keys to prevent inserting duplicates
    existing_keys = get_all_trend_keys(db)
    
    for src in sources:
        source_id = src.source_id
        collector_id = src.collector_id
        scraped_at = datetime.utcnow()
        
        # Create Scrape Run
        scrape_run = create_scrape_run(
            db=db,
            source_id=source_id,
            status="running",
            scraped_at=scraped_at,
            records_scraped=0,
            validation_failures=0,
            duplicates_found=0
        )
        
        try:
            # 2. Trigger Collector
            payload = scraper.trigger_and_collect(source_id, collector_id)
            
            # Save Raw Articles for audit/debugging
            raw_dicts = [item.model_dump(mode="json") for item in payload.items]
            create_raw_articles(db, scrape_run.id, source_id, raw_dicts)
            
            duplicates_count = 0
            validation_failures_count = 0
            inserted_count = 0
            stale_count = 0
            
            # 3. Process each RawTrendItem
            for raw_item in payload.items:
                # Validate schema first
                is_valid, reason = validate_raw_item(raw_item)
                if not is_valid:
                    validation_failures_count += 1
                    log_structured(
                        f"Pipeline: Raw item rejected during validation",
                        {"source_id": source_id, "reason": reason},
                        level=40
                    )
                    continue
                
                # Check deduplication before running LLM (Save tokens!)
                norm_url = normalize_url(raw_item.article_url)
                norm_title = normalize_title(raw_item.trend_title)
                dedup_key = f"{source_id}:{norm_url}:{norm_title}"
                
                if dedup_key in existing_keys:
                    duplicates_count += 1
                    continue
                    
                existing_keys.append(dedup_key)
                
                # Freshness status calculation
                freshness = calculate_freshness(
                    published_at=raw_item.published_at,
                    updated_at=raw_item.updated_at,
                    scraped_at=scraped_at,
                    threshold_hours=src.expected_freshness_hours
                )
                if freshness == "stale":
                    stale_count += 1

                # 3. Calculate content hash to check LLM cache
                desc_text = raw_item.trend_description or ""
                ev_text = raw_item.evidence_text or ""
                content_to_hash = f"{desc_text}:{ev_text}"
                content_hash = hashlib.md5(content_to_hash.encode("utf-8")).hexdigest()
                
                # Check LLM Cache
                from tune_the_trend.db.repository import find_cached_trend, get_music_for_trend
                cached_trend = find_cached_trend(
                    db=db,
                    source_id=source_id,
                    article_url=raw_item.article_url,
                    trend_title=raw_item.trend_title,
                    content_hash=content_hash
                )
                
                if cached_trend:
                    log_structured(
                        "LLM Cache Hit: Reusing structured extraction",
                        {"source_id": source_id, "trend_title": raw_item.trend_title}
                    )
                    # Reconstruct from cache
                    trend_sig = TrendSignal(
                        source_id=cached_trend.source_id,
                        article_url=cached_trend.article_url,
                        trend_title=cached_trend.trend_title,
                        normalized_title=cached_trend.normalized_title,
                        trend_description=cached_trend.trend_description,
                        platform=cached_trend.platform,
                        content_format=cached_trend.content_format,
                        content_hash=cached_trend.content_hash,
                        niches=cached_trend.niches or [],
                        keywords=cached_trend.keywords or [],
                        moods=cached_trend.moods or [],
                        styles=cached_trend.styles or [],
                        scraped_at=scraped_at,
                        freshness_status=freshness,
                        interpreted_at=datetime.utcnow()
                    )
                    
                    db_music = get_music_for_trend(db, cached_trend.id)
                    music_ev = None
                    if db_music:
                        music_ev = MusicEvidence(
                            audio_mentioned=db_music.audio_mentioned,
                            track_title=db_music.track_title,
                            artist=db_music.artist,
                            spotify_id=db_music.spotify_id,
                            spotify_url=db_music.spotify_url,
                            preview_url=db_music.preview_url,
                            genres=db_music.genres or [],
                            popularity=db_music.popularity,
                            energy=db_music.energy,
                            tempo=db_music.tempo,
                            valence=db_music.valence,
                            confidence_score=db_music.confidence_score
                        )
                else:
                    # 4. LLM parses and enriches structured details (Job A)
                    try:
                        extracted = llm.extract_trend_signal(raw_item)
                    except Exception as extraction_err:
                        log_structured(
                            "Pipeline: LLM extraction failed. Skipping item.",
                            {"trend": raw_item.trend_title, "error": str(extraction_err)},
                            level=40 # ERROR
                        )
                        validation_failures_count += 1
                        continue

                    # Merge parsed LLM data with raw item metadata to build TrendSignal
                    trend_sig = TrendSignal(
                        source_id=source_id,
                        article_url=raw_item.article_url,
                        trend_title=raw_item.trend_title,
                        normalized_title=norm_title,
                        trend_description=raw_item.trend_description or extracted.trend_name,
                        platform=raw_item.platform,
                        content_format=extracted.content_formats[0] if extracted.content_formats else raw_item.content_format,
                        content_hash=content_hash,
                        niches=extracted.niches or raw_item.niches,
                        keywords=extracted.keywords or raw_item.keywords,
                        moods=extracted.moods or raw_item.moods,
                        styles=extracted.styles or raw_item.styles,
                        scraped_at=scraped_at,
                        freshness_status=freshness,
                        interpreted_at=datetime.utcnow()
                    )
                    
                    # 5. Resolve Music Evidence if available
                    music_ev = None
                    music_data = extracted.music_evidence
                    if music_data.explicit_track or music_data.audio_name:
                        track_title = music_data.track_title
                        artist = music_data.artist
                        
                        if track_title:
                            # Call Music Metadata Provider (e.g. Spotify) to enrich
                            spotify_details = music_resolver.resolve_track(track_title, artist)
                            
                            if spotify_details:
                                music_ev = MusicEvidence(
                                    audio_mentioned=music_data.audio_name,
                                    track_title=track_title,
                                    artist=artist,
                                    spotify_id=spotify_details.get("spotify_id"),
                                    spotify_url=spotify_details.get("spotify_url"),
                                    preview_url=spotify_details.get("preview_url"),
                                    genres=spotify_details.get("genres") or [],
                                    popularity=spotify_details.get("popularity"),
                                    energy=spotify_details.get("energy"),
                                    tempo=spotify_details.get("tempo"),
                                    valence=spotify_details.get("valence"),
                                    confidence_score=spotify_details.get("confidence_score") or extracted.confidence
                                )
                            else:
                                music_ev = MusicEvidence(
                                    audio_mentioned=music_data.audio_name,
                                    track_title=track_title,
                                    artist=artist,
                                    confidence_score=extracted.confidence
                                )
                        elif music_data.audio_name:
                            music_ev = MusicEvidence(
                                audio_mentioned=music_data.audio_name,
                                track_title=music_data.audio_name,
                                artist="Unknown Artist",
                                confidence_score=extracted.confidence
                            )

                # 6. Persist to DB
                save_trend_and_music(db, trend_sig, music_ev)
                inserted_count += 1
                
            # Update Scrape Run details
            scrape_run.status = "success"
            scrape_run.records_scraped = inserted_count
            scrape_run.validation_failures = validation_failures_count
            scrape_run.duplicates_found = duplicates_count
            db.commit()
            
            summary_stats["details"][source_id] = {
                "inserted": inserted_count,
                "duplicates": duplicates_count,
                "validation_failures": validation_failures_count,
                "stale_records": stale_count,
                "status": "success"
            }
            
            log_structured(
                f"Pipeline Complete: {source_id} execution successful",
                summary_stats["details"][source_id]
            )
            
        except Exception as e:
            db.rollback()
            scrape_run.status = "failed"
            scrape_run.error_message = f"{str(e)}\n{traceback.format_exc()}"
            db.commit()
            
            summary_stats["details"][source_id] = {
                "status": "failed",
                "error": str(e)
            }
            
            log_structured(
                f"Pipeline Error: Failed to ingest source {source_id}",
                {"error": str(e), "traceback": traceback.format_exc()},
                level=50 # CRITICAL
            )
            summary_stats["status"] = "partial_failure"
            
    return summary_stats
