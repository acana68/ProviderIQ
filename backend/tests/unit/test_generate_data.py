import math
import statistics
from collections import defaultdict
from pathlib import Path

import pytest

from scripts.generate_data import (
    MAX_CONDITIONS,
    MIN_CONDITIONS,
    RADIUS_MILES,
    ProviderConditionRow,
    ProviderRow,
    generate,
    load_reference,
    within_specialty_correlations,
    write_csvs,
)

N_PROVIDERS = 500

GeneratedData = tuple[list[ProviderRow], list[ProviderConditionRow]]


@pytest.fixture(scope="module")
def generated() -> GeneratedData:
    return generate(n_providers=N_PROVIDERS, seed=42)


@pytest.fixture(scope="module")
def providers(generated: GeneratedData) -> list[ProviderRow]:
    return generated[0]


def _haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    a = (
        math.sin((phi2 - phi1) / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    )
    return 2 * 3958.8 * math.asin(math.sqrt(a))


def test_same_seed_gives_byte_identical_csvs(generated: GeneratedData, tmp_path: Path) -> None:
    again = generate(n_providers=N_PROVIDERS, seed=42)
    write_csvs(*generated, tmp_path / "a")
    write_csvs(*again, tmp_path / "b")

    assert again == generated
    for name in ("providers.csv", "provider_conditions.csv"):
        assert (tmp_path / "a" / name).read_bytes() == (tmp_path / "b" / name).read_bytes()


def test_different_seed_gives_different_output(generated: GeneratedData) -> None:
    assert generate(n_providers=N_PROVIDERS, seed=43) != generated


def test_provider_keys_are_unique_and_sequential(providers: list[ProviderRow]) -> None:
    assert [p["provider_key"] for p in providers] == [
        f"P{i:05d}" for i in range(1, N_PROVIDERS + 1)
    ]


def test_values_are_within_db_check_ranges(providers: list[ProviderRow]) -> None:
    for p in providers:
        assert p["credential"] in ("MD", "DO")
        assert 30 <= p["quality_score"] <= 99
        assert 0 <= p["complication_rate"] <= 0.5
        assert 0 <= p["readmission_rate"] <= 0.5
        assert 1 <= p["years_experience"] <= 45
        assert 0.55 <= p["cost_index"] <= 1.6
        assert p["patient_volume"] >= 0
        assert -90 <= p["latitude"] <= 90
        assert -180 <= p["longitude"] <= 180
        assert len(p["state"]) == 2
        assert len(p["zip_code"]) == 5 and p["zip_code"].isdigit()
        assert isinstance(p["accepting_new_patients"], bool)
        for field in ("first_name", "last_name", "city", "subspecialty"):
            assert p[field] is None or 0 < len(p[field]) <= 100


def test_providers_are_within_radius_of_their_city(providers: list[ProviderRow]) -> None:
    cities = {(c.name, c.state): c for c in load_reference().cities}
    for p in providers:
        city = cities[(p["city"], p["state"])]
        assert p["zip_code"].startswith(city.zip_prefix)
        distance = _haversine_miles(city.latitude, city.longitude, p["latitude"], p["longitude"])
        # Small tolerance for rounding coordinates to 6 decimals.
        assert distance <= RADIUS_MILES + 0.01


def test_every_provider_has_2_to_5_conditions_from_its_specialty(
    generated: GeneratedData,
) -> None:
    providers, provider_conditions = generated
    conditions_by_specialty = load_reference().conditions_by_specialty
    conditions_by_provider: dict[str, list[str]] = defaultdict(list)
    for link in provider_conditions:
        conditions_by_provider[link["provider_key"]].append(link["condition_slug"])

    assert set(conditions_by_provider) == {p["provider_key"] for p in providers}
    for p in providers:
        conditions = conditions_by_provider[p["provider_key"]]
        assert MIN_CONDITIONS <= len(conditions) <= MAX_CONDITIONS
        assert len(set(conditions)) == len(conditions)
        assert set(conditions) <= set(conditions_by_specialty[p["specialty"]])


@pytest.mark.parametrize("rate", ["complication_rate", "readmission_rate"])
def test_quality_is_clearly_negatively_correlated_with_rates(
    providers: list[ProviderRow], rate: str
) -> None:
    # Checked within each specialty: base rates differ ~15x between specialties, which
    # dilutes the pooled correlation, so the pooled check is deliberately looser.
    for specialty, r in within_specialty_correlations(providers, "quality_score", rate).items():
        assert r < -0.3, specialty

    pooled = statistics.correlation(
        [p["quality_score"] for p in providers],
        [p[rate] for p in providers],
        method="ranked",
    )
    assert pooled < -0.1


def test_quality_is_uncorrelated_with_cost(providers: list[ProviderRow]) -> None:
    r = statistics.correlation(
        [p["quality_score"] for p in providers], [p["cost_index"] for p in providers]
    )

    assert abs(r) < 0.15
