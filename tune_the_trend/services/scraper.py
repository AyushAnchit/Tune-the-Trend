import time
from datetime import datetime, timedelta
import httpx
from typing import Any, Dict, List, Optional, Tuple
from tune_the_trend.config import log_structured, settings
from tune_the_trend.models import RawTrendItem, RawScrapePayload
from tune_the_trend.services.validation import calculate_freshness


class BrightDataClient:
    """
    HTTP Client interacting with custom Bright Data Scraper Studio API.
    Supports real API integration and a simulation DEMO_MODE.
    """
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.BRIGHTDATA_API_KEY
        self.client = httpx.Client(timeout=30.0)
        
        # State tracker for DEMO_MODE simulation
        # Options: "healthy", "broken", "repaired"
        self._demo_state = "healthy"
        self._demo_job_counter = 0

    def trigger_collector(self, collector_id: str) -> str:
        """Triggers the collector. Returns job response_id."""
        if settings.DEMO_MODE or self.api_key == "mock-api" or not self.api_key:
            self._demo_job_counter += 1
            log_structured(
                f"Bright Data Client (Mock): Triggered collector {collector_id}",
                {"collector_id": collector_id, "demo_state": self._demo_state}
            )
            return f"job_demo_{collector_id}_{self._demo_job_counter}"

        # Real API request
        url = f"https://api.brightdata.com/dca/trigger"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        params = {"collector": collector_id}
        
        log_structured(
            f"Bright Data Client: Triggering collector {collector_id}",
            {"collector_id": collector_id}
        )
        res = self.client.post(url, headers=headers, params=params)
        res.raise_for_status()
        return res.json()["response_id"]

    def check_job_status(self, response_id: str) -> str:
        """Returns status of a collector job run (e.g. running, ready, failed)."""
        if settings.DEMO_MODE or response_id.startswith("job_demo_"):
            # Mock instant completion
            return "ready"
            
        url = f"https://api.brightdata.com/dca/status"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        params = {"response_id": response_id}
        
        res = self.client.get(url, headers=headers, params=params)
        res.raise_for_status()
        return res.json().get("status", "running")

    def get_job_results(self, response_id: str, source_id: str) -> List[Dict[str, Any]]:
        """Retrieves raw JSON results array for a completed collector job."""
        if settings.DEMO_MODE or response_id.startswith("job_demo_"):
            return self._get_simulated_payload(source_id)

        url = f"https://api.brightdata.com/dca/dataset"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        params = {"id": response_id}
        
        res = self.client.get(url, headers=headers, params=params)
        res.raise_for_status()
        
        raw_data = res.json()
        if isinstance(raw_data, list):
            return raw_data
        return raw_data.get("results", [])

    def trigger_self_healing(self, collector_id: str, diagnostic_prompt: str) -> str:
        """Triggers Bright Data's custom Scraper Studio Self-Healing API. Returns repair_job_id."""
        if settings.DEMO_MODE or self.api_key == "mock-api" or not self.api_key:
            log_structured(
                "Bright Data Client (Mock): Triggered Self-Healing API",
                {"collector_id": collector_id, "prompt_length": len(diagnostic_prompt)}
            )
            # Advance demo state to repaired after self-healing is triggered
            self._demo_state = "repaired"
            return f"repair_demo_{collector_id}"
            
        url = "https://api.brightdata.com/dca/self_heal"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "collector_id": collector_id,
            "diagnostic_prompt": diagnostic_prompt
        }
        
        res = self.client.post(url, headers=headers, json=payload)
        res.raise_for_status()
        return res.json()["repair_job_id"]

    def check_self_healing_status(self, repair_job_id: str) -> Dict[str, Any]:
        """Polls self-healing repair progress."""
        if settings.DEMO_MODE or repair_job_id.startswith("repair_demo_"):
            return {"status": "completed", "success": True}
            
        url = f"https://api.brightdata.com/dca/self_heal/status"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        params = {"repair_job_id": repair_job_id}
        
        res = self.client.get(url, headers=headers, params=params)
        res.raise_for_status()
        return res.json()

    def _get_simulated_payload(self, source_id: str) -> List[Dict[str, Any]]:
        """Simulates scraper results based on demo states."""
        now = datetime.utcnow()
        
        if self._demo_state == "healthy" or self._demo_state == "repaired":
            # 100% field coverage, fresh date
            if source_id == "later_instagram":
                return [
                    {
                        "source_url": "https://later.com/blog/instagram-reels-trends/",
                        "article_url": "https://later.com/blog/instagram-reels-trends/august-2026",
                        "article_title": "Instagram Reels Trends to Use in August 2026",
                        "published_at": (now - timedelta(hours=2)).isoformat() + "Z",
                        "updated_at": (now - timedelta(hours=1)).isoformat() + "Z",
                        "trend_title": "Espresso Dance Challenge",
                        "trend_description": "Creators sharing clips to Sabrina Carpenter's Espresso.",
                        "platform": "instagram",
                        "content_format": "reels",
                        "niches": ["lifestyle", "dance"],
                        "keywords": ["espresso", "dance"],
                        "moods": ["energetic"],
                        "styles": ["pop"],
                        "audio_mentioned": "Espresso by Sabrina Carpenter",
                        "track_title": "Espresso",
                        "artist": "Sabrina Carpenter",
                        "evidence_text": "Trending audio used in 100k+ reels."
                    },
                    {
                        "source_url": "https://later.com/blog/instagram-reels-trends/",
                        "article_url": "https://later.com/blog/instagram-reels-trends/august-2026",
                        "article_title": "Instagram Reels Trends to Use in August 2026",
                        "published_at": (now - timedelta(hours=4)).isoformat() + "Z",
                        "trend_title": "Aesthetic Cooking ASMR & Recipe Reel",
                        "trend_description": "Quick recipe clips featuring soothing lofi background music and cooking sound effects.",
                        "platform": "instagram",
                        "content_format": "reels",
                        "niches": ["cooking", "food"],
                        "keywords": ["cooking", "recipe", "foodie", "asmr"],
                        "moods": ["calm", "pleasant"],
                        "styles": ["lo-fi", "chill"],
                        "audio_mentioned": "Kitchen Lofi Beats",
                        "track_title": "Chill Cooking Lofi",
                        "artist": "Chef Beats",
                        "evidence_text": "Food Reels with chill beats show 45% higher save rates."
                    },
                    {
                        "source_url": "https://later.com/blog/instagram-reels-trends/",
                        "article_url": "https://later.com/blog/instagram-reels-trends/august-2026",
                        "article_title": "Instagram Reels Trends to Use in August 2026",
                        "published_at": (now - timedelta(hours=5)).isoformat() + "Z",
                        "trend_title": "Workout Transition & Gym Motivation",
                        "trend_description": "High energy fitness beat drop transitions showing before and after workouts.",
                        "platform": "instagram",
                        "content_format": "reels",
                        "niches": ["fitness", "health"],
                        "keywords": ["gym", "workout", "fitness", "motivation"],
                        "moods": ["high-energy", "inspiring"],
                        "styles": ["electronic", "edm", "pop"],
                        "audio_mentioned": "Pump Up Beat",
                        "track_title": "Gym Drop Energy",
                        "artist": "Fit Beats",
                        "evidence_text": "Fitness workout clips trending across short video platforms."
                    },
                    {
                        "source_url": "https://later.com/blog/instagram-reels-trends/",
                        "article_url": "https://later.com/blog/instagram-reels-trends/travel-spain",
                        "article_title": "Instagram Reels Trends for Travel Creators",
                        "published_at": (now - timedelta(hours=3)).isoformat() + "Z",
                        "trend_title": "Solo Travel Spain & Scenic Flamenco Reel",
                        "trend_description": "Scenic solo travel montages in Spain paired with Spanish flamenco acoustic guitar audio.",
                        "platform": "instagram",
                        "content_format": "reels",
                        "niches": ["travel", "lifestyle", "vacation"],
                        "keywords": ["travel", "spain", "flamenco", "solo", "scenic"],
                        "moods": ["passionate", "vibrant", "inspiring"],
                        "styles": ["flamenco", "spanish", "acoustic", "guitar"],
                        "audio_mentioned": "Spanish Flamenco Guitar",
                        "track_title": "Flamenco Guitar",
                        "artist": "Spanish Acoustic Ensemble",
                        "evidence_text": "Spanish travel Reels with authentic flamenco music see 60% higher engagement."
                    },
                    {
                        "source_url": "https://later.com/blog/instagram-reels-trends/",
                        "article_url": "https://later.com/blog/instagram-reels-trends/indian-classical-dance",
                        "article_title": "Instagram Reels Trends for Classical Dance Creators",
                        "published_at": (now - timedelta(hours=2)).isoformat() + "Z",
                        "trend_title": "Indian Classical Kathak & Sitar Fusion Reel",
                        "trend_description": "Traditional Indian classical Kathak and Bharatanatyam dance choreography set to sitar and tabla classical fusion beats.",
                        "platform": "instagram",
                        "content_format": "reels",
                        "niches": ["dance", "culture", "arts"],
                        "keywords": ["dance", "indian classical", "kathak", "bharatanatyam", "classical", "fusion"],
                        "moods": ["graceful", "expressive", "traditional"],
                        "styles": ["indian classical", "sitar", "tabla", "raga"],
                        "audio_mentioned": "Sitar Kathak Classical Fusion",
                        "track_title": "Kathak Sitar Fusion",
                        "artist": "Indian Classical Ensemble",
                        "evidence_text": "Classical Indian dance Reels with traditional sitar fusion audio see viral retention."
                    }
                ]
            elif source_id == "shazam_charts":
                return [
                    {
                        "source_url": "https://www.shazam.com/charts/top-200/united-states",
                        "article_url": "https://www.shazam.com/track/chart-top-1",
                        "article_title": "Shazam Top 200 US Chart #1",
                        "published_at": (now - timedelta(hours=1)).isoformat() + "Z",
                        "trend_title": "Die With A Smile Viral Skit Trend",
                        "trend_description": "Trending dramatic comedy skits & viral sound overlays on Shazam & TikTok.",
                        "platform": "cross_platform",
                        "content_format": "reels",
                        "niches": ["comedy", "entertainment"],
                        "keywords": ["shazam", "skit", "funny", "viral"],
                        "moods": ["funny", "dramatic"],
                        "styles": ["pop", "ballad"],
                        "audio_mentioned": "Die With A Smile by Lady Gaga & Bruno Mars",
                        "track_title": "Die With A Smile",
                        "artist": "Lady Gaga & Bruno Mars",
                        "evidence_text": "#1 Trending on Shazam US Top 200 with 1.2M Shazams."
                    },
                    {
                        "source_url": "https://www.shazam.com/charts/top-200/united-states",
                        "article_url": "https://www.shazam.com/track/chart-top-2",
                        "article_title": "Shazam Top 200 US Chart #2",
                        "published_at": (now - timedelta(hours=3)).isoformat() + "Z",
                        "trend_title": "Birds Of A Feather Aesthetic Edits",
                        "trend_description": "Uplifting lifestyle and comedy vlog background audio.",
                        "platform": "cross_platform",
                        "content_format": "video",
                        "niches": ["comedy", "lifestyle", "vlog"],
                        "keywords": ["billie", "feather", "vlog", "funny"],
                        "moods": ["cheerful", "upbeat"],
                        "styles": ["indie-pop", "chill"],
                        "audio_mentioned": "BIRDS OF A FEATHER by Billie Eilish",
                        "track_title": "BIRDS OF A FEATHER",
                        "artist": "Billie Eilish",
                        "evidence_text": "Top 5 Shazam trend audio used in comedy & lifestyle Reels."
                    }
                ]
            elif source_id in ["hypem_popular", "hypem_lastweek"]:
                return [
                    {
                        "source_url": "https://hypem.com/popular",
                        "article_url": "https://hypem.com/track/popular-1",
                        "article_title": "Hype Machine Popular #1 Track",
                        "published_at": (now - timedelta(hours=2)).isoformat() + "Z",
                        "trend_title": "Indie Pop Remix & Skit Sound",
                        "trend_description": "Trending HypeMachine blog audio used for funny comedy skits & outfit reels.",
                        "platform": "cross_platform",
                        "content_format": "reels",
                        "niches": ["comedy", "fashion", "lifestyle"],
                        "keywords": ["hypem", "indie", "remix", "funny"],
                        "moods": ["funny", "upbeat"],
                        "styles": ["indie-pop", "remix"],
                        "audio_mentioned": "360 by Charli xcx",
                        "track_title": "360",
                        "artist": "Charli xcx",
                        "evidence_text": "#1 Most blogged track on Hype Machine this week."
                    },
                    {
                        "source_url": "https://hypem.com/popular/lastweek",
                        "article_url": "https://hypem.com/track/popular-2",
                        "article_title": "Hype Machine Popular #2 Track",
                        "published_at": (now - timedelta(hours=6)).isoformat() + "Z",
                        "trend_title": "Electronic Dance Beat Drop Trend",
                        "trend_description": "High energy blog favorite for gaming, fitness, and comedy transitions.",
                        "platform": "cross_platform",
                        "content_format": "video",
                        "niches": ["comedy", "fitness", "gaming"],
                        "keywords": ["dance", "electronic", "hype", "funny"],
                        "moods": ["high-energy", "funny"],
                        "styles": ["electronic", "house"],
                        "audio_mentioned": "Guess by Charli xcx ft. Billie Eilish",
                        "track_title": "Guess featuring Billie Eilish",
                        "artist": "Charli xcx",
                        "evidence_text": "Top blogged remix on Hype Machine."
                    }
                ]
            else:
                return [
                    {
                        "source_url": "https://blog.hootsuite.com/social-media-trends/",
                        "article_url": "https://blog.hootsuite.com/social-media-trends/bts",
                        "article_title": "Bts Social Media Trends",
                        "published_at": (now - timedelta(hours=10)).isoformat() + "Z",
                        "trend_title": "Behind-the-Scenes & Setup Tours",
                        "trend_description": "Raw desk setup tours, gaming clips, and creator behind-the-scenes vlogs.",
                        "platform": "cross_platform",
                        "content_format": "video",
                        "niches": ["business", "tech", "gaming"],
                        "keywords": ["bts", "setup", "tech", "gaming"],
                        "moods": ["authentic", "engaging"],
                        "styles": ["vlog", "synthwave"],
                        "audio_mentioned": "Synthwave Ambient",
                        "track_title": "Neon Setup Wave",
                        "artist": "Synth Studio",
                        "evidence_text": "Tech and gaming desk setups see high engagement."
                    },
                    {
                        "source_url": "https://blog.hootsuite.com/social-media-trends/",
                        "article_url": "https://blog.hootsuite.com/social-media-trends/fashion-grwm",
                        "article_title": "Fashion GRWM Social Media Trends",
                        "published_at": (now - timedelta(hours=8)).isoformat() + "Z",
                        "trend_title": "Get Ready With Me (GRWM) Outfit Edits",
                        "trend_description": "Fast-cut fashion transitions with upbeat pop tracks.",
                        "platform": "cross_platform",
                        "content_format": "video",
                        "niches": ["fashion", "beauty", "lifestyle"],
                        "keywords": ["grwm", "outfit", "fashion", "style"],
                        "moods": ["stylish", "upbeat"],
                        "styles": ["pop", "dance-pop"],
                        "audio_mentioned": "Chic Pop Vibe",
                        "track_title": "Chic Runway Pop",
                        "artist": "Glam Audio",
                        "evidence_text": "GRWM videos remain top performing format."
                    }
                ]
                
        elif self._demo_state == "broken":
            # Low coverage of trend_title, 0% updated_at/published_at coverage, stale
            stale_date = now - timedelta(days=20) # Stale date
            return [
                {
                    "source_url": "https://later.com/blog/instagram-reels-trends/",
                    "article_url": "https://later.com/blog/instagram-reels-trends/august-2026",
                    "article_title": "Instagram Reels Trends to Use in August 2026",
                    "published_at": stale_date.isoformat() + "Z",
                    "updated_at": None,
                    "trend_title": None,  # Broken title
                    "trend_description": "Creators sharing clips to Sabrina Carpenter's Espresso.",
                    "platform": "instagram",
                },
                {
                    "source_url": "https://later.com/blog/instagram-reels-trends/",
                    "article_url": "https://later.com/blog/instagram-reels-trends/august-2026",
                    "article_title": "Instagram Reels Trends to Use in August 2026",
                    "published_at": None,
                    "trend_title": None,  # Broken title
                    "trend_description": "Relaxing morning routines with lofi beats.",
                    "platform": "instagram",
                }
            ]
            
        return []


class CollectorRunner:
    """
    Handles triggering Bright Data collectors, polling status,
    fetching dataset payloads, and recording logs.
    """
    def __init__(self, client: BrightDataClient):
        self.client = client

    def run_collector(self, source_id: str, collector_id: str) -> List[Dict[str, Any]]:
        """
        Triggers a collector run, polls until complete, and retrieves output.
        Fails if no output is returned.
        """
        started_at = datetime.utcnow()
        log_structured(
            f"Collector Runner: Initiating run",
            {"source_id": source_id, "collector_id": collector_id}
        )
        
        try:
            # 1. Trigger
            response_id = self.client.trigger_collector(collector_id)
            
            # 2. Poll Status
            status = "running"
            max_attempts = 30
            attempts = 0
            
            while status not in ["ready", "failed"] and attempts < max_attempts:
                attempts += 1
                time.sleep(0.5 if settings.DEMO_MODE else 2.0)
                status = self.client.check_job_status(response_id)
                
            if status != "ready":
                raise ValueError(f"Collector job failed or timed out. Final status: {status}")
                
            # 3. Retrieve
            results = self.client.get_job_results(response_id, source_id)
            
            if not results:
                raise ValueError("Collector run completed but returned zero records.")
                
            log_structured(
                f"Collector Runner: Execution complete",
                {
                    "source_id": source_id,
                    "collector_id": collector_id,
                    "started_at": started_at.isoformat(),
                    "completed_at": datetime.utcnow().isoformat(),
                    "record_count": len(results)
                }
            )
            return results
            
        except Exception as e:
            log_structured(
                f"Collector Runner: Execution failed",
                {"source_id": source_id, "error": str(e)},
                level=40
            )
            raise


class ScrapeHealthChecker:
    """
    Performs field coverage evaluations, schema verification, and freshness audits.
    """
    def check_health(
        self,
        records: List[Dict[str, Any]],
        expected_freshness_hours: int = settings.STALE_THRESHOLD_HOURS
    ) -> Tuple[bool, Dict[str, float], List[str]]:
        """
        Evaluates record quality, date freshness, and schemas.
        Returns: (is_healthy, field_coverages, list_of_reasons)
        """
        total_records = len(records)
        reasons = []
        coverages = {}
        
        # 1. Check zero records
        if total_records == 0:
            return False, {}, ["Collection contains zero records."]
            
        # 2. Check record count drop
        if total_records < settings.MIN_RECORDS_THRESHOLD:
            reasons.append(
                f"Record count {total_records} dropped below minimum threshold {settings.MIN_RECORDS_THRESHOLD}."
            )
            
        critical_fields = ["trend_title", "trend_description", "article_url", "platform"]
        
        # Calculate coverage percentages
        for field in critical_fields:
            valid_count = sum(
                1 for r in records if r.get(field) is not None and str(r.get(field)).strip() != ""
            )
            coverage = valid_count / total_records
            coverages[field] = round(coverage, 2)
            
            # 3. Required field coverage check
            if coverage < settings.FIELD_COVERAGE_THRESHOLD:
                reasons.append(
                    f"Critical field '{field}' coverage is {coverage*100:.0f}%, which is below threshold {settings.FIELD_COVERAGE_THRESHOLD*100:.0f}%."
                )

        # Date Coverage
        pub_count = sum(1 for r in records if r.get("published_at") is not None)
        upd_count = sum(1 for r in records if r.get("updated_at") is not None)
        date_coverage = (pub_count + upd_count) / total_records
        coverages["dates_coverage"] = round(date_coverage, 2)
        
        if date_coverage < 0.5:
            reasons.append(f"Date details coverage unexpectedly collapsed to {date_coverage*100:.0f}%.")

        # 4. Freshness check
        def parse_date(date_str):
            if not date_str:
                return None
            try:
                dt = datetime.fromisoformat(str(date_str).replace("Z", "+00:00"))
                return dt.replace(tzinfo=None)
            except ValueError:
                return None

        stale_records = 0
        scraped_at = datetime.utcnow()
        for r in records:
            pub_date = parse_date(r.get("published_at"))
            upd_date = parse_date(r.get("updated_at"))
            
            freshness = calculate_freshness(
                published_at=pub_date,
                updated_at=upd_date,
                scraped_at=scraped_at,
                threshold_hours=expected_freshness_hours
            )
            if freshness == "stale":
                stale_records += 1

        stale_percentage = stale_records / total_records
        coverages["stale_percentage"] = round(stale_percentage, 2)
        
        if stale_percentage == 1.0:
            reasons.append("All collected records are flagged as stale. Scraper may be fetching cached/outdated reports.")

        # Determine health state
        is_healthy = len(reasons) == 0
        return is_healthy, coverages, reasons


class SelfHealingController:
    """
    Coordinates diagnostic building, triggering Bright Data self-healing API repairs,
    polling progress, and verifying fixes against schema specifications.
    """
    def __init__(self, client: BrightDataClient, runner: CollectorRunner, health_checker: ScrapeHealthChecker):
        self.client = client
        self.runner = runner
        self.health_checker = health_checker

    def handle_repair(
        self,
        db_session: Any,
        collector_id: str,
        source_id: str,
        records: List[Dict[str, Any]],
        reasons: List[str],
        coverages: Dict[str, float]
    ) -> bool:
        """
        Builds diagnostics, triggers self-healing, polls status, runs validation check,
        and saves results to DB. Returns success boolean.
        """
        # 1. Create diagnostic prompt
        prompt = self._build_repair_prompt(source_id, records, reasons, coverages)
        
        log_structured(
            f"Self-Healing: Starting repair process for {collector_id}",
            {"collector_id": collector_id, "prompt": prompt}
        )
        
        # Insert run to DB
        from tune_the_trend.db.repository import create_self_healing_run, update_self_healing_run
        db_run = create_self_healing_run(
            db=db_session,
            collector_id=collector_id,
            diagnostic_prompt=prompt,
            repair_job_id="",
            status="pending"
        )
        
        try:
            # 2. Trigger Self-Healing
            repair_job_id = self.client.trigger_self_healing(collector_id, prompt)
            update_self_healing_run(db_session, db_run.id, status="running", repair_job_id=repair_job_id)
            
            # 3. Poll Self-Healing Progress
            status = "running"
            success = False
            max_attempts = 30
            attempts = 0
            
            while status not in ["completed", "failed"] and attempts < max_attempts:
                attempts += 1
                time.sleep(0.5 if settings.DEMO_MODE else 3.0)
                progress = self.client.check_self_healing_status(repair_job_id)
                status = progress.get("status", "running")
                success = progress.get("success", False)

            if status != "completed" or not success:
                error_msg = f"Self-healing API job failed or timed out. Final status: {status}, Success: {success}"
                update_self_healing_run(
                    db_session,
                    db_run.id,
                    status="failed",
                    success=False,
                    error_message=error_msg
                )
                return False
                
            # 4. Validation Run
            # Trigger runner on repaired collector in validation environment
            log_structured(
                f"Self-Healing: Scraper repaired. Initiating validation collection run",
                {"collector_id": collector_id}
            )
            
            try:
                validation_records = self.runner.run_collector(source_id, collector_id)
                
                # 5. Run Health Check on Validation Results
                is_valid, validation_coverages, validation_reasons = self.health_checker.check_health(validation_records)
                
                validation_status = "healthy" if is_valid else "unhealthy"
                
                # Update DB run
                update_self_healing_run(
                    db_session,
                    db_run.id,
                    status="completed",
                    repaired_at=datetime.utcnow(),
                    success=is_valid,
                    validation_status=validation_status,
                    error_message=None if is_valid else f"Validation run failed checks: {', '.join(validation_reasons)}"
                )
                
                if is_valid:
                    log_structured(
                        f"Self-Healing: Repair validated successfully. Production activation required via Bright Data UI.",
                        {"collector_id": collector_id}
                    )
                    return True
                else:
                    log_structured(
                        f"Self-Healing: Repair failed validation tests",
                        {"reasons": validation_reasons},
                        level=40
                    )
                    return False
                    
            except Exception as eval_err:
                update_self_healing_run(
                    db_session,
                    db_run.id,
                    status="completed",
                    success=False,
                    validation_status="error",
                    error_message=f"Validation run crashed: {str(eval_err)}"
                )
                return False
                
        except Exception as e:
            update_self_healing_run(
                db_session,
                db_run.id,
                status="failed",
                success=False,
                error_message=str(e)
            )
            return False

    def _build_repair_prompt(
        self,
        source_id: str,
        records: List[Dict[str, Any]],
        reasons: List[str],
        coverages: Dict[str, float]
    ) -> str:
        """Constructs the standard repair diagnostic prompt."""
        title_cov = int(coverages.get("trend_title", 0.0) * 100)
        date_cov = int(coverages.get("dates_coverage", 0.0) * 100)
        
        return (
            f"Collector {source_id} failed validation.\n\n"
            f"Observed:\n"
            f"- trend_title coverage: {title_cov}%\n"
            f"- date coverage (published/updated): {date_cov}%\n"
            f"- records: {len(records)}\n"
            f"- expected minimum: {settings.MIN_RECORDS_THRESHOLD}\n\n"
            f"Reasons for failure:\n"
            + "".join(f"- {r}\n" for r in reasons) +
            f"\nRequired fields:\n"
            f"trend_title\n"
            f"trend_description\n"
            f"article_url\n"
            f"scraped_at\n\n"
            f"The target page structure may have changed.\n"
            f"Repair the scraper so these fields are extracted from the current page structure.\n"
            f"Do not remove existing output fields.\n"
            f"Do not invent data.\n"
            f"Preserve the existing output schema."
        )


class BrightDataScraper:
    """
    Deprecated/Legacy compatibility layer wrapper (keeps imports functioning elsewhere).
    """
    def __init__(self, api_token: Optional[str] = None):
        self.client = BrightDataClient(api_token)
        self.runner = CollectorRunner(self.client)

    def trigger_and_collect(self, source_id: str, collector_id: str) -> RawScrapePayload:
        """Legacy helper directly parsing items."""
        raw_items_dict = self.runner.run_collector(source_id, collector_id)
        scraped_at = datetime.utcnow()
        
        from tune_the_trend.services.scraper import BrightDataClient
        parsed_items = []
        
        # Build raw items payload
        for rec in raw_items_dict:
            def parse_date(date_str):
                if not date_str:
                    return None
                try:
                    dt = datetime.fromisoformat(str(date_str).replace("Z", "+00:00"))
                    return dt.replace(tzinfo=None)
                except ValueError:
                    return None

            item = RawTrendItem(
                source_id=source_id,
                source_url=rec.get("source_url") or rec.get("article_url") or "",
                article_url=rec.get("article_url") or rec.get("source_url") or "",
                article_title=rec.get("article_title") or "Untitled Scrape",
                published_at=parse_date(rec.get("published_at")),
                updated_at=parse_date(rec.get("updated_at")),
                scraped_at=scraped_at,
                trend_title=rec.get("trend_title") or "Unknown Trend",
                trend_description=rec.get("trend_description"),
                platform=rec.get("platform") or "cross_platform",
                content_format=rec.get("content_format"),
                niches=rec.get("niches") or [],
                keywords=rec.get("keywords") or [],
                moods=rec.get("moods") or [],
                styles=rec.get("styles") or [],
                audio_mentioned=rec.get("audio_mentioned"),
                track_title=rec.get("track_title"),
                artist=rec.get("artist"),
                example_url=rec.get("example_url"),
                evidence_text=rec.get("evidence_text")
            )
            parsed_items.append(item)
            
        return RawScrapePayload(
            source_id=source_id,
            scraped_at=scraped_at,
            items=parsed_items
        )
