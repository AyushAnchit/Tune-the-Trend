from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, model_validator


class SourceMetadata(BaseModel):
    """Metadata representing an external source (e.g., Later Blog, Hootsuite)."""
    source_id: str = Field(..., description="Unique identifier for the source")
    name: str = Field(..., description="Name of the source")
    base_url: str = Field(..., description="Base URL of the source website")
    source_type: str = Field(..., description="Type of source, e.g. blog, report")
    platform_focus: str = Field(..., description="Focus platform, e.g. instagram, cross_platform")
    collector_id: str = Field(..., description="Bright Data Collector ID associated with this source")
    enabled: bool = Field(default=True, description="Whether this source is currently active")
    expected_freshness_hours: int = Field(default=168, description="Expected maximum hours since last update")


class ArticleRecord(BaseModel):
    """Represents a raw scraped article's metadata."""
    source_id: str
    article_url: str
    article_title: str
    published_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    scraped_at: datetime


class RawTrendItem(BaseModel):
    """
    Represents a raw trend record extracted by the scraper.
    Matches the RAW SCRAPER SCHEMA fields.
    """
    source_id: str
    source_url: str
    article_url: str
    article_title: str
    published_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    scraped_at: datetime

    trend_title: str
    trend_description: Optional[str] = None
    platform: str
    content_format: Optional[str] = None

    niches: List[str] = Field(default_factory=list)
    keywords: List[str] = Field(default_factory=list)
    moods: List[str] = Field(default_factory=list)
    styles: List[str] = Field(default_factory=list)

    audio_mentioned: Optional[str] = None
    track_title: Optional[str] = None
    artist: Optional[str] = None
    example_url: Optional[str] = None
    evidence_text: Optional[str] = None


class RawScrapePayload(BaseModel):
    """A collection of RawTrendItems scraped in a single collector run."""
    source_id: str
    scraped_at: datetime
    items: List[RawTrendItem]


class TrendSignal(BaseModel):
    """
    Curated and structured trend intelligence representing processed trend items.
    """
    id: Optional[int] = None
    source_id: str
    article_url: str
    trend_title: str
    normalized_title: str
    trend_description: Optional[str] = None
    platform: str
    content_format: Optional[str] = None
    content_hash: Optional[str] = None
    
    niches: List[str] = Field(default_factory=list)
    keywords: List[str] = Field(default_factory=list)
    moods: List[str] = Field(default_factory=list)
    styles: List[str] = Field(default_factory=list)
    
    scraped_at: datetime
    freshness_status: str = Field(default="fresh", description="fresh or stale")
    interpreted_at: datetime = Field(default_factory=datetime.utcnow)
    
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class MusicEvidence(BaseModel):
    """
    Structured music candidate metadata linked to a specific TrendSignal.
    """
    id: Optional[int] = None
    trend_signal_id: Optional[int] = None
    audio_mentioned: Optional[str] = None
    track_title: Optional[str] = None
    artist: Optional[str] = None
    
    # Resolved metadata fields
    spotify_id: Optional[str] = None
    spotify_url: Optional[str] = None
    preview_url: Optional[str] = None
    genres: List[str] = Field(default_factory=list)
    popularity: Optional[int] = None
    
    # Audio features
    energy: Optional[float] = None
    tempo: Optional[float] = None
    valence: Optional[float] = None
    
    confidence_score: float = Field(default=1.0)
    
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class CreatorProfile(BaseModel):
    """
    Input received from a creator looking for audio/trend recommendations.
    Supports both compulsory and optional UI fields.
    """
    content_type: str = Field(..., description="Compulsory: short video or long-form video")
    niche: str = Field(..., description="Compulsory: Core content topic")
    desired_music: Optional[str] = Field(default=None, description="Compulsory: Preferred music style")
    desired_music_style: Optional[str] = Field(default=None, description="Legacy parameter for compatibility")
    
    platform: Optional[str] = Field(default=None, description="Optional target social platform")
    content_description: Optional[str] = Field(default=None, description="Optional video concept details")
    description: Optional[str] = Field(default=None, description="Legacy parameter for compatibility")
    audience: Optional[str] = Field(default=None, description="Optional target audience segment")
    extra_keywords: List[str] = Field(default_factory=list, description="Optional search keywords")

    @model_validator(mode="before")
    @classmethod
    def populate_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            # Music fields
            if "desired_music_style" in data and ("desired_music" not in data or data["desired_music"] is None):
                data["desired_music"] = data["desired_music_style"]
            elif "desired_music" in data and ("desired_music_style" not in data or data["desired_music_style"] is None):
                data["desired_music_style"] = data["desired_music"]
            # Description fields
            if "description" in data and ("content_description" not in data or data["content_description"] is None):
                data["content_description"] = data["description"]
            elif "content_description" in data and ("description" not in data or data["description"] is None):
                data["description"] = data["content_description"]
        return data

    @model_validator(mode="after")
    def check_music(self) -> "CreatorProfile":
        if not self.desired_music and not self.desired_music_style:
            raise ValueError("desired_music is a compulsory field")
        return self


# JOB B: Canonical Query Representation
class CreatorQueryContent(BaseModel):
    type: str
    platform: Optional[str] = None
    keywords: List[str] = Field(default_factory=list)


class CreatorQueryCreator(BaseModel):
    niche: str
    sub_niche: Optional[str] = None
    keywords: List[str] = Field(default_factory=list)


class CreatorQueryMusic(BaseModel):
    genres: List[str] = Field(default_factory=list)
    moods: List[str] = Field(default_factory=list)
    styles: List[str] = Field(default_factory=list)
    tempo: Optional[str] = None
    energy: Optional[str] = None


class CreatorQuery(BaseModel):
    """Structured query derived by LLM from CreatorProfile."""
    content: CreatorQueryContent
    creator: CreatorQueryCreator
    music: CreatorQueryMusic
    description: str
    search_terms: List[str] = Field(default_factory=list)
    negative_preferences: List[str] = Field(default_factory=list)

    # Legacy compatibility getters
    @property
    def target_platforms(self) -> List[str]:
        return [self.content.platform] if self.content.platform else []

    @property
    def target_niches(self) -> List[str]:
        return [self.creator.niche]

    @property
    def target_moods(self) -> List[str]:
        return self.music.moods

    @property
    def target_styles(self) -> List[str]:
        return self.music.styles

    @property
    def semantic_search_terms(self) -> List[str]:
        return self.search_terms


# JOB A: Canonical LLM Trend Signal Outputs
class MusicEvidenceExtraction(BaseModel):
    explicit_track: bool
    track_title: Optional[str] = None
    artist: Optional[str] = None
    audio_name: Optional[str] = None
    genre_clues: List[str] = Field(default_factory=list)
    mood_clues: List[str] = Field(default_factory=list)
    music_characteristics: List[str] = Field(default_factory=list)
    evidence_type: Optional[str] = Field(default=None, description="explicit or inferred")


class ExtractedTrendSignal(BaseModel):
    """Canonical trend signal extracted from scraper evidence."""
    trend_name: str
    platforms: List[str] = Field(default_factory=list)
    content_formats: List[str] = Field(default_factory=list)
    niches: List[str] = Field(default_factory=list)
    sub_niches: List[str] = Field(default_factory=list)
    keywords: List[str] = Field(default_factory=list)
    moods: List[str] = Field(default_factory=list)
    styles: List[str] = Field(default_factory=list)
    music_evidence: MusicEvidenceExtraction
    confidence: float = Field(default=1.0)


class CandidateRecommendation(BaseModel):
    """A matched trend signal and associated music evidence, before final reranking."""
    trend_signal: TrendSignal
    music_evidence: Optional[MusicEvidence] = None
    match_reasons: List[str] = Field(default_factory=list)
    initial_score: float = Field(default=0.0)


class Recommendation(BaseModel):
    """Final output recommendations with evidence summary and final reranked score."""
    candidate: CandidateRecommendation
    final_score: float
    rerank_reasons: List[str] = Field(default_factory=list)
    evidence_summary: str

    # Spec fields
    rank: int = 1
    track: Optional[str] = None
    artist: Optional[str] = None
    trend_name: str = ""
    platform: str = ""
    content_type: str = ""
    creator_match_score: float = 0.0
    trend_score: float = 0.0
    freshness: str = "fresh"
    evidence_confidence: float = 1.0
    
    # Probabilistic Similarity & Virality Metrics
    p_music_similarity: float = Field(default=0.85, description="Probability (0.0 to 1.0) that music matches creator audio request")
    p_virality_potential: float = Field(default=0.80, description="Probability (0.0 to 1.0) of trend audio going viral")
    p_concept_relevance: float = Field(default=0.90, description="Probability (0.0 to 1.0) that trend matches creator concept")
    posterior_match_probability: float = Field(default=0.88, description="Combined Bayesian posterior probability")
    virality_tier: str = Field(default="High Momentum", description="Virality probability tier")
    
    why_trending: str = ""
    why_it_matches: str = ""
    why_now: str = ""
    
    source_url: str = ""
    evidence_url: str = ""
