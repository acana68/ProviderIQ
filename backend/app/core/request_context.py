from contextvars import ContextVar

# Set by RequestContextMiddleware for the duration of each request. Log lines and error
# bodies read it from here, so it never has to be passed around explicitly.
request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)


def get_request_id() -> str | None:
    return request_id_var.get()
