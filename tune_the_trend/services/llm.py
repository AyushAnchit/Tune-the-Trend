import json
import httpx
import hashlib
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple
from tune_the_trend.config import log_structured, settings
from tune_the_trend.models import (
    CreatorProfile,
    CreatorQuery,
    CreatorQueryContent,
    CreatorQueryCreator,
    CreatorQueryMusic,
    RawTrendItem,
    TrendSignal,
    MusicEvidence,
    ExtractedTrendSignal,
    MusicEvidenceExtraction
)


class ILLMProvider(ABC):
    """
    Interface for LLM Operations.
    """
    @abstractmethod
    def interpret_trend(self, raw_item: RawTrendItem) -> Tuple[Dict[str, Any], Optional[Dict[str, Any]]]:
        """Legacy helper for trend interpretation."""
        pass

    @abstractmethod
    def parse_creator_profile(self, profile: CreatorProfile) -> CreatorQuery:
        """Legacy helper for creator profile query parsing."""
        pass

    @abstractmethod
    def generate_evidence_summary(self, trend_title: str, trend_desc: str, music_title: Optional[str], artist: Optional[str], profile: CreatorProfile) -> str:
        """Generates evidence summary."""
        pass

    @abstractmethod
    def evaluate_semantic_relevance(self, trend_title: str, trend_desc: str, evidence_text: str, profile: CreatorProfile) -> Tuple[float, List[str]]:
        """Evaluates semantic matching multiplier."""
        pass

    # NEW API Layer Methods
    @abstractmethod
    def extract_trend_signal(self, raw_trend_item: RawTrendItem) -> ExtractedTrendSignal:
        """
        Job A: Raw structured scraper evidence -> canonical ExtractedTrendSignal Pydantic model.
        Includes validation, single-retry repair flow, and error catching.
        """
        pass

    @abstractmethod
    def parse_creator_input(self, creator_profile: CreatorProfile) -> CreatorQuery:
        """
        Job B: Creator profile input -> canonical CreatorQuery Pydantic model.
        """
        pass

    @abstractmethod
    def llm_rerank(self, query: CreatorQuery, candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Stage 4: LLM Reranking. Evaluates top candidate trends for query relevance.
        """
        pass


class MockLLMProvider(ILLMProvider):
    """
    Mock LLM Provider that runs rule-based heuristics on text inputs to return
    strictly formatted schemas without hitting an external API.
    """
    def interpret_trend(self, raw_item: RawTrendItem) -> Tuple[Dict[str, Any], Optional[Dict[str, Any]]]:
        # Legacy fallback
        raw_sig = self.extract_trend_signal(raw_item)
        trend_data = {
            "niches": raw_sig.niches,
            "keywords": raw_sig.keywords,
            "moods": raw_sig.moods,
            "styles": raw_sig.styles,
            "content_format": raw_sig.content_formats[0] if raw_sig.content_formats else "video",
        }
        music_data = None
        if raw_sig.music_evidence.explicit_track or raw_sig.music_evidence.audio_name:
            music_data = {
                "audio_mentioned": raw_sig.music_evidence.audio_name,
                "track_title": raw_sig.music_evidence.track_title,
                "artist": raw_sig.music_evidence.artist,
                "confidence_score": raw_sig.confidence
            }
        return trend_data, music_data

    def parse_creator_profile(self, profile: CreatorProfile) -> CreatorQuery:
        # Legacy fallback
        return self.parse_creator_input(profile)

    def generate_evidence_summary(self, trend_title: str, trend_desc: str, music_title: Optional[str], artist: Optional[str], profile: CreatorProfile) -> str:
        music_part = f" utilizing the track '{music_title}' by {artist}" if music_title else ""
        return (
            f"This trend '{trend_title}' matches your niche '{profile.niche}' on content format '{profile.content_type}'. "
            f"The trend involves: '{trend_desc}'. We suggest following this trend{music_part} "
            f"which aligns with your desired music preference of '{profile.desired_music}'."
        )

    def evaluate_semantic_relevance(self, trend_title: str, trend_desc: str, evidence_text: str, profile: CreatorProfile) -> Tuple[float, List[str]]:
        profile_words = set(f"{profile.niche} {profile.desired_music} {profile.content_description or ''}".lower().split())
        trend_words = set(f"{trend_title} {trend_desc or ''} {evidence_text or ''}".lower().split())
        
        stop_words = {"with", "that", "this", "your", "were", "have", "some", "more", "song", "music", "audio"}
        profile_words = {w.strip(".,!?\"'()[]{}") for w in profile_words if len(w) > 3 and w not in stop_words}
        trend_words = {w.strip(".,!?\"'()[]{}") for w in trend_words if len(w) > 3 and w not in stop_words}
        
        intersection = profile_words.intersection(trend_words)
        
        relevance_score = min(1.0, 0.2 + (len(intersection) * 0.2))
        
        reasons = []
        if intersection:
            reasons.append(f"Strong keyword alignment on: {', '.join(intersection)}")
        else:
            reasons.append("General stylistic relevance matching core descriptors")
            
        has_metrics = any(char.isdigit() for char in (evidence_text or ""))
        if has_metrics:
            relevance_score = min(1.0, relevance_score + 0.1)
            reasons.append("Evidence quality boosted by quantitative/scraped engagement metrics")
            
        return relevance_score, reasons

    # Job A: Mock Extractor
    def extract_trend_signal(self, raw_trend_item: RawTrendItem) -> ExtractedTrendSignal:
        text_context = f"{raw_trend_item.trend_title} {raw_trend_item.trend_description or ''} {raw_trend_item.evidence_text or ''}".lower()
        
        # Niches Heuristic
        niches = []
        if "fit" in text_context or "workout" in text_context:
            niches.append("fitness")
        if "cook" in text_context or "food" in text_context:
            niches.append("food & cooking")
        if "travel" in text_context:
            niches.append("travel")
        if "dance" in text_context:
            niches.append("dance")
        if not niches:
            niches.append("lifestyle")
            
        # Moods Heuristic
        moods = []
        if "chill" in text_context or "relax" in text_context or "lo-fi" in text_context or "lofi" in text_context or "soft" in text_context:
            moods.append("chill")
        if "hype" in text_context or "energetic" in text_context:
            moods.append("energetic")
        if not moods:
            moods.append("neutral")
            
        # Styles Heuristic
        styles = []
        if "lo-fi" in text_context or "lofi" in text_context:
            styles.append("lo-fi")
        if "pop" in text_context:
            styles.append("pop")
        if not styles:
            styles.append("upbeat")

        # Explicit song extraction
        explicit_track = False
        track_title = None
        artist = None
        
        if raw_trend_item.audio_mentioned:
            audio_lower = raw_trend_item.audio_mentioned.lower()
            if "original" not in audio_lower and " by " in audio_lower:
                parts = raw_trend_item.audio_mentioned.split(" by ")
                track_title = parts[0].strip()
                artist = parts[1].strip()
                explicit_track = True

        music_evidence = MusicEvidenceExtraction(
            explicit_track=explicit_track,
            track_title=track_title,
            artist=artist,
            audio_name=raw_trend_item.audio_mentioned or "Original Audio",
            genre_clues=styles,
            mood_clues=moods,
            music_characteristics=["low-bpm" if "lo-fi" in styles else "high-energy"],
            evidence_type="explicit" if explicit_track else "inferred"
        )
        
        return ExtractedTrendSignal(
            trend_name=raw_trend_item.trend_title,
            platforms=[raw_trend_item.platform],
            content_formats=[raw_trend_item.content_format or "reels"],
            niches=niches,
            sub_niches=[niches[0] + "_general"],
            keywords=raw_trend_item.keywords or ["trending"],
            moods=moods,
            styles=styles,
            music_evidence=music_evidence,
            confidence=0.9
        )

    # Job B: Mock Query Parser
    def parse_creator_input(self, creator_profile: CreatorProfile) -> CreatorQuery:
        text = f"{creator_profile.niche} {creator_profile.desired_music} {creator_profile.content_description or creator_profile.description or ''}".lower()
        
        # Target platform mapping
        platform = creator_profile.platform
        if not platform:
            ct = creator_profile.content_type.lower()
            if "reel" in ct:
                platform = "reels"
            elif "short" in ct:
                platform = "shorts"
            elif "tiktok" in ct:
                platform = "tiktok"
            else:
                platform = ct
                
        moods = []
        if "chill" in text or "relaxed" in text or "lo-fi" in text or "lofi" in text or "soft" in text:
            moods.append("chill")
        if "energetic" in text or "upbeat" in text or "hype" in text or "pop" in text:
            moods.append("energetic")
        if not moods:
            moods.append("neutral")
            
        styles = []
        if "lo-fi" in text or "lofi" in text:
            styles.append("lo-fi")
        if "pop" in text:
            styles.append("pop")
        if not styles:
            desired_music_str = creator_profile.desired_music or ""
            styles.extend([w for w in desired_music_str.lower().split() if len(w) > 3])

        content = CreatorQueryContent(
            type="short_video" if ("short" in creator_profile.content_type.lower() or "reel" in creator_profile.content_type.lower()) else "long_form_video",
            platform=platform,
            keywords=creator_profile.extra_keywords
        )
        
        creator = CreatorQueryCreator(
            niche=creator_profile.niche,
            sub_niche=creator_profile.niche + "_general",
            keywords=[creator_profile.niche.lower()]
        )
        
        music = CreatorQueryMusic(
            genres=styles,
            moods=moods,
            styles=styles,
            tempo="medium",
            energy="high" if "energetic" in moods else "medium"
        )
        
        desc = creator_profile.content_description if creator_profile.content_description is not None else (
            creator_profile.description if creator_profile.description is not None else "Default description"
        )
        desc_words = [w.strip(".,!?") for w in desc.lower().split() if len(w) > 4]
        search_terms = [creator_profile.niche.lower()] + styles + desc_words
        
        return CreatorQuery(
            content=content,
            creator=creator,
            music=music,
            description=desc,
            search_terms=search_terms,
            negative_preferences=[]
        )

    def llm_rerank(self, query: CreatorQuery, candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        results = []
        for cand in candidates:
            # Check overlap logic to generate a mockup score
            niche_overlap = any(n.lower() == query.creator.niche.lower() for n in cand.get("niches", []))
            relevance = 0.9 if niche_overlap else 0.4
            
            results.append({
                "candidate_id": str(cand.get("id", "")),
                "relevance": relevance,
                "evidence_quality": 0.85 if cand.get("freshness_status") == "fresh" else 0.4,
                "music_fit": 0.9 if query.music.moods and any(m in cand.get("moods", []) for m in query.music.moods) else 0.5,
                "reason": f"Mock Reranker matched candidate '{cand.get('trend_title')}' to niche '{query.creator.niche}'"
            })
        return results


class RealLLMProvider(ILLMProvider):
    """
    Real LLM Provider using OpenAI or Google Gemini REST API.
    Integrates Pydantic schema validation and repair-retry loops.
    """
    def __init__(self, provider: str, api_key: str, model: str):
        self.provider = provider
        self.api_key = api_key
        self.model = model
        self.client = httpx.Client(timeout=30.0)

    def interpret_trend(self, raw_item: RawTrendItem) -> Tuple[Dict[str, Any], Optional[Dict[str, Any]]]:
        # Implementation adapted to utilize the new extract_trend_signal method internally
        try:
            raw_sig = self.extract_trend_signal(raw_item)
            trend_data = {
                "niches": raw_sig.niches,
                "keywords": raw_sig.keywords,
                "moods": raw_sig.moods,
                "styles": raw_sig.styles,
                "content_format": raw_sig.content_formats[0] if raw_sig.content_formats else "video",
            }
            music_data = None
            if raw_sig.music_evidence.explicit_track or raw_sig.music_evidence.audio_name:
                music_data = {
                    "audio_mentioned": raw_sig.music_evidence.audio_name,
                    "track_title": raw_sig.music_evidence.track_title,
                    "artist": raw_sig.music_evidence.artist,
                    "confidence_score": raw_sig.confidence
                }
            return trend_data, music_data
        except Exception:
            return MockLLMProvider().interpret_trend(raw_item)

    def parse_creator_profile(self, profile: CreatorProfile) -> CreatorQuery:
        return self.parse_creator_input(profile)

    def generate_evidence_summary(self, trend_title: str, trend_desc: str, music_title: Optional[str], artist: Optional[str], profile: CreatorProfile) -> str:
        log_structured("LLM Call: Generating evidence summary", {"provider": self.provider, "model": self.model})
        
        prompt = (
            f"Generate a concise (1-2 sentences) creator-facing explanation on why they should join this trend.\n"
            f"Trend Title: {trend_title}\n"
            f"Trend Description: {trend_desc}\n"
            f"Music Title: {music_title} by {artist}\n"
            f"Creator Profile: Niche = {profile.niche}, Style = {profile.desired_music}\n"
            f"Explain how the trend and music align with their content concept. Do not include markdown headers."
        )
        
        try:
            return self._send_simple_text_prompt(prompt)
        except Exception as e:
            log_structured("LLM Failure: summary generation failed, using mock", {"error": str(e)}, level=40)
            return MockLLMProvider().generate_evidence_summary(trend_title, trend_desc, music_title, artist, profile)

    def evaluate_semantic_relevance(self, trend_title: str, trend_desc: str, evidence_text: str, profile: CreatorProfile) -> Tuple[float, List[str]]:
        log_structured("LLM Call: Evaluating semantic relevance", {"provider": self.provider, "model": self.model})
        
        prompt = (
            f"Evaluate the semantic relevance and evidence quality of this trend for the following creator profile.\n"
            f"Trend Title: {trend_title}\n"
            f"Trend Description: {trend_desc}\n"
            f"Scraped Evidence: {evidence_text}\n"
            f"Creator Profile:\n"
            f"- Niche: {profile.niche}\n"
            f"- Preferred Music Style: {profile.desired_music}\n"
            f"- Concept Description: {profile.content_description or 'None'}\n\n"
            f"Rate how well this trend and its evidence match the creator's focus.\n"
            f"Output JSON with EXACTLY this structure:\n"
            f"{{\n"
            f"  \"relevance_score\": 0.85, (float between 0.0 and 1.0)\n"
            f"  \"reasons\": [\"reason1\", \"reason2\"]\n"
            f"}}\n"
            f"Do not include any other text."
        )
        
        try:
            res_json = self._call_llm_api_json(prompt)
            score = float(res_json.get("relevance_score", 0.5))
            reasons = res_json.get("reasons", ["Matched semantic features"])
            return min(1.0, max(0.0, score)), reasons
        except Exception as e:
            log_structured("LLM Failure: relevance evaluation failed, using mock", {"error": str(e)}, level=40)
            return MockLLMProvider().evaluate_semantic_relevance(trend_title, trend_desc, evidence_text, profile)

    # Job A: Real Extractor with retries & repair
    def extract_trend_signal(self, raw_trend_item: RawTrendItem) -> ExtractedTrendSignal:
        log_structured(
            "LLM Call: Extracting trend signal (Job A)",
            {"source_id": raw_trend_item.source_id, "trend_title": raw_trend_item.trend_title}
        )
        
        # Bounded context: Cap evidence text to 4000 characters
        evidence = raw_trend_item.evidence_text or ""
        if len(evidence) > 4000:
            evidence = evidence[:4000] + "... [TRUNCATED]"

        prompt = (
            f"Analyze this raw scraped trend information. Extract structured trend intelligence matching the requested JSON schema.\n\n"
            f"Metadata:\n"
            f"Source: {raw_trend_item.source_id}\n"
            f"Article Title: {raw_trend_item.article_title}\n"
            f"Article URL: {raw_trend_item.article_url}\n\n"
            f"Trend Title: {raw_trend_item.trend_title}\n"
            f"Trend Description: {raw_trend_item.trend_description or 'N/A'}\n"
            f"Audio mentioned: {raw_trend_item.audio_mentioned or 'N/A'}\n"
            f"Evidence text excerpt: {evidence}\n\n"
            f"You MUST output JSON with EXACTLY this structure:\n"
            f"{{\n"
            f"  \"trend_name\": \"...\",\n"
            f"  \"platforms\": [\"...\"],\n"
            f"  \"content_formats\": [\"...\"],\n"
            f"  \"niches\": [\"...\"],\n"
            f"  \"sub_niches\": [\"...\"],\n"
            f"  \"keywords\": [\"...\"],\n"
            f"  \"moods\": [\"...\"],\n"
            f"  \"styles\": [\"...\"],\n"
            f"  \"music_evidence\": {{\n"
            f"      \"explicit_track\": false,\n"
            f"      \"track_title\": null,\n"
            f"      \"artist\": null,\n"
            f"      \"audio_name\": null,\n"
            f"      \"genre_clues\": [],\n"
            f"      \"mood_clues\": [],\n"
            f"      \"music_characteristics\": [],\n"
            f"      \"evidence_type\": \"explicit\" or \"inferred\" or null\n"
            f"  }},\n"
            f"  \"confidence\": 1.0\n"
            f"}}\n\n"
            f"Rules:\n"
            f"1. Distinguish between EXPLICIT EVIDENCE and INFERRED EVIDENCE.\n"
            f"2. If the source explicitly names a track, extract it and set explicit_track to true.\n"
            f"3. Otherwise, if you infer styles or moods, set explicit_track to false and fill in genre_clues/mood_clues/evidence_type.\n"
            f"4. Do not invent details. Output ONLY JSON."
        )

        try:
            # First attempt
            response_json = self._call_llm_api_json(prompt)
            return ExtractedTrendSignal(**response_json)
        except Exception as err:
            log_structured(
                "LLM Job A: First attempt validation failed, executing repair retry",
                {"error": str(err)},
                level=30 # WARNING
            )
            
            # Single retry with repair prompt
            repair_prompt = (
                f"Your previous response failed JSON schema validation with error: {str(err)}.\n"
                f"Please fix the schema formatting. Output ONLY a valid JSON object matching the schema.\n"
                f"Original raw details:\n"
                f"Trend: {raw_trend_item.trend_title}\n"
                f"Audio: {raw_trend_item.audio_mentioned}\n"
                f"Desc: {raw_trend_item.trend_description}"
            )
            
            try:
                repair_json = self._call_llm_api_json(repair_prompt)
                return ExtractedTrendSignal(**repair_json)
            except Exception as final_err:
                log_structured(
                    "LLM Job A: Repair retry validation failed. Raising error.",
                    {"error": str(final_err), "raw_input": raw_trend_item.trend_title},
                    level=40 # ERROR
                )
                raise ValueError(f"LLM Job A failed validation repair retry: {str(final_err)}")

    # Job B: Real Query Parser
    def parse_creator_input(self, creator_profile: CreatorProfile) -> CreatorQuery:
        log_structured(
            "LLM Call: Parsing creator query (Job B)",
            {"niche": creator_profile.niche}
        )
        
        prompt = (
            f"Convert this creator input profile into a structured query JSON.\n\n"
            f"Creator Profile:\n"
            f"Content Type: {creator_profile.content_type}\n"
            f"Niche: {creator_profile.niche}\n"
            f"Desired Music Style: {creator_profile.desired_music}\n"
            f"Platform: {creator_profile.platform or 'N/A'}\n"
            f"Description Concept: {creator_profile.content_description or 'None'}\n"
            f"Audience: {creator_profile.audience or 'N/A'}\n"
            f"Extra Keywords: {', '.join(creator_profile.extra_keywords)}\n\n"
            f"You MUST output JSON with EXACTLY this structure:\n"
            f"{{\n"
            f"  \"content\": {{\n"
            f"    \"type\": \"short_video\" or \"long_form_video\",\n"
            f"    \"platform\": \"...\",\n"
            f"    \"keywords\": []\n"
            f"  }},\n"
            f"  \"creator\": {{\n"
            f"    \"niche\": \"...\",\n"
            f"    \"sub_niche\": \"...\",\n"
            f"    \"keywords\": []\n"
            f"  }},\n"
            f"  \"music\": {{\n"
            f"    \"genres\": [],\n"
            f"    \"moods\": [],\n"
            f"    \"styles\": [],\n"
            f"    \"tempo\": \"slow\" or \"medium\" or \"fast\" or null,\n"
            f"    \"energy\": \"low\" or \"medium\" or \"high\" or null\n"
            f"  }},\n"
            f"  \"description\": \"...\",\n"
            f"  \"search_terms\": [],\n"
            f"  \"negative_preferences\": []\n"
            f"}}\n\n"
            f"Rules:\n"
            f"1. Derive sub-niche, moods, keywords, and music requirements from the description if present.\n"
            f"2. Do not invent features or tools (e.g. do not invent Valorant if the description says only 'gaming').\n"
            f"3. Output ONLY JSON."
        )

        try:
            response_json = self._call_llm_api_json(prompt)
            return CreatorQuery(**response_json)
        except Exception as e:
            log_structured("LLM Job B: Parser failed, falling back to mock", {"error": str(e)}, level=40)
            return MockLLMProvider().parse_creator_input(creator_profile)

    def llm_rerank(self, query: CreatorQuery, candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        log_structured(
            "LLM Call: Reranking candidates (Stage 4)",
            {"candidates_count": len(candidates)}
        )
        
        candidates_repr = []
        for cand in candidates:
            repr_item = {
                "candidate_id": str(cand.get("id")),
                "trend_name": cand.get("trend_title"),
                "niche": cand.get("niches"),
                "platform": cand.get("platform"),
                "format": cand.get("content_format"),
                "mood": cand.get("moods"),
                "music_characteristics": cand.get("styles"),
                "track": cand.get("track_title"),
                "artist": cand.get("artist"),
                "source": cand.get("source_id"),
                "scraped_at": str(cand.get("scraped_at")),
                "evidence_excerpt": cand.get("trend_description")
            }
            candidates_repr.append(repr_item)
            
        prompt = (
            f"You are the Tune the Trend AI probabilistic inference engine. Compute probabilistic similarity and virality metrics for candidate trend signals.\n\n"
            f"CREATOR VIDEO PROJECT REQUIREMENTS:\n"
            f"- Primary Niche: {query.creator.niche} (Sub-niche: {query.creator.sub_niche or 'N/A'})\n"
            f"- Target Video Format/Platform: {query.content.type} ({query.content.platform or 'Cross-Platform'})\n"
            f"- Desired Music Style & Mood: Genres/Styles: {', '.join(query.music.genres + query.music.styles)} | Moods: {', '.join(query.music.moods)}\n"
            f"- Video Concept & Description: \"{query.description or 'N/A'}\"\n"
            f"- Key Search Intent Terms: {', '.join(query.search_terms)}\n\n"
            f"CANDIDATES TO EVALUATE:\n"
            f"{json.dumps(candidates_repr, indent=2)}\n\n"
            f"PROBABILISTIC SCORING INSTRUCTIONS:\n"
            f"1. Evaluate p_music_similarity (0.0 to 1.0): Probability that the candidate audio matches creator requested music style, instruments, and mood. CRITICAL RULE: If the creator requested calm/instrumental/violin/piano/acoustic, and the candidate track is upbeat pop, aggressive EDM, electronic bounce, or rap, you MUST rate p_music_similarity < 0.20.\n"
            f"2. Evaluate p_virality_potential (0.0 to 1.0): Probability that this trend audio has high algorithm momentum / virality potential.\n"
            f"3. Evaluate p_concept_relevance (0.0 to 1.0): Probability that this trend matches the creator's specific video concept & niche.\n"
            f"4. Assign virality_tier: 'Explosive Growth' (p_virality > 0.85), 'High Momentum' (p_virality > 0.70), or 'Steady Trend'.\n"
            f"5. Write a personalized 'reason' explaining the probabilistic match and viral tendency for this creator concept.\n"
            f"6. You MUST output a JSON list of objects matching EXACTLY this schema:\n"
            f"[\n"
            f"  {{\n"
            f"    \"candidate_id\": \"...\",\n"
            f"    \"p_music_similarity\": 0.94,\n"
            f"    \"p_virality_potential\": 0.88,\n"
            f"    \"p_concept_relevance\": 0.95,\n"
            f"    \"virality_tier\": \"Explosive Growth\",\n"
            f"    \"relevance\": 0.95,\n"
            f"    \"evidence_quality\": 0.88,\n"
            f"    \"music_fit\": 0.94,\n"
            f"    \"reason\": \"High probabilistic match (94% music similarity) for your solo travel reel in Spain...\"\n"
            f"  }}\n"
            f"]\n\n"
            f"Output ONLY valid JSON."
        )
        
        try:
            res_json = self._call_llm_api_json(prompt)
            if isinstance(res_json, list):
                return res_json
            elif isinstance(res_json, dict) and "results" in res_json:
                return res_json["results"]
            elif isinstance(res_json, dict) and "candidates" in res_json:
                return res_json["candidates"]
            return []
        except Exception as e:
            log_structured("LLM Rerank: Call failed, falling back to mock reranker", {"error": str(e)}, level=40)
            return MockLLMProvider().llm_rerank(query, candidates)

    def _send_simple_text_prompt(self, prompt: str) -> str:
        """Sends a simple prompt and returns text response."""
        if self.provider == "openai":
            headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
            payload = {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.7
            }
            res = self.client.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
            res.raise_for_status()
            return res.json()["choices"][0]["message"]["content"].strip()
            
        elif self.provider == "gemini":
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
            payload = {
                "contents": [{"parts": [{"text": prompt}]}]
            }
            res = self.client.post(url, json=payload)
            res.raise_for_status()
            return res.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
            
        else:
            raise ValueError(f"Unsupported provider: {self.provider}")

    def _call_llm_api_json(self, prompt: str) -> Dict[str, Any]:
        """Invokes LLM API requesting structured JSON output."""
        if self.provider == "openai":
            headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
            payload = {
                "model": self.model,
                "response_format": {"type": "json_object"},
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1
            }
            res = self.client.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
            res.raise_for_status()
            text = res.json()["choices"][0]["message"]["content"]
            return json.loads(text)
            
        elif self.provider == "gemini":
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "responseMimeType": "application/json"
                }
            }
            res = self.client.post(url, json=payload)
            res.raise_for_status()
            text = res.json()["candidates"][0]["content"]["parts"][0]["text"]
            return json.loads(text)
            
        else:
            raise ValueError(f"Unsupported provider: {self.provider}")


def get_llm_provider() -> ILLMProvider:
    """Factory retrieving configured LLM provider."""
    provider = settings.LLM_PROVIDER.lower()
    if provider == "mock" or not settings.LLM_API_KEY:
        return MockLLMProvider()
    return RealLLMProvider(
        provider=provider,
        api_key=settings.LLM_API_KEY,
        model=settings.LLM_MODEL
    )
