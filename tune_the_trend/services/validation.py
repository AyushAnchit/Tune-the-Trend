import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from tune_the_trend.config import log_structured, settings
from tune_the_trend.models import RawTrendItem, TrendSignal


def normalize_url(url: str) -> str:
    """
    Normalizes a URL by removing fragments, trailing slashes,
    lowercasing, and stripping whitespace.
    """
    if not url:
        return ""
    # Strip whitespace
    url = url.strip()
    # Remove URL fragment
    url = url.split("#")[0]
    # Remove trailing slash
    url = url.rstrip("/")
    # Lowercase for canonical comparisons
    return url.lower()


def normalize_title(title: str) -> str:
    """
    Normalizes a trend title by lowercasing, stripping leading/trailing whitespace,
    and replacing multiple spaces with a single space.
    """
    if not title:
        return ""
    title = title.lower().strip()
    # Replace multiple spaces/newlines/tabs with a single space
    title = re.sub(r"\s+", " ", title)
    return title


def calculate_freshness(
    published_at: Optional[datetime],
    updated_at: Optional[datetime],
    scraped_at: datetime,
    threshold_hours: int = settings.STALE_THRESHOLD_HOURS
) -> str:
    """
    Checks the freshness of a record based on updated_at and published_at.
    Returns "fresh" or "stale".
    """
    target_date = None
    
    if updated_at:
        target_date = updated_at
    elif published_at:
        target_date = published_at
        
    if not target_date:
        log_structured(
            "Validation Warning: Both published_at and updated_at are missing. Defaulting to fresh.",
            {"scraped_at": scraped_at.isoformat()},
            level=30 # WARNING
        )
        return "fresh"
        
    age_hours = (scraped_at - target_date).total_seconds() / 3600.0
    
    if age_hours > threshold_hours:
        log_structured(
            "Freshness Check: Record marked as stale",
            {
                "target_date": target_date.isoformat(),
                "scraped_at": scraped_at.isoformat(),
                "age_hours": age_hours,
                "threshold_hours": threshold_hours
            }
        )
        return "stale"
        
    return "fresh"


def validate_raw_item(item: RawTrendItem) -> Tuple[bool, Optional[str]]:
    """
    Validates a RawTrendItem against basic schema requirements.
    Returns (is_valid, error_reason).
    """
    if not item.source_id:
        return False, "source_id is required"
    if not item.article_url:
        return False, "article_url is required"
    if not item.trend_title:
        return False, "trend_title is required"
    if not item.platform:
        return False, "platform is required"
    if not item.published_at and not item.updated_at:
        # Warn but pass validation according to "published_at and/or updated_at where available"
        pass
    return True, None


def process_and_deduplicate(
    raw_items: List[RawTrendItem],
    existing_normalized_keys: Optional[List[str]] = None
) -> Tuple[List[TrendSignal], int, int]:
    """
    Validates, normalizes, and filters raw items to remove duplicates.
    Keeps track of how many items were processed, how many were duplicate,
    and how many validation failures occurred.
    
    Returns (list of TrendSignals, deduplication_count, validation_failure_count).
    """
    existing_keys = set(existing_normalized_keys or [])
    dedup_count = 0
    validation_failures = 0
    stale_count = 0
    valid_signals: List[TrendSignal] = []
    
    for raw in raw_items:
        # 1. Validate Schema
        is_valid, reason = validate_raw_item(raw)
        if not is_valid:
            validation_failures += 1
            log_structured(
                f"Validation Failure: Raw trend item rejected",
                {"reason": reason, "raw_item": raw.model_dump_json()},
                level=40 # ERROR
            )
            continue
            
        # 2. Normalize components
        norm_url = normalize_url(raw.article_url)
        norm_title = normalize_title(raw.trend_title)
        
        # 3. Deduplication check
        # Deduplicate using: source_id + canonical article URL + normalized trend title
        dedup_key = f"{raw.source_id}:{norm_url}:{norm_title}"
        if dedup_key in existing_keys:
            dedup_count += 1
            log_structured(
                f"Deduplication: Duplicate trend item skipped",
                {"dedup_key": dedup_key}
            )
            continue
            
        # Add to the current run's deduplication set to avoid duplicates within the same batch
        existing_keys.add(dedup_key)
        
        # 4. Freshness Validation
        freshness = calculate_freshness(
            published_at=raw.published_at,
            updated_at=raw.updated_at,
            scraped_at=raw.scraped_at
        )
        if freshness == "stale":
            stale_count += 1
            
        # 5. Build TrendSignal
        signal = TrendSignal(
            source_id=raw.source_id,
            article_url=raw.article_url,
            trend_title=raw.trend_title,
            normalized_title=norm_title,
            trend_description=raw.trend_description,
            platform=raw.platform,
            content_format=raw.content_format,
            niches=raw.niches,
            keywords=raw.keywords,
            moods=raw.moods,
            styles=raw.styles,
            scraped_at=raw.scraped_at,
            freshness_status=freshness,
            interpreted_at=datetime.utcnow()
        )
        valid_signals.append(signal)
        
    log_structured(
        "Deduplication and Validation Run Complete",
        {
            "input_items": len(raw_items),
            "valid_signals_produced": len(valid_signals),
            "duplicates_removed": dedup_count,
            "stale_records_found": stale_count,
            "validation_failures": validation_failures
        }
    )
    
    return valid_signals, dedup_count, validation_failures
