from datetime import datetime, timedelta
from tune_the_trend.models import RawTrendItem
from tune_the_trend.services.validation import (
    normalize_url,
    normalize_title,
    calculate_freshness,
    process_and_deduplicate
)


def test_normalize_url():
    assert normalize_url("https://Later.com/Blog/reels/ ") == "https://later.com/blog/reels"
    assert normalize_url("https://hootsuite.com/report#fragment-1") == "https://hootsuite.com/report"
    assert normalize_url("") == ""


def test_normalize_title():
    assert normalize_title("  Espresso   Dance   Challenge  ") == "espresso dance challenge"
    assert normalize_title("Test\nTitle\tMulti-Space") == "test title multi-space"
    assert normalize_title("") == ""


def test_calculate_freshness():
    now = datetime.utcnow()
    
    # Fresh item (1 hour old)
    fresh_pub = now - timedelta(hours=1)
    assert calculate_freshness(published_at=fresh_pub, updated_at=None, scraped_at=now, threshold_hours=24) == "fresh"
    
    # Stale item (25 hours old with 24 hour threshold)
    stale_pub = now - timedelta(hours=25)
    assert calculate_freshness(published_at=stale_pub, updated_at=None, scraped_at=now, threshold_hours=24) == "stale"
    
    # Stale published, but fresh updated (updated takes precedence)
    fresh_upd = now - timedelta(hours=2)
    assert calculate_freshness(published_at=stale_pub, updated_at=fresh_upd, scraped_at=now, threshold_hours=24) == "fresh"


def test_process_and_deduplicate():
    now = datetime.utcnow()
    raw_items = [
        RawTrendItem(
            source_id="later",
            source_url="https://later.com/blog",
            article_url="https://later.com/blog/trends-now",
            article_title="Trends August",
            published_at=now,
            scraped_at=now,
            trend_title="Aesthetic Cooking",
            platform="instagram"
        ),
        # Exact duplicate
        RawTrendItem(
            source_id="later",
            source_url="https://later.com/blog",
            article_url="https://later.com/blog/trends-now/",
            article_title="Trends August",
            published_at=now,
            scraped_at=now,
            trend_title="  Aesthetic   Cooking  ",
            platform="instagram"
        ),
        # Unique trend
        RawTrendItem(
            source_id="later",
            source_url="https://later.com/blog",
            article_url="https://later.com/blog/trends-now",
            article_title="Trends August",
            published_at=now,
            scraped_at=now,
            trend_title="Fitness Challenge",
            platform="instagram"
        )
    ]
    
    signals, dedup_count, validation_failures = process_and_deduplicate(raw_items)
    
    assert len(signals) == 2
    assert dedup_count == 1
    assert validation_failures == 0
    assert signals[0].trend_title == "Aesthetic Cooking"
    assert signals[1].trend_title == "Fitness Challenge"
