# Logging: will write the required timestamped connection, neighbor, choke, interest, piece, and completion events to log_peer_<peer_id>.log

import logging
import sys
from pathlib import Path


def create_logger(root: Path, peer_id: int) -> logging.Logger:
    # A dedicated logger keeps each peer's output in its own file
    logger = logging.Logger(f"peer.{peer_id}", level=logging.INFO)
    handler = logging.FileHandler(root / f"log_peer_{peer_id}.log", encoding="utf-8")
    formatter = logging.Formatter(
        "%(asctime)s: %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    logger.addHandler(console)
    return logger


class PeerLog:
    def __init__(self, root: Path, peer_id: int) -> None:
        self.peer_id = peer_id
        self.logger = create_logger(root, peer_id)

    def connection(self, remote_id: int, outgoing: bool) -> None:
        action = "makes a connection to" if outgoing else "is connected from"
        self.logger.info("Peer %s %s Peer %s.", self.peer_id, action, remote_id)

    def interest(self, remote_id: int, interested: bool) -> None:
        kind = "interested" if interested else "not interested"
        self.logger.info("Peer %s received the '%s' message from %s.",
                         self.peer_id, kind, remote_id)

    def have(self, remote_id: int, index: int) -> None:
        self.logger.info("Peer %s received the 'have' message from %s for the piece %s.",
                         self.peer_id, remote_id, index)

    def choke(self, remote_id: int, choked: bool) -> None:
        action = "choked" if choked else "unchoked"
        self.logger.info("Peer %s is %s by %s.", self.peer_id, action, remote_id)

    def close(self) -> None:
        for handler in self.logger.handlers[:]:
            handler.close()
            self.logger.removeHandler(handler)
