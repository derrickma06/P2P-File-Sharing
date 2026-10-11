# Neighbor management: will track interest, choke state, download rates, and pending requests, select preferred and optimistic neighbors at the configured intervals

from dataclasses import dataclass, field

from p2p.config import PeerInfo


@dataclass
class NeighborState:
    info: PeerInfo
    # Choking in each direction is independent, both start choked
    we_choke_neighbor: bool = True
    neighbor_chokes_us: bool = True
    we_are_interested: bool = False
    neighbor_is_interested: bool = False
    bitfield: list[bool] = field(default_factory=list)
    connected: bool = False
    received_message_count: int = 0
    last_interest_sent: bool | None = None

    def reset_connection(self, piece_count: int) -> None:
        # Do not assume initial file ownership is still the neighbor's current state
        self.bitfield = [False] * piece_count
        self.connected = True
        self.received_message_count = 0
        self.last_interest_sent = None
        self.we_choke_neighbor = True
        self.neighbor_chokes_us = True
        self.we_are_interested = False
        self.neighbor_is_interested = False

    def has_interesting_pieces(self, local: list[bool]) -> bool:
        if len(self.bitfield) != len(local):
            raise ValueError("Neighbor and local bitfields must have the same length")
        return any(remote and not own for remote, own in zip(self.bitfield, local))
