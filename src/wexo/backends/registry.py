"""Route a bound runner to the builder for its placement.

All text placements use ``TinygradBuilder``. This fork has no image runtime.
"""

from wexo.shared.types.events import Event
from wexo.shared.types.tasks import TaskId
from wexo.shared.types.worker.instances import BoundInstance
from wexo.utils.channels import MpReceiver, MpSender
from wexo.worker.engines.base import Builder


def resolve_builder(
    bound_instance: BoundInstance,
    event_sender: MpSender[Event],
    cancel_receiver: MpReceiver[TaskId],
) -> Builder:
    """Construct the builder for ``bound_instance``.

    Tinygrad device selection happens inside ``TinygradBuilder`` and reads the
    per-node backend stored on ``TinygradInstance``. It does not inspect the
    operating system.

    Raises:
        ValueError: A Tinygrad placement refers to an image model, which this
            text-generation backend cannot run.
        TinygradDeviceSelectionError: The tinygrad package is missing. The
            runner entrypoint handles this by publishing
            ``RunnerTerminationError``.
    """
    if bound_instance.is_image_model:
        raise ValueError("This fork has no image runtime; only text generation is placed")

    instance = bound_instance.instance

    from wexo.backends.tinygrad_engine import (
        TinygradBuilder,
        tinygrad_device_name_for_backend,
    )

    device_name = tinygrad_device_name_for_backend(
        instance.backend_for_node(bound_instance.bound_node_id)
    )
    return TinygradBuilder(
        device_name=device_name,
        model_id=bound_instance.bound_shard.model_card.model_id,
        event_sender=event_sender,
        cancel_receiver=cancel_receiver,
    )
