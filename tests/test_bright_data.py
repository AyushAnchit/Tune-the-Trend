import pytest
from datetime import datetime, timedelta
from typing import Dict, Any, List
from tune_the_trend.config import settings
from tune_the_trend.services.scraper import (
    BrightDataClient,
    CollectorRunner,
    ScrapeHealthChecker,
    SelfHealingController
)
from tune_the_trend.db.repository import sync_sources


@pytest.fixture(autouse=True)
def enable_demo_mode():
    """Forces DEMO_MODE to True for testing scraper behaviors locally."""
    prev_demo = settings.DEMO_MODE
    prev_min_rec = settings.MIN_RECORDS_THRESHOLD
    settings.DEMO_MODE = True
    settings.MIN_RECORDS_THRESHOLD = 2
    yield
    settings.DEMO_MODE = prev_demo
    settings.MIN_RECORDS_THRESHOLD = prev_min_rec


def test_successful_scrape(test_db):
    client = BrightDataClient()
    client._demo_state = "healthy"
    
    runner = CollectorRunner(client)
    records = runner.run_collector("later_instagram", "c_mt47pfo62p9gw2puop")
    
    assert len(records) == 5
    assert records[0]["trend_title"] == "Espresso Dance Challenge"
    
    checker = ScrapeHealthChecker()
    is_healthy, coverages, reasons = checker.check_health(records)
    
    assert is_healthy is True
    assert coverages["trend_title"] == 1.0
    assert len(reasons) == 0


def test_empty_output():
    client = BrightDataClient()
    # Mock return value to be empty list
    def mock_results(response_id, source_id):
        return []
    client.get_job_results = mock_results
    
    runner = CollectorRunner(client)
    
    # Empty output from collector runner should raise a ValueError
    with pytest.raises(ValueError, match="completed but returned zero records"):
        runner.run_collector("later_instagram", "c_mt47pfo62p9gw2puop")
        
    # Check directly via HealthChecker
    checker = ScrapeHealthChecker()
    is_healthy, coverages, reasons = checker.check_health([])
    assert is_healthy is False
    assert "zero records" in reasons[0]


def test_schema_degradation():
    client = BrightDataClient()
    # Mock records with broken/missing trend_title
    def mock_results(response_id, source_id):
        return [
            {"trend_title": None, "article_url": "https://test.com/1", "trend_description": "A", "platform": "instagram"},
            {"trend_title": None, "article_url": "https://test.com/2", "trend_description": "B", "platform": "instagram"}
        ]
    client.get_job_results = mock_results
    
    runner = CollectorRunner(client)
    records = runner.run_collector("later_instagram", "c_mt47pfo62p9gw2puop")
    
    checker = ScrapeHealthChecker()
    is_healthy, coverages, reasons = checker.check_health(records)
    
    assert is_healthy is False
    assert coverages["trend_title"] == 0.0
    assert any("trend_title" in r and "coverage" in r for r in reasons)


def test_stale_output():
    client = BrightDataClient()
    stale_date = datetime.utcnow() - timedelta(days=20)
    
    # Mock records with stale date
    def mock_results(response_id, source_id):
        return [
            {"trend_title": "T1", "article_url": "https://test.com/1", "trend_description": "A", "platform": "instagram", "published_at": stale_date.isoformat()},
            {"trend_title": "T2", "article_url": "https://test.com/2", "trend_description": "B", "platform": "instagram", "published_at": stale_date.isoformat()}
        ]
    client.get_job_results = mock_results
    
    runner = CollectorRunner(client)
    records = runner.run_collector("later_instagram", "c_mt47pfo62p9gw2puop")
    
    checker = ScrapeHealthChecker()
    # Check with 24 hour threshold to guarantee staleness
    is_healthy, coverages, reasons = checker.check_health(records, expected_freshness_hours=24)
    
    assert is_healthy is False
    assert coverages["stale_percentage"] == 1.0
    assert any("stale" in r for r in reasons)


def test_self_healing_workflow_success(test_db):
    client = BrightDataClient()
    client._demo_state = "broken" # Starts broken
    
    runner = CollectorRunner(client)
    checker = ScrapeHealthChecker()
    controller = SelfHealingController(client, runner, checker)
    
    # Initial run is broken
    records = runner.run_collector("later_instagram", "c_mt47pfo62p9gw2puop")
    is_healthy, coverages, reasons = checker.check_health(records)
    assert is_healthy is False
    
    # Run self healing repair
    success = controller.handle_repair(
        db_session=test_db,
        collector_id="c_mt47pfo62p9gw2puop",
        source_id="later_instagram",
        records=records,
        reasons=reasons,
        coverages=coverages
    )
    
    assert success is True
    assert client._demo_state == "repaired"
    
    # Check DB logs
    from tune_the_trend.db.models import DBSelfHealingRun
    db_run = test_db.query(DBSelfHealingRun).filter(DBSelfHealingRun.collector_id == "c_mt47pfo62p9gw2puop").first()
    assert db_run is not None
    assert db_run.status == "completed"
    assert db_run.success is True
    assert db_run.validation_status == "healthy"


def test_self_healing_workflow_failure(test_db):
    client = BrightDataClient()
    client._demo_state = "broken"
    
    # Mock repair API check to fail
    def mock_check_repair_status(repair_job_id):
        return {"status": "failed", "success": False}
    client.check_self_healing_status = mock_check_repair_status
    
    runner = CollectorRunner(client)
    checker = ScrapeHealthChecker()
    controller = SelfHealingController(client, runner, checker)
    
    records = runner.run_collector("later_instagram", "c_mt47pfo62p9gw2puop")
    is_healthy, coverages, reasons = checker.check_health(records)
    
    # Repair should fail
    success = controller.handle_repair(
        db_session=test_db,
        collector_id="c_mt47pfo62p9gw2puop",
        source_id="later_instagram",
        records=records,
        reasons=reasons,
        coverages=coverages
    )
    
    assert success is False
    
    from tune_the_trend.db.models import DBSelfHealingRun
    db_run = test_db.query(DBSelfHealingRun).filter(DBSelfHealingRun.collector_id == "c_mt47pfo62p9gw2puop").first()
    assert db_run is not None
    assert db_run.status == "failed"
    assert db_run.success is False
