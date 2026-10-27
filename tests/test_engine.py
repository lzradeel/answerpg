"""Unit tests for the Stopwatch that times each stage of a request."""

import time

import pytest

from answerpg.engine import Stopwatch


@pytest.fixture
def clock(monkeypatch):
    """Return a function that makes time.perf_counter hand out the given readings, in seconds."""

    def script(*readings: float) -> None:
        """Queue up the values perf_counter returns, one per call."""
        ticks = iter(readings)
        monkeypatch.setattr(time, "perf_counter", lambda: next(ticks))

    return script


@pytest.mark.parametrize(
    ("start", "stop", "expected_ms"),
    [
        (100.0, 100.0421789, 42.18),
        (5.0, 5.0015, 1.5),
        (0.0, 2.5, 2500.0),
        (3.0, 3.000004, 0.0),
    ],
)
def test_measure_stores_rounded_milliseconds(clock, start, stop, expected_ms):
    """A measured block is stored under its stage name in milliseconds, rounded to two places."""
    clock(start, stop)
    watch = Stopwatch()
    with watch.measure("semantic"):
        pass
    assert watch.elapsed_ms == {"semantic": expected_ms}


def test_measure_still_records_when_block_raises(clock):
    """A stage that blows up is timed all the same, and its exception still reaches the caller."""
    clock(1.0, 1.25)
    watch = Stopwatch()
    with pytest.raises(TimeoutError, match="no reply"):
        with watch.measure("compose"):
            raise TimeoutError("answer backend sent no reply")
    assert watch.elapsed_ms == {"compose": 250.0}


def test_nested_stages_get_separate_entries(clock):
    """A stage timed inside the overall total gets its own entry, the way the engine nests them."""
    clock(10.0, 10.002, 10.0065, 10.01)
    watch = Stopwatch()
    with watch.measure("total"):
        with watch.measure("encode"):
            pass
    assert watch.elapsed_ms == {"encode": 4.5, "total": 10.0}


def test_each_stopwatch_keeps_its_own_timings(clock):
    """Timings belong to the instance, so a new Stopwatch starts out empty."""
    clock(0.0, 0.003)
    first = Stopwatch()
    with first.measure("fusion"):
        pass
    assert first.elapsed_ms == {"fusion": 3.0}
    assert Stopwatch().elapsed_ms == {}
