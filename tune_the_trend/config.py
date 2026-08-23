import logging
import json
import os
from typing import Any, Dict, List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

# Structured Logging Formatter
class StructuredFormatter(logging.Formatter):
    """
    Custom formatter to output logs in structured JSON format or clear key-value format.
    Ensures sensitive variables are never logged.
    """
    def format(self, record: logging.LogRecord) -> str:
        log_data: Dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "name": record.name,
            "message": record.getMessage(),
        }
        
        # Add extra fields if present
        if hasattr(record, "extra_fields") and isinstance(record.extra_fields, dict): # type: ignore
            # Redact common secret keys just in case
            redacted_fields = {}
            for k, v in record.extra_fields.items(): # type: ignore
                if any(sec in k.lower() for sec in ["key", "secret", "token", "password"]):
                    redacted_fields[k] = "[REDACTED]"
                else:
                    redacted_fields[k] = v
            log_data["extra"] = redacted_fields
            
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
            
        return json.dumps(log_data)


def setup_logging(level: str = "INFO") -> logging.Logger:
    """Sets up the structured logger."""
    logger = logging.getLogger("tune_the_trend")
    logger.setLevel(level)
    
    # Avoid duplicate handlers if re-called
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = StructuredFormatter(datefmt="%Y-%m-%dT%H:%M:%SZ")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        
    return logger


# Initialize base logger
logger = setup_logging()


class Settings(BaseSettings):
    """
    Application settings managed via environment variables and .env file.
    """
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    DATABASE_URL: str = Field(default="sqlite:///tune_the_trend.db", description="SQLite connection string")
    
    # Bright Data Scraper Studio Configuration
    BRIGHTDATA_API_KEY: str = Field(default="40728823-8535-4027-b6d4-19c404627b11", description="API token for Bright Data")
    LATER_COLLECTOR_ID: str = Field(default="c_mt47pfo62p9gw2puop", description="Collector ID for Later Instagram Trends")
    HOOTSUITE_COLLECTOR_ID: str = Field(default="c_mt4810w31jr2acer44", description="Collector ID for Hootsuite Social Trends")
    SHAZAM_COLLECTOR_ID: str = Field(default="c_mt43dtxopg54950h2", description="Collector ID for Shazam Charts")
    SHAZAM_URL: str = Field(default="https://www.shazam.com/charts/top-200/united-states", description="URL for Shazam Top 200 Charts")
    INCLUDE_SHAZAM_SECONDARY: bool = Field(default=True, description="Include Shazam as secondary audio source")
    HYPEM_COLLECTOR_ID: str = Field(default="c_mt2h6pz91yzzrb4q1c", description="Collector ID for HypeM Popular Tracks")
    HYPEM_LASTWEEK_COLLECTOR_ID: str = Field(default="c_mt2hi3z610som0x6qk", description="Collector ID for HypeM Last Week Popular Tracks")
    
    # Health check thresholds
    MIN_RECORDS_THRESHOLD: int = Field(default=5, description="Expected minimum records in a scrape")
    FIELD_COVERAGE_THRESHOLD: float = Field(default=0.8, description="Expected minimum coverage percentage (0.0 to 1.0) for critical fields")
    
    # Demo Mode
    DEMO_MODE: bool = Field(default=False, description="Simulate health states and self-healing response in demo/development")

    # LLM Settings
    LLM_PROVIDER: str = Field(default="mock", description="LLM provider: mock, openai, gemini, etc.")
    LLM_API_KEY: Optional[str] = Field(default=None, description="API key for LLM provider")
    LLM_MODEL: str = Field(default="mock-model", description="Model name to use")
    
    # Music Provider Settings
    MUSIC_PROVIDER: str = Field(default="mock", description="Music Metadata provider: mock, spotify, etc.")
    MUSIC_API_CLIENT_ID: Optional[str] = Field(default=None, description="Music API client ID")
    MUSIC_API_CLIENT_SECRET: Optional[str] = Field(default=None, description="Music API client secret")
    RAPIDAPI_KEY: Optional[str] = Field(default=None, description="RapidAPI Key for Deezer API")
    RAPIDAPI_HOST: str = Field(default="deezerdevs-deezer.p.rapidapi.com", description="RapidAPI Host for Deezer API")
    YOUTUBE_API_KEY: Optional[str] = Field(default=None, description="YouTube Data API v3 Key")
    
    # Freshness/Staleness threshold
    STALE_THRESHOLD_HOURS: int = Field(default=168, description="Threshold hours after which a record is stale")


settings = Settings()

# Source Registry definition
DEFAULT_SOURCES: List[Dict[str, Any]] = [
    {
        "source_id": "later_instagram",
        "name": "Later Instagram Reels Trends",
        "base_url": "https://later.com/blog/instagram-reels-trends/",
        "source_type": "blog",
        "platform_focus": "instagram",
        "collector_id": settings.LATER_COLLECTOR_ID,
        "enabled": True,
        "expected_freshness_hours": 168,
    },
    {
        "source_id": "hootsuite_social",
        "name": "Hootsuite Social Trends",
        "base_url": "https://www.hootsuite.com/research/social-trends",
        "source_type": "report",
        "platform_focus": "cross_platform",
        "collector_id": settings.HOOTSUITE_COLLECTOR_ID,
        "enabled": True,
        "expected_freshness_hours": 720,
    },
    {
        "source_id": "hootsuite_blog",
        "name": "Hootsuite Blog Social Media Trends",
        "base_url": "https://blog.hootsuite.com/social-media-trends/",
        "source_type": "blog",
        "platform_focus": "cross_platform",
        "collector_id": settings.HOOTSUITE_COLLECTOR_ID,
        "enabled": True,
        "expected_freshness_hours": 168,
    },
    {
        "source_id": "shazam_charts",
        "name": "Shazam Top 200 US Charts",
        "base_url": settings.SHAZAM_URL,
        "source_type": "chart",
        "platform_focus": "cross_platform",
        "collector_id": settings.SHAZAM_COLLECTOR_ID,
        "enabled": True,
        "expected_freshness_hours": 24,
    },
    {
        "source_id": "hypem_popular",
        "name": "Hype Machine Popular Now",
        "base_url": "https://hypem.com/popular",
        "source_type": "chart",
        "platform_focus": "cross_platform",
        "collector_id": settings.HYPEM_COLLECTOR_ID,
        "enabled": True,
        "expected_freshness_hours": 24,
    },
    {
        "source_id": "hypem_lastweek",
        "name": "Hype Machine Popular Last Week",
        "base_url": "https://hypem.com/popular/lastweek",
        "source_type": "chart",
        "platform_focus": "cross_platform",
        "collector_id": settings.HYPEM_LASTWEEK_COLLECTOR_ID,
        "enabled": True,
        "expected_freshness_hours": 168,
    }
]


def log_structured(msg: str, extra: Optional[Dict[str, Any]] = None, level: int = logging.INFO) -> None:
    """
    Helper to emit structured log records with key-value pairs, ignoring secrets.
    """
    record = logger.makeRecord(
        name=logger.name,
        level=level,
        fn="",
        lno=0,
        msg=msg,
        args=(),
        exc_info=None
    )
    if extra:
        record.extra_fields = extra # type: ignore
    logger.handle(record)
