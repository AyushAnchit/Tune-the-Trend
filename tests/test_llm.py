import pytest
from datetime import datetime
from tune_the_trend.models import CreatorProfile, RawTrendItem
from tune_the_trend.services.llm import get_llm_provider, MockLLMProvider


def test_llm_provider_factory():
    provider = get_llm_provider()
    assert isinstance(provider, MockLLMProvider)


def test_mock_interpret_trend():
    now = datetime.utcnow()
    raw = RawTrendItem(
        source_id="later_instagram",
        source_url="https://later.com/blog",
        article_url="https://later.com/blog/trends",
        article_title="Trends List",
        scraped_at=now,
        trend_title="Cooking Lo-Fi Vlog",
        trend_description="Sharing recipes with soft lo-fi background music.",
        platform="instagram",
        audio_mentioned="Espresso by Sabrina Carpenter"
    )
    
    provider = MockLLMProvider()
    trend_data, music_data = provider.interpret_trend(raw)
    
    assert "food & cooking" in trend_data["niches"]
    assert "lo-fi" in trend_data["styles"]
    assert "chill" in trend_data["moods"]
    
    assert music_data is not None
    assert music_data["track_title"] == "Espresso"
    assert music_data["artist"] == "Sabrina Carpenter"


def test_mock_parse_creator_profile():
    profile = CreatorProfile(
        content_type="reels",
        niche="fitness",
        desired_music_style="upbeat pop",
        description="Daily workouts at the gym showing transitions."
    )
    
    provider = MockLLMProvider()
    query = provider.parse_creator_profile(profile)
    
    assert "reels" in query.target_platforms
    assert "fitness" in query.target_niches
    assert "energetic" in query.target_moods
    assert "pop" in query.target_styles
    assert "workouts" in query.semantic_search_terms


def test_mock_evaluate_semantic_relevance():
    profile = CreatorProfile(
        content_type="reels",
        niche="cooking",
        desired_music_style="chill lo-fi",
        description="Baking cakes at home."
    )
    
    provider = MockLLMProvider()
    
    score_high, reasons_high = provider.evaluate_semantic_relevance(
        trend_title="Cake Decorating Lofi",
        trend_desc="Baking cakes with lofi audio background.",
        evidence_text="Trending with 50% increase in baking niches.",
        profile=profile
    )
    
    score_low, reasons_low = provider.evaluate_semantic_relevance(
        trend_title="Gym Gym Gym",
        trend_desc="Workout motivation challenge.",
        evidence_text="Highly energetic audio.",
        profile=profile
    )
    
    assert score_high > score_low
    assert any("alignment" in r for r in reasons_high)


def test_creator_profile_minimal_input():
    profile = CreatorProfile(
        content_type="short video",
        niche="gaming",
        desired_music="lofi"
    )
    assert profile.desired_music == "lofi"
    assert profile.desired_music_style == "lofi"
    assert profile.content_description is None
    
    provider = MockLLMProvider()
    query = provider.parse_creator_input(profile)
    assert query.content.type == "short_video"
    assert query.creator.niche == "gaming"
    assert "gaming" in query.search_terms


def test_creator_profile_detailed_input():
    profile = CreatorProfile(
        content_type="short video",
        niche="gaming",
        desired_music="heavy metal",
        platform="youtube",
        content_description="I make Valorant clutch Shorts",
        audience="teens",
        extra_keywords=["clutch", "radiant"]
    )
    
    provider = MockLLMProvider()
    query = provider.parse_creator_input(profile)
    
    assert query.content.platform == "youtube"
    assert "valorant" in query.search_terms
    assert "clutch" in query.search_terms
    assert "radiant" in query.content.keywords


def test_creator_profile_ambiguous_input():
    profile = CreatorProfile(
        content_type="short video",
        niche="lifestyle",
        desired_music="pop",
        content_description="just doing some content for fun"
    )
    
    provider = MockLLMProvider()
    query = provider.parse_creator_input(profile)
    
    # Heuristics should not invent unrelated niches or platforms
    assert query.creator.niche == "lifestyle"
    assert "valorant" not in query.search_terms


def test_creator_profile_empty_optional_description():
    profile = CreatorProfile(
        content_type="short video",
        niche="cooking",
        desired_music="jazz",
        content_description=""
    )
    
    provider = MockLLMProvider()
    query = provider.parse_creator_input(profile)
    assert query.description == ""
    assert query.creator.niche == "cooking"


def test_malformed_llm_output():
    from tune_the_trend.services.llm import RealLLMProvider
    
    provider = RealLLMProvider(provider="openai", api_key="test-key", model="gpt-4")
    
    # Mock calls list to simulate a failure on first call and success on second call
    call_counter = 0
    
    def mock_call_api_json(prompt):
        nonlocal call_counter
        call_counter += 1
        if call_counter == 1:
            raise ValueError("Malformed JSON brackets")
        
        # Valid JSON structure for ExtractedTrendSignal Pydantic model
        return {
            "trend_name": "Espresso Dance",
            "platforms": ["instagram"],
            "content_formats": ["reels"],
            "niches": ["dance"],
            "sub_niches": ["dance_pop"],
            "keywords": ["espresso"],
            "moods": ["energetic"],
            "styles": ["pop"],
            "music_evidence": {
                "explicit_track": True,
                "track_title": "Espresso",
                "artist": "Sabrina Carpenter",
                "audio_name": "Espresso",
                "genre_clues": ["pop"],
                "mood_clues": ["happy"],
                "music_characteristics": ["upbeat"],
                "evidence_type": "explicit"
            },
            "confidence": 1.0
        }
        
    provider._call_llm_api_json = mock_call_api_json
    
    # Run extractor
    raw = RawTrendItem(
        source_id="later_instagram",
        source_url="https://later.com",
        article_url="https://later.com/trends",
        article_title="Reels Trends",
        scraped_at=datetime.utcnow(),
        trend_title="Espresso Dance",
        platform="instagram"
    )
    
    # First attempt fails but repair retry succeeds
    result = provider.extract_trend_signal(raw)
    assert result.trend_name == "Espresso Dance"
    assert result.music_evidence.explicit_track is True
    assert call_counter == 2
    
    # Now simulate complete failure where repair also fails
    call_counter = 0
    def mock_call_always_fails(prompt):
        raise ValueError("API error")
        
    provider._call_llm_api_json = mock_call_always_fails
    with pytest.raises(ValueError, match="failed validation repair retry"):
        provider.extract_trend_signal(raw)
