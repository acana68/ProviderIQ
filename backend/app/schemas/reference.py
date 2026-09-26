from pydantic import BaseModel, ConfigDict


class SpecialtySummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    name: str
    provider_count: int


class ConditionSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    name: str


class SpecialtyRef(BaseModel):
    """A specialty embedded in another resource."""

    model_config = ConfigDict(from_attributes=True)

    slug: str
    name: str


class ConditionRef(BaseModel):
    """A condition embedded in another resource."""

    model_config = ConfigDict(from_attributes=True)

    slug: str
    name: str
