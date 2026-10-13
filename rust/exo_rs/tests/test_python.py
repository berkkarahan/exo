import asyncio
import os
import sys
from pathlib import Path

import pytest
from exo_rs import (
    NetworkingHandle,
    FromSwarm,
)


@pytest.mark.slow
@pytest.mark.asyncio
async def test_sleep_on_multiple_items() -> None:
    print("PYTHON: starting handle")
    h = NetworkingHandle.new(os.urandom(16).hex().lstrip("0"), 52414, 52413)
    print("PYTHON: handle started")

    rt = asyncio.create_task(_await_recv(h))

    # sleep for 4 ticks
    for i in range(10):
        await asyncio.sleep(1)

        await h.gossipsub_publish("topic", b"somehting or other")


@pytest.mark.skipif(sys.platform == "win32", reason="Pidfile is Unix-only")
def test_pidfile(tmp_path: Path) -> None:
    path = tmp_path / "lock.pid"
    scoped_lock_file(path)
    assert not path.exists()


async def _await_recv(h: NetworkingHandle):
    while True:
        event = await h.recv()
        match event:
            case FromSwarm.Connection() as c:
                print(f"PYTHON: connection update: {c}")
            case FromSwarm.Message() as m:
                print(f"PYTHON: message: {m}")


def scoped_lock_file(path: Path) -> None:
    from exo_rs import Pidfile

    Pidfile(str(path), 0o0600)


if __name__ == "__main__":
    asyncio.run(test_sleep_on_multiple_items())
