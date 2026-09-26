import pytest
from pydantic import ValidationError

from app.schemas.search import DEFAULT_RADIUS_MILES, ScoreContext, SearchRequest


def test_defaults() -> None:
    request = SearchRequest()

    assert request.radius_miles == DEFAULT_RADIUS_MILES
    assert request.priority == "balanced"
    assert request.sort == "match"
    assert (request.page, request.page_size, request.source) == (1, 20, "manual")


def test_location_is_normalized() -> None:
    request = SearchRequest.model_validate({"location": {"city": " New York ", "state": "ny"}})

    assert request.location is not None
    assert (request.location.city, request.location.state) == ("New York", "NY")


def test_explicit_radius_requires_location() -> None:
    with pytest.raises(ValidationError, match="radius_miles requires a location"):
        SearchRequest.model_validate({"radius_miles": 10})

    ok = SearchRequest.model_validate(
        {"radius_miles": 10, "location": {"city": "A", "state": "NY"}}
    )
    assert ok.radius_miles == 10


def test_unknown_fields_are_rejected() -> None:
    with pytest.raises(ValidationError):
        SearchRequest.model_validate({"specialty": "cardiology", "query": "free text"})


@pytest.mark.parametrize(
    "params",
    [{"city": "New York"}, {"state": "NY"}, {"radius_miles": 10}],
)
def test_score_context_needs_city_and_state_together(params: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        ScoreContext.model_validate(params)


def test_score_context_location() -> None:
    assert ScoreContext().location is None
    context = ScoreContext.model_validate({"city": "Boston", "state": "ma"})
    assert context.location is not None
    assert context.location.state == "MA"
