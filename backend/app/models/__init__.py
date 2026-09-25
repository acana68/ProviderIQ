"""Every model is imported here so that `import app.models` registers all tables on
Base.metadata. Alembic autogenerate only sees tables that are registered."""

from app.models.city import City
from app.models.condition import Condition
from app.models.provider import Provider, provider_conditions
from app.models.search_log import SearchLog
from app.models.specialty import Specialty

__all__ = [
    "City",
    "Condition",
    "Provider",
    "SearchLog",
    "Specialty",
    "provider_conditions",
]
