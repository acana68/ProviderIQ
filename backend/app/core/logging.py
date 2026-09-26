import json
import logging
import sys
from datetime import UTC, datetime

from app.core.request_context import get_request_id

_HANDLER_NAME = "provideriq-json"

# Attributes every LogRecord has. Anything else on a record came from `extra=`.
_STANDARD_RECORD_ATTRS = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__) | {
    "message",
    "asctime",
}


class JsonFormatter(logging.Formatter):
    """One JSON object per line, including request_id when logged during a request."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(
                timespec="milliseconds"
            ),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        request_id = get_request_id()
        if request_id is not None:
            payload["request_id"] = request_id
        for key, value in record.__dict__.items():
            if key not in _STANDARD_RECORD_ATTRS and not key.startswith("_"):
                payload[key] = value
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


class _StdoutHandler(logging.StreamHandler):
    """Looks up sys.stdout on every write instead of keeping the object from startup,
    so it keeps working when sys.stdout is swapped (e.g. by pytest's output capture)."""

    def emit(self, record: logging.LogRecord) -> None:
        self.stream = sys.stdout
        super().emit(record)


def configure_logging(level: str) -> None:
    """Send all logs to stdout as JSON. Safe to call more than once (e.g. once per test app).

    Only replaces the handler it installed itself, so handlers added by others (such as
    pytest's log capture) are left alone.
    """
    root = logging.getLogger()
    for handler in [h for h in root.handlers if h.get_name() == _HANDLER_NAME]:
        root.removeHandler(handler)
    handler = _StdoutHandler()
    handler.set_name(_HANDLER_NAME)
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)
    root.setLevel(level)

    # Uvicorn configures its own plain-text handlers before importing the app. Route its
    # logs through ours instead, and silence its access log: we write our own (see
    # RequestContextMiddleware), and uvicorn's includes the query string.
    for name in ("uvicorn", "uvicorn.error"):
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers.clear()
        uvicorn_logger.propagate = True
    logging.getLogger("uvicorn.access").disabled = True
