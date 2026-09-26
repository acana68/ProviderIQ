from fastapi import APIRouter

from app.schemas.ranking import RankingWeightsResponse

router = APIRouter(prefix="/ranking", tags=["ranking"])


@router.get("/weights", response_model=RankingWeightsResponse)
def get_weights() -> RankingWeightsResponse:
    """The weight profile for each priority, and the floor no profile's quality weight goes
    below. Served from the engine's own PROFILES, so it can't drift from the rankings.

    These are the base weights. Without a location, a search drops distance and scales the
    others up to sum to 1 (see `weights_used` on a search response).
    """
    return RankingWeightsResponse.current()
