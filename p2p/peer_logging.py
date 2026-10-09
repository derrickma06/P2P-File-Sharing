# Logging: will write the required timestamped connection, neighbor, choke, interest, piece, and completion events to log_peer_<peer_id>.log

import logging
from pathlib import Path


def create_logger(root: Path, peer_id: int) -> logging.Logger:
    # A dedicated logger keeps each peer's output in its own file
    logger = logging.Logger(f"peer.{peer_id}", level=logging.INFO)
    handler = logging.FileHandler(root / f"log_peer_{peer_id}.log", encoding="utf-8")
    handler.setFormatter(logging.Formatter(
        "%(asctime)s: %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    ))
    logger.addHandler(handler)
    return logger
