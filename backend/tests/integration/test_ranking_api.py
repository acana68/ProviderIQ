from fastapi.testclient import TestClient

from app.services.ranking.weights import MIN_QUALITY_WEIGHT, PROFILES, Priority


def test_weights_are_the_engine_profiles(client: TestClient) -> None:
    response = client.get("/api/v1/ranking/weights")

    assert response.status_code == 200
    body = response.json()
    assert body == {
        "profiles": {
            priority.value: profile.model_dump() for priority, profile in PROFILES.items()
        },
        "min_quality_weight": MIN_QUALITY_WEIGHT,
    }


def test_weights_cover_every_priority_in_order(client: TestClient) -> None:
    profiles = client.get("/api/v1/ranking/weights").json()["profiles"]

    assert list(profiles) == [p.value for p in Priority]
    for weights in profiles.values():
        assert list(weights) == ["quality", "experience", "cost", "volume", "distance"]
        assert weights["quality"] >= 0.25
