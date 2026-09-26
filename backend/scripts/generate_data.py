"""Synthetic provider generator.

Reads the reference CSVs in data/reference/ and writes data/generated/providers.csv and
data/generated/provider_conditions.csv. Output is byte-identical for the same seed (and
the same pinned Faker version).

Run from backend/:  python -m scripts.generate_data
"""

import csv
import math
import random
import statistics
from collections import Counter, defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from faker import Faker

from app.core.config import REPO_ROOT

DATA_DIR = REPO_ROOT / "data"
REFERENCE_DIR = DATA_DIR / "reference"
GENERATED_DIR = DATA_DIR / "generated"

RADIUS_MILES = 15.0
EARTH_RADIUS_MILES = 3958.8
MIN_CONDITIONS = 2
MAX_CONDITIONS = 5
SUBSPECIALTY_PROBABILITY = 0.4

ProviderRow = dict[str, Any]
ProviderConditionRow = dict[str, str]


@dataclass(frozen=True)
class SpecialtyProfile:
    # Relative share of providers (the weights sum to 100).
    weight: float
    # Rates for an average-skill provider (z = 0).
    complication_base: float
    readmission_base: float
    # Annual patients for a provider with average experience.
    volume_median: int
    subspecialties: tuple[str, ...]


SPECIALTY_PROFILES: dict[str, SpecialtyProfile] = {
    "primary-care": SpecialtyProfile(
        weight=25,
        complication_base=0.008,
        readmission_base=0.07,
        volume_median=2500,
        subspecialties=(
            "Geriatrics",
            "Sports Medicine",
            "Adolescent Medicine",
            "Preventive Medicine",
        ),
    ),
    "cardiology": SpecialtyProfile(
        weight=11,
        complication_base=0.035,
        readmission_base=0.12,
        volume_median=1800,
        subspecialties=(
            "Interventional Cardiology",
            "Electrophysiology",
            "Heart Failure",
            "Echocardiography",
        ),
    ),
    "orthopedics": SpecialtyProfile(
        weight=11,
        complication_base=0.045,
        readmission_base=0.06,
        volume_median=1600,
        subspecialties=("Sports Medicine", "Joint Replacement", "Spine Surgery", "Hand Surgery"),
    ),
    "psychiatry": SpecialtyProfile(
        weight=10,
        complication_base=0.003,
        readmission_base=0.09,
        volume_median=600,
        subspecialties=(
            "Child and Adolescent Psychiatry",
            "Addiction Psychiatry",
            "Geriatric Psychiatry",
        ),
    ),
    "dermatology": SpecialtyProfile(
        weight=8,
        complication_base=0.004,
        readmission_base=0.005,
        volume_median=3000,
        subspecialties=("Mohs Surgery", "Pediatric Dermatology", "Dermatopathology"),
    ),
    "gastroenterology": SpecialtyProfile(
        weight=8,
        complication_base=0.020,
        readmission_base=0.08,
        volume_median=1500,
        subspecialties=("Hepatology", "Inflammatory Bowel Disease", "Advanced Endoscopy"),
    ),
    "neurology": SpecialtyProfile(
        weight=7,
        complication_base=0.015,
        readmission_base=0.09,
        volume_median=1200,
        subspecialties=(
            "Epilepsy",
            "Movement Disorders",
            "Vascular Neurology",
            "Headache Medicine",
        ),
    ),
    "oncology": SpecialtyProfile(
        weight=7,
        complication_base=0.050,
        readmission_base=0.15,
        volume_median=450,
        subspecialties=("Hematologic Oncology", "Breast Oncology", "Thoracic Oncology"),
    ),
    "pulmonology": SpecialtyProfile(
        weight=7,
        complication_base=0.020,
        readmission_base=0.13,
        volume_median=1100,
        subspecialties=("Critical Care Medicine", "Sleep Medicine", "Interventional Pulmonology"),
    ),
    "endocrinology": SpecialtyProfile(
        weight=6,
        complication_base=0.008,
        readmission_base=0.06,
        volume_median=1400,
        subspecialties=("Diabetes", "Thyroid Disorders", "Obesity Medicine"),
    ),
}

PROVIDER_FIELDS = [
    "provider_key",
    "first_name",
    "last_name",
    "credential",
    "specialty",
    "subspecialty",
    "city",
    "state",
    "zip_code",
    "latitude",
    "longitude",
    "years_experience",
    "quality_score",
    "cost_index",
    "patient_volume",
    "complication_rate",
    "readmission_rate",
    "accepting_new_patients",
]
PROVIDER_CONDITION_FIELDS = ["provider_key", "condition_slug"]

# Fixed decimal places, so the CSVs don't depend on float repr details.
FLOAT_FORMATS = {
    "latitude": ".6f",
    "longitude": ".6f",
    "quality_score": ".1f",
    "cost_index": ".2f",
    "complication_rate": ".4f",
    "readmission_rate": ".4f",
}


@dataclass(frozen=True)
class City:
    name: str
    state: str
    latitude: float
    longitude: float
    zip_prefix: str
    population_weight: float


@dataclass(frozen=True)
class Reference:
    specialties: list[str]
    # Specialty slug -> condition slugs, in CSV order.
    conditions_by_specialty: dict[str, list[str]]
    cities: list[City]


def load_reference(reference_dir: Path = REFERENCE_DIR) -> Reference:
    specialties = [row["slug"] for row in _read_csv(reference_dir / "specialties.csv")]
    if set(specialties) != set(SPECIALTY_PROFILES):
        raise ValueError(
            "specialties.csv and SPECIALTY_PROFILES disagree: "
            f"{sorted(set(specialties) ^ set(SPECIALTY_PROFILES))}"
        )

    conditions_by_specialty: dict[str, list[str]] = {slug: [] for slug in specialties}
    for row in _read_csv(reference_dir / "conditions.csv"):
        for specialty in row["specialties"].split(";"):
            if specialty not in conditions_by_specialty:
                raise ValueError(
                    f"conditions.csv: {row['slug']!r} lists unknown specialty {specialty!r}"
                )
            conditions_by_specialty[specialty].append(row["slug"])
    for specialty, conditions in conditions_by_specialty.items():
        if len(conditions) < MAX_CONDITIONS:
            raise ValueError(
                f"{specialty!r} has {len(conditions)} conditions; need at least {MAX_CONDITIONS}"
            )

    cities = [
        City(
            name=row["name"],
            state=row["state"],
            latitude=float(row["latitude"]),
            longitude=float(row["longitude"]),
            zip_prefix=row["zip_prefix"],
            population_weight=float(row["population_weight"]),
        )
        for row in _read_csv(reference_dir / "cities.csv")
    ]
    return Reference(specialties, conditions_by_specialty, cities)


def generate(
    n_providers: int = 1500,
    seed: int = 42,
    reference_dir: Path = REFERENCE_DIR,
) -> tuple[list[ProviderRow], list[ProviderConditionRow]]:
    """Generate providers and their provider-condition links. Deterministic for a seed.

    Every provider has a latent skill z ~ N(0, 1). Quality rises with z; complication and
    readmission rates fall with it. Cost is drawn independently of z on purpose, so
    "cheap" and "good" are separate trade-offs in the ranking.
    """
    reference = load_reference(reference_dir)
    rng = random.Random(seed)
    fake = Faker("en_US")
    fake.seed_instance(seed)

    specialty_weights = [SPECIALTY_PROFILES[slug].weight for slug in reference.specialties]
    city_weights = [city.population_weight for city in reference.cities]

    providers: list[ProviderRow] = []
    provider_conditions: list[ProviderConditionRow] = []
    for i in range(1, n_providers + 1):
        key = f"P{i:05d}"
        specialty = rng.choices(reference.specialties, weights=specialty_weights)[0]
        profile = SPECIALTY_PROFILES[specialty]
        city = rng.choices(reference.cities, weights=city_weights)[0]
        latitude, longitude = _random_point_near(rng, city.latitude, city.longitude, RADIUS_MILES)

        z = rng.gauss(0, 1)
        years = _clamp(round(rng.gauss(16, 9)), 1, 45)
        subspecialty = (
            rng.choice(profile.subspecialties) if rng.random() < SUBSPECIALTY_PROBABILITY else None
        )

        providers.append(
            {
                "provider_key": key,
                "first_name": fake.first_name(),
                "last_name": fake.last_name(),
                "credential": "MD" if rng.random() < 0.9 else "DO",
                "specialty": specialty,
                "subspecialty": subspecialty,
                "city": city.name,
                "state": city.state,
                "zip_code": f"{city.zip_prefix}{rng.randrange(100):02d}",
                "latitude": latitude,
                "longitude": longitude,
                "years_experience": years,
                "quality_score": round(_clamp(72 + 10 * z + rng.gauss(0, 4), 30, 99), 1),
                "cost_index": round(_clamp(rng.lognormvariate(0, 0.18), 0.55, 1.6), 2),
                "patient_volume": round(
                    profile.volume_median * math.exp(0.01 * (years - 16) + rng.gauss(0, 0.4))
                ),
                "complication_rate": _skill_adjusted_rate(rng, profile.complication_base, z),
                "readmission_rate": _skill_adjusted_rate(rng, profile.readmission_base, z),
                "accepting_new_patients": rng.random() < 0.8,
            }
        )

        n_conditions = rng.randint(MIN_CONDITIONS, MAX_CONDITIONS)
        for condition in rng.sample(reference.conditions_by_specialty[specialty], n_conditions):
            provider_conditions.append({"provider_key": key, "condition_slug": condition})

    return providers, provider_conditions


def write_csvs(
    providers: list[ProviderRow],
    provider_conditions: list[ProviderConditionRow],
    out_dir: Path,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(out_dir / "providers.csv", PROVIDER_FIELDS, providers)
    _write_csv(out_dir / "provider_conditions.csv", PROVIDER_CONDITION_FIELDS, provider_conditions)


def within_specialty_correlations(providers: list[ProviderRow], x: str, y: str) -> dict[str, float]:
    """Pearson r of two fields, computed separately inside each specialty.

    Pooled correlations of rates are diluted by the large differences in base rates between
    specialties, so this is the number that shows the skill relationship.
    """
    by_specialty: dict[str, list[ProviderRow]] = defaultdict(list)
    for provider in providers:
        by_specialty[provider["specialty"]].append(provider)
    return {
        specialty: statistics.correlation([p[x] for p in rows], [p[y] for p in rows])
        for specialty, rows in sorted(by_specialty.items())
    }


def print_summary(providers: list[ProviderRow]) -> None:
    by_specialty: dict[str, list[float]] = defaultdict(list)
    for provider in providers:
        by_specialty[provider["specialty"]].append(provider["quality_score"])

    print(f"\n{'Specialty':<18}{'Providers':>10}{'Mean quality':>14}")
    for specialty, scores in sorted(by_specialty.items(), key=lambda item: -len(item[1])):
        print(f"{specialty:<18}{len(scores):>10}{statistics.fmean(scores):>14.1f}")

    print(f"\n{'State':<18}{'Providers':>10}")
    for state, count in Counter(p["state"] for p in providers).most_common():
        print(f"{state:<18}{count:>10}")

    quality = [p["quality_score"] for p in providers]
    complications = [p["complication_rate"] for p in providers]
    cost = [p["cost_index"] for p in providers]
    within = within_specialty_correlations(providers, "quality_score", "complication_rate")
    correlations = {
        "quality vs complications, pooled Pearson": statistics.correlation(quality, complications),
        "quality vs complications, pooled Spearman": statistics.correlation(
            quality, complications, method="ranked"
        ),
        "quality vs complications, within specialty": statistics.fmean(within.values()),
        "quality vs cost_index, pooled Pearson": statistics.correlation(quality, cost),
    }
    print("\nCorrelations (within specialty = mean of per-specialty Pearson r)")
    for label, r in correlations.items():
        print(f"  {label:<44}{r:+.3f}")


def main() -> None:
    providers, provider_conditions = generate()
    write_csvs(providers, provider_conditions, GENERATED_DIR)
    print(
        f"Wrote {len(providers)} providers and {len(provider_conditions)} "
        f"provider-condition links to {GENERATED_DIR}"
    )
    print_summary(providers)


def _clamp[T: (int, float)](value: T, low: T, high: T) -> T:
    return max(low, min(high, value))


def _skill_adjusted_rate(rng: random.Random, base: float, z: float) -> float:
    return round(_clamp(base * math.exp(-0.3 * z + rng.gauss(0, 0.15)), 0.0, 0.5), 4)


def _random_point_near(
    rng: random.Random, latitude: float, longitude: float, radius_miles: float
) -> tuple[float, float]:
    """A point uniformly distributed over the disc of the given radius around a center.

    sqrt() on the distance makes the density uniform over area rather than over radius
    (otherwise points would bunch up at the center).
    """
    angular_distance = radius_miles * math.sqrt(rng.random()) / EARTH_RADIUS_MILES
    bearing = rng.uniform(0, 2 * math.pi)
    lat1, lon1 = math.radians(latitude), math.radians(longitude)
    # Great-circle destination point, so haversine distance back to the center is exact.
    lat2 = math.asin(
        math.sin(lat1) * math.cos(angular_distance)
        + math.cos(lat1) * math.sin(angular_distance) * math.cos(bearing)
    )
    lon2 = lon1 + math.atan2(
        math.sin(bearing) * math.sin(angular_distance) * math.cos(lat1),
        math.cos(angular_distance) - math.sin(lat1) * math.sin(lat2),
    )
    return round(math.degrees(lat2), 6), round(math.degrees(lon2), 6)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _write_csv(path: Path, fields: Sequence[str], rows: Iterable[dict[str, Any]]) -> None:
    # Explicit "\n" line endings: the csv module defaults to "\r\n" on every OS.
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(fields)
        for row in rows:
            writer.writerow([_format(field, row[field]) for field in fields])


def _format(field: str, value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if field in FLOAT_FORMATS:
        return format(value, FLOAT_FORMATS[field])
    return str(value)


if __name__ == "__main__":
    main()
