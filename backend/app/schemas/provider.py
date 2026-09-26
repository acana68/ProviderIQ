from typing import Self

from pydantic import BaseModel

from app.models import Provider
from app.schemas.reference import ConditionRef, SpecialtyRef


class ProviderSummary(BaseModel):
    id: int
    display_name: str
    specialty: SpecialtyRef
    subspecialty: str | None
    city: str
    state: str
    years_experience: int
    quality_score: float
    # 1.0 = regional average; lower is cheaper.
    cost_index: float
    accepting_new_patients: bool

    @classmethod
    def from_model(cls, provider: Provider) -> Self:
        """Build from a Provider whose specialty is already loaded."""
        return cls(**_summary_fields(provider))


class ProviderDetail(ProviderSummary):
    zip_code: str
    latitude: float
    longitude: float
    # Annual patients.
    patient_volume: int
    complication_rate: float
    readmission_rate: float
    conditions: list[ConditionRef]

    @classmethod
    def from_model(cls, provider: Provider) -> Self:
        """Build from a Provider whose specialty and conditions are already loaded."""
        return cls(
            **_summary_fields(provider),
            zip_code=provider.zip_code,
            latitude=provider.latitude,
            longitude=provider.longitude,
            patient_volume=provider.patient_volume,
            complication_rate=provider.complication_rate,
            readmission_rate=provider.readmission_rate,
            conditions=[
                ConditionRef.model_validate(condition)
                for condition in sorted(provider.conditions, key=lambda c: c.name)
            ],
        )


def _summary_fields(provider: Provider) -> dict[str, object]:
    return {
        "id": provider.id,
        "display_name": f"Dr. {provider.first_name} {provider.last_name}, {provider.credential}",
        "specialty": SpecialtyRef.model_validate(provider.specialty),
        "subspecialty": provider.subspecialty,
        "city": provider.city,
        "state": provider.state,
        "years_experience": provider.years_experience,
        "quality_score": provider.quality_score,
        "cost_index": provider.cost_index,
        "accepting_new_patients": provider.accepting_new_patients,
    }
