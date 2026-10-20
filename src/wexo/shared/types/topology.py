from collections.abc import Iterator
from dataclasses import dataclass

from wexo.shared.types.common import NodeId
from wexo.shared.types.multiaddr import Multiaddr
from wexo.utils.pydantic_ext import FrozenModel


@dataclass(frozen=True)
class Cycle:
    node_ids: list[NodeId]

    def __len__(self) -> int:
        return self.node_ids.__len__()

    def __iter__(self) -> Iterator[NodeId]:
        return self.node_ids.__iter__()


class RDMAConnection(FrozenModel):
    source_rdma_iface: str
    sink_rdma_iface: str


class SocketConnection(FrozenModel):
    sink_multiaddr: Multiaddr

    def __hash__(self):
        return hash(self.sink_multiaddr.ip_address)


class Connection(FrozenModel):
    source: NodeId
    sink: NodeId
    edge: RDMAConnection | SocketConnection
