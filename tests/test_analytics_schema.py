import pytest
from src.api.schemas import (
    AnalyticsResponse,
    ReplayIdentity,
    HitCounts,
    PerformanceData,
    LifeBarEntry,
)


def test_analytics_response_schema():
    """
    Contract test for the AnalyticsResponse schema.
    Ensures that the JSON structure matches exactly what the frontend charting library expects.
    """

    identity = ReplayIdentity(
        username="TestUser",
        beatmap_hash="hash123",
        game_mode=0,
        mods=["HD", "DT"],
        mods_int=72,
        score=1000000,
        timestamp="2023-01-01T12:00:00Z",
    )

    hits = HitCounts(
        **{
            "300s": 100,
            "100s": 20,
            "50s": 5,
            "misses": 1,
            "gekis": 10,
            "katus": 5,
            "max_combo": 500,
        }
    )

    perf = PerformanceData(pp=150.5, star_rating=5.2)

    life = [LifeBarEntry(t=0, hp=1.0), LifeBarEntry(t=1000, hp=0.8)]

    resp = AnalyticsResponse(
        job_id="test-uuid",
        status="completed",
        has_analytics=True,
        identity=identity,
        hit_counts=hits,
        performance=perf,
        life_bar=life,
        frames_url="https://s3.example.com/frames.json.gz",
        frame_count=5000,
    )

    json_data = resp.model_dump(by_alias=True)

    # Assert top-level keys
    assert "job_id" in json_data
    assert "status" in json_data
    assert "has_analytics" in json_data
    assert "frames_url" in json_data

    # Assert nested identity
    assert json_data["identity"]["username"] == "TestUser"
    assert json_data["identity"]["game_mode"] == 0
    assert "timestamp" in json_data["identity"]

    # Assert hit counts are correctly mapped (testing alias bypass)
    assert json_data["hit_counts"]["300s"] == 100
    assert json_data["hit_counts"]["misses"] == 1

    # Assert performance
    assert json_data["performance"]["pp"] == 150.5
    assert json_data["performance"]["star_rating"] == 5.2

    # Assert life bar list of dicts
    assert len(json_data["life_bar"]) == 2
    assert json_data["life_bar"][0]["t"] == 0
    assert json_data["life_bar"][0]["hp"] == 1.0
