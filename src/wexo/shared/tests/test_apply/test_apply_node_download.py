from wexo.shared.apply import apply_node_download_progress
from wexo.shared.tests.conftest import get_pipeline_shard_metadata
from wexo.shared.types.common import NodeId
from wexo.shared.types.events import NodeDownloadProgress
from wexo.shared.types.memory import Memory
from wexo.shared.types.state import State
from wexo.shared.types.worker.downloads import DownloadCompleted
from wexo.worker.tests.constants import MODEL_A_ID, MODEL_B_ID


def test_apply_node_download_progress():
    state = State()
    shard1 = get_pipeline_shard_metadata(MODEL_A_ID, device_rank=0, world_size=2)
    event = DownloadCompleted(
        node_id=NodeId("node-1"),
        shard_metadata=shard1,
        total=Memory(),
    )

    new_state = apply_node_download_progress(
        NodeDownloadProgress(download_progress=event), state
    )

    assert new_state.downloads == {NodeId("node-1"): [event]}


def test_apply_two_node_download_progress():
    shard1 = get_pipeline_shard_metadata(MODEL_A_ID, device_rank=0, world_size=2)
    shard2 = get_pipeline_shard_metadata(MODEL_B_ID, device_rank=0, world_size=2)
    event1 = DownloadCompleted(
        node_id=NodeId("node-1"),
        shard_metadata=shard1,
        total=Memory(),
    )
    event2 = DownloadCompleted(
        node_id=NodeId("node-1"),
        shard_metadata=shard2,
        total=Memory(),
    )
    state = State(downloads={NodeId("node-1"): [event1]})

    new_state = apply_node_download_progress(
        NodeDownloadProgress(download_progress=event2), state
    )

    assert new_state.downloads == {NodeId("node-1"): [event1, event2]}
