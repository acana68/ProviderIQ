import pytest

from app.core.rate_limit import SlidingWindowRateLimiter


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


def test_allows_up_to_limit_then_rejects(clock: FakeClock) -> None:
    limiter = SlidingWindowRateLimiter(limit=3, window_seconds=60, clock=clock)

    assert [limiter.hit("a") for _ in range(3)] == [None, None, None]
    assert limiter.hit("a") == 60


def test_keys_are_counted_separately(clock: FakeClock) -> None:
    limiter = SlidingWindowRateLimiter(limit=1, window_seconds=60, clock=clock)

    assert limiter.hit("a") is None
    assert limiter.hit("b") is None
    assert limiter.hit("a") is not None


def test_window_slides_instead_of_resetting(clock: FakeClock) -> None:
    limiter = SlidingWindowRateLimiter(limit=2, window_seconds=60, clock=clock)
    limiter.hit("a")  # t=0
    clock.now += 30
    limiter.hit("a")  # t=30

    clock.now += 20  # t=50: both still inside the window
    assert limiter.hit("a") == pytest.approx(10)  # the t=0 hit expires at t=60

    clock.now += 10  # t=60: the first hit has expired, the second hasn't
    assert limiter.hit("a") is None
    assert limiter.hit("a") == pytest.approx(30)


def test_rejected_requests_do_not_extend_the_block(clock: FakeClock) -> None:
    limiter = SlidingWindowRateLimiter(limit=1, window_seconds=60, clock=clock)
    limiter.hit("a")
    for _ in range(5):
        clock.now += 10
        limiter.hit("a")

    clock.now += 10  # 60s after the only accepted request
    assert limiter.hit("a") is None


def test_idle_clients_are_forgotten(clock: FakeClock) -> None:
    limiter = SlidingWindowRateLimiter(limit=5, window_seconds=60, clock=clock)
    for i in range(100):
        limiter.hit(f"client-{i}")

    clock.now += 61
    limiter.hit("new-client")

    assert set(limiter._hits) == {"new-client"}
