from datetime import datetime
from tune_the_trend.models import CreatorProfile, TrendSignal, MusicEvidence
from tune_the_trend.db.repository import save_trend_and_music
from tune_the_trend.services.recommendation import RecommendationEngine


def test_recommendation_ranking(test_db):
    now = datetime.utcnow()
    
    # 1. Seed DB with trend options
    # Trend 1: Lofi Cooking (Matches Cooking + Chill Lofi profile)
    trend_lofi_cook = TrendSignal(
        source_id="later_instagram",
        article_url="https://later.com/blog/trends-cooking",
        trend_title="Easy Baking Reels",
        normalized_title="easy baking reels",
        trend_description="Creators share quick recipes with lofi background music.",
        platform="instagram",
        niches=["cooking", "lifestyle"],
        moods=["chill"],
        styles=["lo-fi"],
        scraped_at=now,
        freshness_status="fresh"
    )
    music_lofi_cook = MusicEvidence(
        track_title="Baking Beats Lofi",
        artist="Cake Kid",
        genres=["lo-fi"],
        popularity=65,
        energy=0.3,
        tempo=80.0,
        valence=0.4
    )
    save_trend_and_music(test_db, trend_lofi_cook, music_lofi_cook)
    
    # Trend 2: Hype Gym Workout (Mismatch for Cooking profile)
    trend_gym = TrendSignal(
        source_id="later_instagram",
        article_url="https://later.com/blog/trends-fitness",
        trend_title="Deadlift Challenge Hype",
        normalized_title="deadlift challenge hype",
        trend_description="Creators show heavy deadlifts with loud hype music.",
        platform="instagram",
        niches=["fitness"],
        moods=["energetic"],
        styles=["hype"],
        scraped_at=now,
        freshness_status="fresh"
    )
    music_gym = MusicEvidence(
        track_title="Hype Gym Metal",
        artist="Iron Lifters",
        genres=["heavy-metal"],
        popularity=80,
        energy=0.9,
        tempo=140.0,
        valence=0.7
    )
    save_trend_and_music(test_db, trend_gym, music_gym)
    
    # 2. Run Recommendation Engine
    engine = RecommendationEngine(test_db)
    
    profile = CreatorProfile(
        content_type="reels",
        niche="cooking",
        desired_music_style="chill lo-fi",
        description="Showing a simple recipe for baking chocolate cookies."
    )
    
    recs = engine.generate_recommendations(profile, limit=5)
    
    # 3. Assertions
    assert len(recs) > 0
    # The lofi cooking trend must be the top recommendation
    top_rec = recs[0]
    assert top_rec.candidate.trend_signal.trend_title == "Easy Baking Reels"
    assert top_rec.candidate.music_evidence.track_title == "Baking Beats Lofi"
    
    # Verify reasons
    assert any("cooking" in reason for reason in top_rec.rerank_reasons)
    assert any("lo-fi" in reason or "lofi" in reason for reason in top_rec.rerank_reasons)
    
    # Ensure final score is programmatically calculated and valid
    assert top_rec.final_score > 0.0
    
    # If the gym trend was included, it must be lower ranked
    if len(recs) > 1:
        assert recs[1].candidate.trend_signal.trend_title == "Deadlift Challenge Hype"
        assert recs[1].final_score < top_rec.final_score


def test_recommendation_exact_and_partial_niche_match(test_db):
    now = datetime.utcnow()
    # Trend 1: Exact niche match ("cooking")
    t1 = TrendSignal(
        source_id="later_instagram",
        article_url="https://later.com/blog/t1",
        trend_title="Cooking Masterclass",
        normalized_title="cooking masterclass",
        trend_description="Professional baking vlogs.",
        platform="instagram",
        niches=["cooking"],
        scraped_at=now,
        freshness_status="fresh"
    )
    # Trend 2: Partial niche match (no matching niches directly, but similar styles)
    t2 = TrendSignal(
        source_id="later_instagram",
        article_url="https://later.com/blog/t2",
        trend_title="Travel Foodie Vlogs",
        normalized_title="travel foodie vlogs",
        trend_description="Exploring food joints worldwide.",
        platform="instagram",
        niches=["travel"],
        styles=["lo-fi"],
        scraped_at=now,
        freshness_status="fresh"
    )
    save_trend_and_music(test_db, t1, None)
    save_trend_and_music(test_db, t2, None)
    
    engine = RecommendationEngine(test_db)
    profile = CreatorProfile(
        content_type="reels",
        niche="cooking",
        desired_music="lo-fi"
    )
    
    recs = engine.generate_recommendations(profile, allow_broader=True)
    assert len(recs) == 2
    # Exact niche match must rank higher
    assert recs[0].trend_name == "Cooking Masterclass"
    assert recs[1].trend_name == "Travel Foodie Vlogs"


def test_recommendation_no_match(test_db):
    # Seed a cooking trend
    t1 = TrendSignal(
        source_id="later_instagram",
        article_url="https://later.com/blog/t1",
        trend_title="Cooking Masterclass",
        normalized_title="cooking masterclass",
        trend_description="Professional baking vlogs.",
        platform="instagram",
        niches=["cooking"],
        scraped_at=datetime.utcnow(),
        freshness_status="fresh"
    )
    save_trend_and_music(test_db, t1, None)
    
    engine = RecommendationEngine(test_db)
    # Query for gaming, which doesn't match cooking
    profile = CreatorProfile(
        content_type="reels",
        niche="gaming",
        desired_music="hype"
    )
    
    query = engine.llm.parse_creator_input(profile)
    strict_candidates = engine._generate_candidates(query, allow_broader=False)
    assert len(strict_candidates) == 0


def test_recommendation_fresh_vs_stale_trend(test_db):
    now = datetime.utcnow()
    # Trend 1: Fresh
    t1 = TrendSignal(
        source_id="later_instagram",
        article_url="https://later.com/blog/t1",
        trend_title="Fresh Baking",
        normalized_title="fresh baking",
        trend_description="Baking today.",
        platform="instagram",
        niches=["cooking"],
        scraped_at=now,
        freshness_status="fresh"
    )
    # Trend 2: Stale
    t2 = TrendSignal(
        source_id="later_instagram",
        article_url="https://later.com/blog/t2",
        trend_title="Old Baking",
        normalized_title="old baking",
        trend_description="Baking years ago.",
        platform="instagram",
        niches=["cooking"],
        scraped_at=now,
        freshness_status="stale"
    )
    save_trend_and_music(test_db, t1, None)
    save_trend_and_music(test_db, t2, None)
    
    engine = RecommendationEngine(test_db)
    profile = CreatorProfile(
        content_type="reels",
        niche="cooking",
        desired_music="pop"
    )
    
    # Under strict matching, stale trend is filtered out
    recs_strict = engine.generate_recommendations(profile, allow_broader=False)
    assert len(recs_strict) == 1
    assert recs_strict[0].trend_name == "Fresh Baking"
    
    # Under allow_broader, stale trend is included
    recs_broad = engine.generate_recommendations(profile, allow_broader=True)
    assert len(recs_broad) == 2


def test_recommendation_explicit_vs_inferred_music(test_db):
    now = datetime.utcnow()
    # Trend 1: Explicit song
    t1 = TrendSignal(
        source_id="later_instagram",
        article_url="https://later.com/blog/t1",
        trend_title="Cooking With Song",
        normalized_title="cooking with song",
        trend_description="Baking with song.",
        platform="instagram",
        niches=["cooking"],
        scraped_at=now,
        freshness_status="fresh"
    )
    m1 = MusicEvidence(
        track_title="Explicit Track",
        artist="Explicit Artist",
        genres=["pop"],
        confidence_score=1.0
    )
    # Trend 2: Inferred song (styles only, no explicit MusicEvidence)
    t2 = TrendSignal(
        source_id="later_instagram",
        article_url="https://later.com/blog/t2",
        trend_title="Cooking With Style",
        normalized_title="cooking with style",
        trend_description="Baking with lofi.",
        platform="instagram",
        niches=["cooking"],
        styles=["lo-fi"],
        scraped_at=now,
        freshness_status="fresh"
    )
    save_trend_and_music(test_db, t1, m1)
    save_trend_and_music(test_db, t2, None)
    
    engine = RecommendationEngine(test_db)
    profile = CreatorProfile(
        content_type="reels",
        niche="cooking",
        desired_music="pop"
    )
    
    recs = engine.generate_recommendations(profile, allow_broader=False)
    assert len(recs) == 2
    
    # Explicit track prioritized or resolved
    rec_explicit = next(r for r in recs if r.trend_name == "Cooking With Song")
    assert rec_explicit.track == "Explicit Track"
    assert rec_explicit.artist == "Explicit Artist"
    
    # Inferred track triggers dynamic discovery
    rec_inferred = next(r for r in recs if r.trend_name == "Cooking With Style")
    assert rec_inferred.track is not None and len(rec_inferred.track) > 0


def test_recommendation_zero_candidates(test_db):
    engine = RecommendationEngine(test_db)
    profile = CreatorProfile(
        content_type="reels",
        niche="cooking",
        desired_music="pop"
    )
    recs = engine.generate_recommendations(profile)
    assert len(recs) == 0


def test_recommendation_stable_deterministic_ranking(test_db):
    now = datetime.utcnow()
    for i in range(10):
        t = TrendSignal(
            source_id="later_instagram",
            article_url=f"https://later.com/blog/t{i}",
            trend_title=f"Trend {i}",
            normalized_title=f"trend {i}",
            trend_description=f"Description {i}",
            platform="instagram",
            niches=["cooking"],
            scraped_at=now,
            freshness_status="fresh"
        )
        save_trend_and_music(test_db, t, None)
        
    engine = RecommendationEngine(test_db)
    profile = CreatorProfile(
        content_type="reels",
        niche="cooking",
        desired_music="pop"
    )
    
    recs1 = engine.generate_recommendations(profile)
    recs2 = engine.generate_recommendations(profile)
    
    assert len(recs1) == len(recs2)
    # Check that rank order is stable and identical
    for r1, r2 in zip(recs1, recs2):
        assert r1.trend_name == r2.trend_name
        assert r1.final_score == r2.final_score
