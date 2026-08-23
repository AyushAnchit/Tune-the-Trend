def test_health_endpoint(api_client):
    res = api_client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok", "service": "tune_the_trend"}


def test_sources_endpoint(api_client):
    res = api_client.get("/sources")
    assert res.status_code == 200
    sources = res.json()
    assert len(sources) == 6
    source_ids = [s["source_id"] for s in sources]
    assert "later_instagram" in source_ids


def test_ingest_endpoint(api_client):
    # This runs the mock collectors since BRIGHT_DATA_API_TOKEN is blank/mock in tests env
    res = api_client.post("/ingest")
    assert res.status_code == 200
    stats = res.json()
    assert stats["status"] == "success"
    assert stats["processed_sources"] == 6
    assert "later_instagram" in stats["details"]
    assert stats["details"]["later_instagram"]["inserted"] == 5


def test_trends_list_endpoint(api_client):
    # Trigger ingest to populate some data
    api_client.post("/ingest")
    
    res = api_client.get("/trends")
    assert res.status_code == 200
    trends = res.json()
    assert len(trends) > 0
    # Inspect first item
    first_item = trends[0]
    assert "trend_signal" in first_item
    assert first_item["trend_signal"]["trend_title"] is not None


def test_recommend_endpoint(api_client):
    # Populate database first
    api_client.post("/ingest")
    
    payload = {
        "content_type": "reels",
        "niche": "dance",
        "desired_music_style": "upbeat pop",
        "description": "Sharing Espresso dance challenge clips."
    }
    
    res = api_client.post("/recommend", json=payload)
    assert res.status_code == 200
    recommendations = res.json()
    assert len(recommendations) > 0
    
    # Check structure
    rec = recommendations[0]
    assert "candidate" in rec
    assert "final_score" in rec
    assert "evidence_summary" in rec
    assert any(r["candidate"]["trend_signal"]["trend_title"] == "Espresso Dance Challenge" for r in recommendations)


def test_ingestion_runs_endpoint(api_client):
    # Trigger ingest first to create a run record
    api_client.post("/ingest")
    
    res = api_client.get("/ingestion/runs")
    assert res.status_code == 200
    runs = res.json()
    assert len(runs) > 0
    assert runs[0]["source_id"] == "later_instagram"
    assert runs[0]["status"] == "success"


def test_recommendations_audit_endpoint(api_client):
    # Trigger ingest and recommend to save recommendations
    api_client.post("/ingest")
    
    payload = {
        "content_type": "reels",
        "niche": "dance",
        "desired_music_style": "upbeat pop",
        "description": "Sharing Espresso dance challenge clips."
    }
    
    res = api_client.post("/recommend", json=payload)
    assert res.status_code == 200
    
    # Get profile audit recommendations (profile ID is 1 in test environment)
    res_audit = api_client.get("/recommendations/1")
    assert res_audit.status_code == 200
    audit_data = res_audit.json()
    assert len(audit_data) > 0
    assert audit_data[0]["creator_profile_id"] == 1
    
    # Asserting non-existent profile ID returns 404
    res_404 = api_client.get("/recommendations/9999")
    assert res_404.status_code == 404


def test_admin_self_heal_endpoint(api_client):
    # Trigger self-heal on active source
    res = api_client.post("/admin/self-heal/later_instagram")
    assert res.status_code == 200
    data = res.json()
    assert data["source_id"] == "later_instagram"
    assert data["self_healing_status"] == "repaired"
    
    # Non-existent source returns 404
    res_404 = api_client.post("/admin/self-heal/non_existent_source")
    assert res_404.status_code == 404
