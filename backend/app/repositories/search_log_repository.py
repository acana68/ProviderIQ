from sqlalchemy.orm import Session

from app.models import SearchLog


class SearchLogRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(
        self,
        *,
        source: str,
        parser_used: str | None,
        specialty_id: int | None,
        state: str | None,
        priority: str,
        result_count: int,
        latency_ms: float,
    ) -> None:
        """Insert and commit one search_logs row. Rolls back and re-raises on failure.

        Takes only these fields on purpose: no query text and no condition is ever stored.
        """
        self.session.add(
            SearchLog(
                source=source,
                parser_used=parser_used,
                specialty_id=specialty_id,
                state=state,
                priority=priority,
                result_count=result_count,
                latency_ms=latency_ms,
            )
        )
        try:
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
