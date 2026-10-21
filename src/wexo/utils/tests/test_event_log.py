from pathlib import Path

import msgspec
import pytest
import zstandard
from pydantic import ValidationError

from wexo.shared.types.events import TestEvent
from wexo.utils.disk_event_log import (
    _MAX_ARCHIVES,  # pyright: ignore[reportPrivateUsage]
    DiskEventLog,
    PersistedEventError,
)


@pytest.fixture
def log_dir(tmp_path: Path) -> Path:
    return tmp_path / "event_log"


def test_append_and_read_back(log_dir: Path):
    log = DiskEventLog(log_dir)
    events = [TestEvent() for _ in range(5)]
    for e in events:
        log.append(e)

    assert len(log) == 5

    result = list(log.read_all())
    assert len(result) == 5
    for original, restored in zip(events, result, strict=True):
        assert original.event_id == restored.event_id

    log.close()


def test_read_range(log_dir: Path):
    log = DiskEventLog(log_dir)
    events = [TestEvent() for _ in range(10)]
    for e in events:
        log.append(e)

    result = list(log.read_range(3, 7))
    assert len(result) == 4
    for i, restored in enumerate(result):
        assert events[3 + i].event_id == restored.event_id

    log.close()


def test_read_range_bounds(log_dir: Path):
    log = DiskEventLog(log_dir)
    events = [TestEvent() for _ in range(3)]
    for e in events:
        log.append(e)

    # Start beyond count
    assert list(log.read_range(5, 10)) == []
    # Negative start
    assert list(log.read_range(-1, 2)) == []
    # End beyond count is clamped
    result = list(log.read_range(1, 100))
    assert len(result) == 2

    log.close()


def test_empty_log(log_dir: Path):
    log = DiskEventLog(log_dir)
    assert len(log) == 0
    assert list(log.read_all()) == []
    assert list(log.read_range(0, 10)) == []
    log.close()


def _archives(log_dir: Path) -> list[Path]:
    return sorted(log_dir.glob("events.*.bin.zst"))


def test_rotation_on_close(log_dir: Path):
    log = DiskEventLog(log_dir)
    log.append(TestEvent())
    log.close()

    active = log_dir / "events.bin"
    assert not active.exists()

    archives = _archives(log_dir)
    assert len(archives) == 1
    assert archives[0].stat().st_size > 0


def test_rotation_on_construction_with_stale_file(log_dir: Path):
    log_dir.mkdir(parents=True, exist_ok=True)
    (log_dir / "events.bin").write_bytes(b"stale data")

    log = DiskEventLog(log_dir)
    archives = _archives(log_dir)
    assert len(archives) == 1
    assert archives[0].exists()
    assert len(log) == 0

    log.close()


def test_empty_log_no_archive(log_dir: Path):
    """Closing an empty log should not leave an archive."""
    log = DiskEventLog(log_dir)
    log.close()

    active = log_dir / "events.bin"

    assert not active.exists()
    assert _archives(log_dir) == []


def test_close_is_idempotent(log_dir: Path):
    log = DiskEventLog(log_dir)
    log.append(TestEvent())
    log.close()
    archive = _archives(log_dir)
    log.close()  # should not raise

    assert _archives(log_dir) == archive


def test_successive_sessions(log_dir: Path):
    """Simulate two master sessions: both archives should be kept."""
    log1 = DiskEventLog(log_dir)
    log1.append(TestEvent())
    log1.close()

    first_archive = _archives(log_dir)[-1]

    log2 = DiskEventLog(log_dir)
    log2.append(TestEvent())
    log2.append(TestEvent())
    log2.close()

    # Session 1 archive shifted to slot 2, session 2 in slot 1
    second_archive = _archives(log_dir)[-1]
    should_be_first_archive = _archives(log_dir)[-2]

    assert first_archive.exists()
    assert second_archive.exists()
    assert first_archive != second_archive
    assert should_be_first_archive == first_archive


def test_rotation_keeps_only_max_archives(log_dir: Path):
    """Only the most recent ``_MAX_ARCHIVES`` archives should remain."""
    total = _MAX_ARCHIVES + 2
    all_archives: list[Path] = []
    for _ in range(total):
        log = DiskEventLog(log_dir)
        log.append(TestEvent())
        log.close()
        all_archives.append(_archives(log_dir)[-1])

    for old in all_archives[:2]:
        assert not old.exists()
    for recent in all_archives[2:]:
        assert recent.exists()


def test_iter_persisted_across_sessions(log_dir: Path):
    """Persisted events from prior sessions are readable in chronological order."""
    first = DiskEventLog(log_dir)
    first_events = [TestEvent() for _ in range(3)]
    for event in first_events:
        first.append(event)
    first.close()

    second = DiskEventLog(log_dir)
    second_events = [TestEvent() for _ in range(2)]
    for event in second_events:
        second.append(event)

    persisted = list(second.iter_persisted())

    # 3 archived from the first session, then 2 from the active second session.
    assert [e.event_id for e in persisted] == [
        e.event_id for e in [*first_events, *second_events]
    ]
    second.close()


def test_iter_persisted_empty_log(log_dir: Path):
    log = DiskEventLog(log_dir)
    assert list(log.iter_persisted()) == []
    log.close()


def test_iter_persisted_snapshots_active_file(log_dir: Path):
    """Appending during iteration must not feed new events back into the replay."""
    log = DiskEventLog(log_dir)
    log.append(TestEvent())

    seen = 0
    for _event in log.iter_persisted():
        seen += 1
        log.append(TestEvent())  # would loop forever without a snapshot

    assert seen == 1
    log.close()


@pytest.mark.parametrize("filtered", [False, True])
@pytest.mark.parametrize(
    "record", [b"\x00\x01", b"\x00\x00\x00\x05abc", b"\x00\x00\x00\x01\xc1"]
)
def test_persisted_corruption_is_not_silently_skipped(
    log_dir: Path, record: bytes, filtered: bool
) -> None:
    log = DiskEventLog(log_dir)
    archive = log_dir / "events.2026-01-01.bin.zst"
    archive.write_bytes(zstandard.ZstdCompressor().compress(record))
    original = archive.read_bytes()
    try:
        with pytest.raises(PersistedEventError, match="record 0, byte 0"):
            list(log.iter_persisted(event_types=(TestEvent,) if filtered else None))
        assert archive.read_bytes() == original
    finally:
        log.close()


def test_unfiltered_history_still_validates_unselected_events(log_dir: Path) -> None:
    log = DiskEventLog(log_dir)
    payload = msgspec.msgpack.encode({"RetiredEvent": {"old_field": True}})
    archive = log_dir / "events.2026-01-01.bin.zst"
    archive.write_bytes(
        zstandard.ZstdCompressor().compress(len(payload).to_bytes(4, "big") + payload)
    )
    event = TestEvent()
    log.append(event)
    try:
        with pytest.raises(PersistedEventError) as caught:
            list(log.iter_persisted())
        assert isinstance(caught.value.__cause__, ValidationError)
        assert list(log.iter_persisted(event_types=(TestEvent,))) == [event]
        assert list(log.read_all()) == [event]
        assert list(log.read_range(0, 1)) == [event]
    finally:
        log.close()
