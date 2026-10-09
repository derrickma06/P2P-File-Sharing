# Neighbor management: will track interest, choke state, download rates, and pending requests, select preferred and optimistic neighbors at the configured intervals

from dataclasses import dataclass

from p2p.config import PeerInfo


@dataclass
class NeighborState:
    info: PeerInfo
    # Choking in each direction is independent, both start choked
    we_choke_neighbor: bool = True
    neighbor_chokes_us: bool = True
    we_are_interested: bool = False
    neighbor_is_interested: bool = False
