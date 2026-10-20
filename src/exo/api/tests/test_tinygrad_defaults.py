from inspect import signature
from typing import cast

from exo.api.main import API
from exo.api.types.api import PlaceInstanceParams
from exo.shared.types.common import ModelId
from exo.shared.types.worker.instances import InstanceMeta


def test_place_instance_request_defaults_to_tinygrad() -> None:
    params = PlaceInstanceParams(model_id=ModelId("example/model"))
    assert params.instance_meta is InstanceMeta.Tinygrad


def test_placement_query_defaults_to_tinygrad() -> None:
    placement_parameter = cast(
        InstanceMeta, signature(API.get_placement).parameters["instance_meta"].default
    )
    assert placement_parameter is InstanceMeta.Tinygrad
