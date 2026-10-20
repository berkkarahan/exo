from enum import Enum
from typing import Annotated

from pydantic import BeforeValidator, Field, model_validator

from wexo.shared.models.model_cards import ModelTask
from wexo.shared.types.backends import Backend
from wexo.shared.types.common import Host, Id, NodeId
from wexo.shared.types.worker.runners import RunnerId, ShardAssignments, ShardMetadata
from wexo.utils.pydantic_ext import FrozenModel, TaggedModel


class InstanceId(Id):
    pass


def _backend_from_name(value: object) -> object:
    """Accept a backend name from placement-preview JSON.

    Raises:
        ValueError: Pydantic reports this as a validation error on the
            create-instance request when the name is not a backend.
    """
    if isinstance(value, str):
        return Backend(value)
    return value


BackendName = Annotated[Backend, BeforeValidator(_backend_from_name)]


class InstanceMeta(str, Enum):
    Tinygrad = "Tinygrad"


class BaseInstance(TaggedModel):
    instance_id: InstanceId
    shard_assignments: ShardAssignments

    def shard(self, runner_id: RunnerId) -> ShardMetadata | None:
        return self.shard_assignments.runner_to_shard.get(runner_id, None)


class TinygradInstance(BaseInstance):
    """Placement executed by the tinygrad adapter.

    ``device_backend_by_node`` records the backend selected for each node.
    The runner turns that backend into a tinygrad device name at startup.
    ``hosts_by_node`` is indexed by pipeline rank. A single-node instance
    leaves the map empty and does not open a socket.
    """

    # Placement previews serialize each backend as its name.
    device_backend_by_node: dict[NodeId, BackendName]
    hosts_by_node: dict[NodeId, list[Host]] = Field(default_factory=dict)
    ephemeral_port: int = 0

    def backend_for_node(self, node_id: NodeId) -> Backend:
        """Return the tinygrad backend selected for ``node_id``.

        Raises:
            ValueError: The runner entrypoint handles this by publishing
                ``RunnerTerminationError`` when the placement omitted the
                node that is starting the runner.
        """
        try:
            return self.device_backend_by_node[node_id]
        except KeyError as error:
            raise ValueError(
                f"Tinygrad instance {self.instance_id} has no backend for node {node_id}"
            ) from error


Instance = TinygradInstance


class BoundInstance(FrozenModel):
    instance: Instance
    bound_runner_id: RunnerId
    bound_node_id: NodeId

    @property
    def bound_shard(self) -> ShardMetadata:
        shard = self.instance.shard(self.bound_runner_id)
        assert shard is not None
        return shard

    @property
    def is_image_model(self) -> bool:
        return (
            ModelTask.TextToImage in self.bound_shard.model_card.tasks
            or ModelTask.ImageToImage in self.bound_shard.model_card.tasks
        )

    @model_validator(mode="after")
    def validate_shard_exists(self) -> "BoundInstance":
        assert (
            self.bound_runner_id in self.instance.shard_assignments.runner_to_shard
        ), (
            "Bound Instance must be constructed with a runner_id that is in the instances assigned shards"
        )
        return self
