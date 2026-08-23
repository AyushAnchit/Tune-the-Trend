from datetime import datetime
from tune_the_trend.models import (
    SourceMetadata,
    ArticleRecord,
    RawTrendItem,
    RawScrapePayload,
    TrendSignal,
    MusicEvidence,
    CreatorProfile,
    CreatorQuery,
    CandidateRecommendation,
    Recommendation
)


def test_source_metadata_model():
    data = {
        "source_id": "test_src",
        "name": "Test Source",
        "base_url": "https://test.com",
        "source_type": "blog",
        "platform_focus": "reels",
        "collector_id": "col_123",
        "enabled": True,
        "expected_freshness_hours": 24
    }
    model = SourceMetadata(**data)
    assert model.source_id == "test_src"
    assert model.enabled is True


def test_raw_trend_item_model():
    now = datetime.utcnow()
    data = {
        "source_id": "later_instagram",
        "source_url": "https://later.com/blog",
        "article_url": "https://later.com/blog/trends-now",
        "article_title": "Weekly Reels Trends",
        "published_at": now,
        "scraped_at": now,
        "trend_title": "Sunset Transitions",
        "platform": "instagram",
        "niches": ["travel", "aesthetic"],
        "keywords": ["sunset", "transition"],
        "audio_mentioned": "Original Audio",
        "track_title": "Sunset Beats",
        "artist": "DJ Sunset"
    }
    model = RawTrendItem(**data)
    assert model.trend_title == "Sunset Transitions"
    assert model.artist == "DJ Sunset"
    assert "sunset" in model.keywords


def test_raw_scrape_payload_model():
    now = datetime.utcnow()
    item_data = {
        "source_id": "later_instagram",
        "source_url": "https://later.com/blog",
        "article_url": "https://later.com/blog/trends-now",
        "article_title": "Weekly Reels Trends",
        "published_at": now,
        "scraped_at": now,
        "trend_title": "Sunset Transitions",
        "platform": "instagram",
    }
    payload = RawScrapePayload(
        source_id="later_instagram",
        scraped_at=now,
        items=[RawTrendItem(**item_data)]
    )
    assert len(payload.items) == 1
    assert payload.items[0].trend_title == "Sunset Transitions"


def test_music_evidence_model():
    model = MusicEvidence(
        track_title="Test Song",
        artist="Test Artist",
        genres=["indie", "pop"],
        energy=0.75,
        tempo=110.5,
        valence=0.6,
        confidence_score=0.9
    )
    assert model.track_title == "Test Song"
    assert model.energy == 0.75
    assert model.genres == ["indie", "pop"]
