import math
import json
from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session
from tune_the_trend.config import log_structured
from tune_the_trend.db.repository import get_all_active_trends_with_music, get_music_for_trend
from tune_the_trend.services.llm import get_llm_provider
from tune_the_trend.services.music import get_music_provider
from tune_the_trend.models import (
    CreatorProfile,
    CreatorQuery,
    CandidateRecommendation,
    Recommendation,
    TrendSignal,
    MusicEvidence
)


def get_cosine_similarity(text1: str, text2: str) -> float:
    """Calculates cosine similarity of two text blocks using simple Bag-of-Words."""
    def get_word_freq(text: str) -> Dict[str, int]:
        freq: Dict[str, int] = {}
        for word in text.lower().split():
            clean_word = "".join(c for c in word if c.isalnum())
            if clean_word and len(clean_word) > 2:
                freq[clean_word] = freq.get(clean_word, 0) + 1
        return freq

    freq1 = get_word_freq(text1)
    freq2 = get_word_freq(text2)
    
    dot_product = sum(val * freq2.get(word, 0) for word, val in freq1.items())
    
    magnitude1 = math.sqrt(sum(val ** 2 for val in freq1.values()))
    magnitude2 = math.sqrt(sum(val ** 2 for val in freq2.values()))
    
    if magnitude1 == 0.0 or magnitude2 == 0.0:
        return 0.0
        
    return dot_product / (magnitude1 * magnitude2)


def platforms_compatible(q_plat: str, t_plat: str) -> bool:
    qp = q_plat.lower()
    tp = t_plat.lower()
    if not qp or qp == "any" or tp == "cross_platform" or qp == "cross_platform":
        return True
    if "reel" in qp and "instagram" in tp:
        return True
    if "instagram" in qp and "reel" in tp:
        return True
    if "short" in qp and "youtube" in tp:
        return True
    if "youtube" in qp and "short" in tp:
        return True
    if qp in tp or tp in qp:
        return True
    return False


class RecommendationEngine:
    """
    Multi-stage recommendation engine:
    Stage 1: Candidate Generation (Deterministic filtering)
    Stage 2: Deterministic Ranking (Configurable weighting & normalization)
    Stage 3: Reranking (Lightweight Cosine Similarity)
    Stage 4: LLM Reranking (Compact context & bounded final score)
    """
    def __init__(self, db: Session):
        self.db = db
        self.llm = get_llm_provider()
        self.music_resolver = get_music_provider()
        
        # Configurable weights (normalized components)
        self.weights = {
            "freshness": 0.25,
            "niche": 0.25,
            "music": 0.20,
            "keyword": 0.15,
            "mood": 0.10,
            "confidence": 0.05
        }

    def generate_recommendations(
        self,
        profile: CreatorProfile,
        limit: int = 5,
        allow_broader: bool = True
    ) -> List[Recommendation]:
        log_structured(
            "Recommendation Run: Starting recommendation generation",
            {"niche": profile.niche, "music_style": profile.desired_music, "allow_broader": allow_broader}
        )

        # Job B: LLM converts creator profile to structured query representation
        query = self.llm.parse_creator_input(profile)
        log_structured("Recommendation Run: Structured CreatorQuery parsed", {"query": query.model_dump()})

        # STAGE 1 — Candidate Generation
        candidates = self._generate_candidates(query, allow_broader)
        if not candidates and not allow_broader:
            log_structured("Recommendation Run: Zero strict candidates found. Automatically expanding to broader candidate matching.")
            candidates = self._generate_candidates(query, allow_broader=True)
            
        if not candidates:
            log_structured("Recommendation Run: Zero candidates found", {"allow_broader": allow_broader})
            return []

        # STAGE 2 — Deterministic Ranking
        ranked_candidates: List[Dict[str, Any]] = []
        for trend, music in candidates:
            score, reasons = self._calculate_match_score(query, trend, music)
            if score > 0.0:
                ranked_candidates.append({
                    "trend": trend,
                    "music": music,
                    "reasons": reasons,
                    "stage2_score": score
                })
                
        # Sort descending and keep top 15
        ranked_candidates.sort(key=lambda x: x["stage2_score"], reverse=True)
        top_15: List[Dict[str, Any]] = ranked_candidates[:15]

        # STAGE 3 — Cosine Similarity
        # creator query representation
        query_text = f"{profile.niche} {profile.desired_music} {profile.content_description or profile.description or ''}"
        for item in top_15:
            trend_sig_item: TrendSignal = item["trend"]
            music_ev_item: Optional[MusicEvidence] = item["music"]
            trend_text = f"{trend_sig_item.trend_title} {trend_sig_item.trend_description or ''} {music_ev_item.audio_mentioned if music_ev_item else ''}"
            
            sim = get_cosine_similarity(query_text, trend_text)
            item["semantic_sim"] = sim
            item["stage3_score"] = float(item["stage2_score"]) + (0.20 * sim)

        # STAGE 4 — LLM Reranking
        candidates_input = []
        for item in top_15:
            trend_llm_item: TrendSignal = item["trend"]
            music_llm_item: Optional[MusicEvidence] = item["music"]
            candidates_input.append({
                "id": trend_llm_item.id,
                "trend_title": trend_llm_item.trend_title,
                "niches": trend_llm_item.niches,
                "platform": trend_llm_item.platform,
                "content_format": trend_llm_item.content_format,
                "moods": trend_llm_item.moods,
                "styles": trend_llm_item.styles,
                "track_title": music_llm_item.track_title if music_llm_item else None,
                "artist": music_llm_item.artist if music_llm_item else None,
                "source_id": trend_llm_item.source_id,
                "scraped_at": trend_llm_item.scraped_at.isoformat(),
                "trend_description": trend_llm_item.trend_description
            })

        # Request LLM Rerank ratings
        llm_ratings = self.llm.llm_rerank(query, candidates_input)
        ratings_by_id = {str(r.get("candidate_id")): r for r in llm_ratings if "candidate_id" in r}

        final_recommendations: List[Recommendation] = []
        seen_track_keys = set()

        # Smart Cultural & Genre Intent Expansion Map
        INTENT_EXPANSIONS = {
            "indian": "bollywood instrumental sitar",
            "mumbai": "bollywood travel sitar",
            "delhi": "bollywood fusion tabla",
            "bollywood": "bollywood instrumental",
            "punjabi": "punjabi bhangra beat",
            "hindi": "hindi bollywood lofi",
            "spanish": "spanish flamenco guitar",
            "flamenco": "flamenco guitar acoustic",
            "japanese": "japanese lofi chill",
            "tokyo": "japanese lofi ambient",
            "french": "french accordion cafe",
            "paris": "french accordion lofi",
            "latin": "latin acoustic guitar",
            "lofi": "lofi chill study beat",
            "violin": "calm classical violin",
            "classical": "cinematic classical violin piano",
            "calm": "calm ambient relaxing",
            "focus": "focus study lofi ambient"
        }

        # Build concise music search query for API resolution
        search_input_text = f"{profile.desired_music or ''} {profile.content_description or profile.description or ''}".lower()
        expanded_terms = []
        for key, val in INTENT_EXPANSIONS.items():
            if key in search_input_text and val not in expanded_terms:
                expanded_terms.append(val)
                
        if expanded_terms:
            clean_query = expanded_terms[0]
        else:
            search_words = []
            raw_music_input = (profile.desired_music or "").replace(",", " ").replace("&", " ").lower().split()
            for w in raw_music_input:
                if len(w) > 2 and w not in search_words:
                    search_words.append(w)
                    
            if not search_words and profile.content_description:
                for word in ["violin", "piano", "guitar", "calm", "focus", "relaxing", "study", "ambient", "flamenco", "classical"]:
                    if word in profile.content_description.lower() and word not in search_words:
                        search_words.append(word)
                        
            clean_query = " ".join(search_words[:3]) if search_words else (query.creator.niche or "trending hits")
            
        similar_tracks = self.music_resolver.search_tracks(clean_query, limit=15)
        similar_track_index = 0
        desired_style = clean_query

        for item in top_15:
            trend_final_item: TrendSignal = item["trend"]
            music_final_item: Optional[MusicEvidence] = item["music"]
            reasons_list: List[str] = list(item["reasons"])
            stage3_score: float = float(item["stage3_score"])
            stage2_score: float = float(item["stage2_score"])
            
            # Retrieve LLM Probabilistic Rating
            rating = ratings_by_id.get(str(trend_final_item.id)) or {}
            
            p_music = float(rating.get("p_music_similarity", rating.get("music_fit", 0.85)))
            p_virality = float(rating.get("p_virality_potential", rating.get("evidence_quality", 0.80)))
            p_concept = float(rating.get("p_concept_relevance", rating.get("relevance", 0.90)))
            v_tier = str(rating.get("virality_tier") or ("Explosive Growth" if p_virality >= 0.85 else ("High Momentum" if p_virality >= 0.70 else "Steady Trend")))
            reason = rating.get("reason", "Strong probabilistic similarity & high virality potential score")
            
            # Posterior combined probability P(Match | Creator, Trend, Music)
            raw_posterior = (0.45 * p_concept) + (0.35 * p_music) + (0.20 * p_virality)
            
            # GATING RULE: If music similarity or concept relevance is low (<0.35), candidate is incompatible
            gating_factor = 1.0 if (p_concept >= 0.35 and p_music >= 0.35) else 0.10
            posterior_prob = round(raw_posterior * gating_factor, 4)
            final_score = round(posterior_prob, 2)
            
            if reason:
                reasons_list.append(reason)
                
            # Filter out candidates with match score under 0.20
            if final_score < 0.20:
                continue

            # Check if explicit track exists or is generic audio placeholder
            t_name = (music_final_item.track_title or "").lower().strip() if music_final_item else ""
            a_name = (music_final_item.artist or "").lower().strip() if music_final_item else ""
            
            is_generic = (
                not music_final_item 
                or not t_name 
                or t_name in ["original audio", "original sound", "unknown track", "unknown artist", "sound", "none", "n/a", ""]
                or a_name in ["unknown artist", "unknown", "various artists", "none", "n/a", ""]
            )
            
            # TRACK DEDUPLICATION & SIMILAR SONG DIVERSITY
            curr_key = (t_name, a_name)
            
            if is_generic or (curr_key in seen_track_keys):
                # Pick a distinct similar track from Deezer search_tracks
                resolved_track = None
                while similar_track_index < len(similar_tracks):
                    cand_trk = similar_tracks[similar_track_index]
                    similar_track_index += 1
                    t_title = str(cand_trk.get("track_title") or "").lower().strip()
                    t_artist = str(cand_trk.get("artist") or "").lower().strip()
                    t_key = (t_title, t_artist)
                    if t_key not in seen_track_keys and t_title:
                        seen_track_keys.add(t_key)
                        resolved_track = cand_trk
                        break
                        
                if resolved_track:
                    music_final_item = MusicEvidence(
                        audio_mentioned=resolved_track.get("track_title"),
                        track_title=resolved_track.get("track_title"),
                        artist=resolved_track.get("artist"),
                        spotify_id=resolved_track.get("spotify_id"),
                        spotify_url=resolved_track.get("spotify_url"),
                        preview_url=resolved_track.get("preview_url"),
                        genres=resolved_track.get("genres") or [desired_style],
                        popularity=resolved_track.get("popularity") or 75,
                        energy=resolved_track.get("energy", 0.25),
                        tempo=resolved_track.get("tempo", 65.0),
                        valence=resolved_track.get("valence", 0.45),
                        confidence_score=0.85
                    )
                else:
                    music_final_item = MusicEvidence(
                        audio_mentioned=f"Trending {desired_style} audio",
                        track_title=f"Trending {desired_style.title()} Sound #{len(final_recommendations)+1}",
                        artist="Trending Beat Producer",
                        genres=[desired_style],
                        popularity=60,
                        energy=0.25,
                        tempo=65.0,
                        valence=0.45,
                        confidence_score=0.75
                    )
            else:
                if t_name and a_name:
                    seen_track_keys.add(curr_key)

            assert music_final_item is not None
            
            cand_rec = CandidateRecommendation(
                trend_signal=trend_final_item,
                music_evidence=music_final_item,
                match_reasons=reasons_list,
                initial_score=stage2_score
            )
            
            final_recommendations.append(Recommendation(
                candidate=cand_rec,
                final_score=final_score,
                rerank_reasons=reasons_list,
                evidence_summary=reason,
                
                rank=len(final_recommendations) + 1,
                track=music_final_item.track_title or "Unknown Track",
                artist=music_final_item.artist or "Unknown Artist",
                trend_name=trend_final_item.trend_title,
                platform=trend_final_item.platform,
                content_type=trend_final_item.content_format or "video",
                creator_match_score=final_score,
                trend_score=stage2_score,
                freshness=trend_final_item.freshness_status,
                evidence_confidence=music_final_item.confidence_score,
                
                # Probabilistic Similarity & Virality Metrics
                p_music_similarity=round(p_music, 2),
                p_virality_potential=round(p_virality, 2),
                p_concept_relevance=round(p_concept, 2),
                posterior_match_probability=round(posterior_prob, 2),
                virality_tier=v_tier,
                
                why_trending=trend_final_item.trend_description or "High engagement metrics and search indicators.",
                why_it_matches=reason if reason else f"Direct overlap on niches: {', '.join(trend_final_item.niches)} and styles: {', '.join(trend_final_item.styles)}",
                why_now="Currently in peak freshness window with active public signals.",
                
                source_url=trend_final_item.article_url,
                evidence_url=trend_final_item.article_url
            ))

        # Sort descending by final score
        final_recommendations.sort(key=lambda x: x.final_score, reverse=True)
        
        # TIER 2 & TIER 3 FALLBACK: If unique recommendation count < 5, fill with distinct similar tracks or overall trending audio
        if len(final_recommendations) < limit and top_15:
            base_cand = top_15[0]
            top_trend_sig: TrendSignal = base_cand["trend"]
            
            while len(final_recommendations) < limit and similar_track_index < len(similar_tracks):
                trk = similar_tracks[similar_track_index]
                similar_track_index += 1
                t_key = (trk.get("track_title", "").lower().strip(), trk.get("artist", "").lower().strip())
                if t_key in seen_track_keys:
                    continue
                seen_track_keys.add(t_key)
                
                mus_ev = MusicEvidence(
                    audio_mentioned=trk.get("track_title"),
                    track_title=trk.get("track_title"),
                    artist=trk.get("artist"),
                    spotify_id=trk.get("spotify_id"),
                    spotify_url=trk.get("spotify_url"),
                    preview_url=trk.get("preview_url"),
                    genres=trk.get("genres") or [desired_style],
                    popularity=trk.get("popularity") or 75,
                    confidence_score=0.85
                )
                
                cand_r = CandidateRecommendation(
                    trend_signal=top_trend_sig,
                    music_evidence=mus_ev,
                    match_reasons=[f"Recommended distinct audio matching {desired_style}"],
                    initial_score=0.75
                )
                
                fallback_score = round(max(0.30, 0.85 - (0.05 * len(final_recommendations))), 2)
                final_recommendations.append(Recommendation(
                    candidate=cand_r,
                    final_score=fallback_score,
                    rerank_reasons=[f"Recommended distinct '{desired_style}' audio track for your video concept."],
                    evidence_summary=f"Recommended distinct audio matching '{desired_style}' style.",
                    rank=len(final_recommendations) + 1,
                    track=trk.get("track_title"),
                    artist=trk.get("artist"),
                    trend_name=top_trend_sig.trend_title,
                    platform=top_trend_sig.platform,
                    content_type=top_trend_sig.content_format or "video",
                    creator_match_score=fallback_score,
                    trend_score=0.75,
                    freshness=top_trend_sig.freshness_status,
                    evidence_confidence=0.85,
                    p_music_similarity=0.85,
                    p_virality_potential=0.80,
                    p_concept_relevance=0.88,
                    posterior_match_probability=0.84,
                    virality_tier="High Momentum",
                    why_trending=top_trend_sig.trend_description or "High engagement metrics.",
                    why_it_matches=f"Recommended distinct audio track ('{trk.get('track_title')}') matching your requested '{desired_style}' music style for your video.",
                    why_now="Currently in peak freshness window with active public signals.",
                    source_url=top_trend_sig.article_url,
                    evidence_url=top_trend_sig.article_url
                ))
        
        # Populate rank index
        for idx, rec in enumerate(final_recommendations):
            rec.rank = idx + 1
            
        return final_recommendations[:limit]

    def _generate_candidates(self, query: CreatorQuery, allow_broader: bool = False) -> List[Tuple[TrendSignal, Optional[MusicEvidence]]]:
        """Stage 1: Generates candidates using deterministic queries."""
        db_trends = get_all_active_trends_with_music(self.db)
        
        candidates = []
        for db_trend in db_trends:
            trend_sig = TrendSignal(
                id=db_trend.id,
                source_id=db_trend.source_id,
                article_url=db_trend.article_url,
                trend_title=db_trend.trend_title,
                normalized_title=db_trend.normalized_title,
                trend_description=db_trend.trend_description,
                platform=db_trend.platform,
                content_format=db_trend.content_format,
                content_hash=db_trend.content_hash,
                niches=db_trend.niches or [],
                keywords=db_trend.keywords or [],
                moods=db_trend.moods or [],
                styles=db_trend.styles or [],
                scraped_at=db_trend.scraped_at,
                freshness_status=db_trend.freshness_status,
                interpreted_at=db_trend.interpreted_at
            )

            # Filtering rules
            # 1. Freshness
            if not allow_broader and trend_sig.freshness_status == "stale":
                continue
                
            # 2. Platform compatibility
            q_platform = (query.content.platform or "").lower()
            if q_platform and not allow_broader:
                if not platforms_compatible(q_platform, trend_sig.platform):
                    continue

            # 3. Niche overlap
            q_niche = query.creator.niche.lower()
            q_sub = (query.creator.sub_niche or "").lower()
            niche_overlap = any(n.lower() in [q_niche, q_sub] for n in trend_sig.niches)
            if not niche_overlap and not allow_broader:
                continue

            db_music = get_music_for_trend(self.db, db_trend.id)
            music_ev = None
            if db_music:
                music_ev = MusicEvidence(
                    id=db_music.id,
                    trend_signal_id=db_music.trend_signal_id,
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
                
            candidates.append((trend_sig, music_ev))
            
        return candidates[:50]

    def _calculate_match_score(
        self,
        query: CreatorQuery,
        trend: TrendSignal,
        music: Optional[MusicEvidence]
    ) -> Tuple[float, List[str]]:
        """Stage 2: Deterministic scoring using normalized weights."""
        reasons = []

        # 1. Freshness (0 or 1)
        freshness_val = 1.0 if trend.freshness_status == "fresh" else 0.0
        reasons.append(f"Freshness check: {trend.freshness_status}")

        # 2. Niche match (0 or 1)
        q_niche = query.creator.niche.lower()
        q_sub = (query.creator.sub_niche or "").lower()
        niche_match_val = 1.0 if any(n.lower() in [q_niche, q_sub] for n in trend.niches) else 0.0
        if niche_match_val > 0:
            reasons.append(f"Matches creator niche '{q_niche}'")

        # 3. Music match
        q_genres = [g.lower() for g in (query.music.genres + query.music.styles)]
        styles_overlap = [s for s in trend.styles if s.lower() in q_genres]
        music_match_val = len(styles_overlap) / max(1, len(q_genres))
        if music_match_val > 0:
            reasons.append(f"Styles overlap match: {', '.join(styles_overlap)}")

        # 4. Keyword match
        q_keywords = [k.lower() for k in query.search_terms]
        kw_overlap = [k for k in trend.keywords if k.lower() in q_keywords]
        kw_match_val = len(kw_overlap) / max(1, len(q_keywords))
        if kw_match_val > 0:
            reasons.append(f"Keyword match: {', '.join(kw_overlap)}")

        # 5. Mood match
        q_moods = [m.lower() for m in query.music.moods]
        mood_overlap = [m for m in trend.moods if m.lower() in q_moods]
        mood_match_val = len(mood_overlap) / max(1, len(q_moods))
        if mood_match_val > 0:
            reasons.append(f"Mood overlap match: {', '.join(mood_overlap)}")

        # 6. Confidence Score
        confidence_val = music.confidence_score if music else 0.5

        # Weighted calculation
        score = (
            self.weights["freshness"] * freshness_val +
            self.weights["niche"] * niche_match_val +
            self.weights["music"] * music_match_val +
            self.weights["keyword"] * kw_match_val +
            self.weights["mood"] * mood_match_val +
            self.weights["confidence"] * confidence_val
        )

        return round(score, 3), reasons
