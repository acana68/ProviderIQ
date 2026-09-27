from typing import cast

from fastapi import APIRouter

from app.api.deps import ReferenceRepo, SettingsDep
from app.schemas.dataset import DatasetInfo, DatasetSource
from app.services.dataset import describe_dataset

router = APIRouter(tags=["dataset"])


@router.get("/dataset", response_model=DatasetInfo)
def get_dataset(repo: ReferenceRepo, settings: SettingsDep) -> DatasetInfo:
    """Which dataset is loaded: synthetic demo data, or real CMS data for New Jersey.

    Read from what the seed script recorded, so it describes the data actually in the
    database. Only an unseeded database falls back to the DATA_SOURCE setting.
    """
    metadata = repo.get_dataset_metadata()
    if metadata is None:
        return describe_dataset(
            settings.data_source, as_of=None, vintage=None, has_conditions=repo.has_conditions()
        )
    return describe_dataset(
        # A CHECK constraint limits the column to the DatasetSource values.
        cast(DatasetSource, metadata.source),
        as_of=metadata.as_of,
        vintage=metadata.vintage,
        has_conditions=repo.has_conditions(),
    )
