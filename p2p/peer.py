# Peer lifecycle: will coordinate startup, TCP connections, message handling, transfers, and shutdown when all peers finish.

from pathlib import Path

from p2p.config import CommonConfig, PeerInfo
from p2p.neighbors import NeighborState
from p2p.peer_logging import create_logger
from p2p.storage import PieceStorage


class PeerProcess:
    def __init__(
        self, peer_id: int, common: CommonConfig, peers: list[PeerInfo], root: Path
    ) -> None:
        index = next((i for i, peer in enumerate(peers) if peer.peer_id == peer_id), None)
        if index is None:
            raise ValueError(f"Peer {peer_id} is not listed in PeerInfo.cfg")

        self.info = peers[index]
        self.common = common
        # File order, rather than numeric ID, determines future outbound connections.
        self.earlier_peers = peers[:index]
        self.neighbors = {
            peer.peer_id: NeighborState(peer) for peer in peers if peer.peer_id != peer_id
        }
        self.storage = PieceStorage(root / f"peer_{peer_id}", common, self.info.has_file)
        self.logger = create_logger(root, peer_id)

    def run(self) -> None:
        """Initialize and report state; the network loop will be added later."""
        try:
            message = (
                f"Peer {self.info.peer_id} initialized at {self.info.host}:{self.info.port}; "
                f"pieces {self.storage.completed_piece_count}/{self.common.piece_count}; "
                f"neighbors {len(self.neighbors)}."
            )
            self.logger.info(message)
            print(message)
            print("Startup complete. Networking and file transfers are not implemented yet.")
        finally:
            # Close log resources even if reporting fails.
            for handler in self.logger.handlers[:]:
                handler.close()
                self.logger.removeHandler(handler)
