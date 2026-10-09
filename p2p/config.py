# Configuration: will parse and validate Common.cfg and PeerInfo.cfg, preserving peer startup order

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)

# Stores choking algorithm and file information
class CommonConfig:
    preferred_neighbor_count: int
    unchoking_interval: int
    optimistic_unchoking_interval: int
    file_name: str
    file_size: int
    piece_size: int

    @property
    def piece_count(self) -> int:
        # Round up so a smaller final piece still counts as a piece
        return (self.file_size + self.piece_size - 1) // self.piece_size


@dataclass(frozen=True)
class PeerInfo:
    peer_id: int
    host: str
    port: int
    has_file: bool

# Helper function for parsing files
def _rows(path: Path):
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        fields = line.split("#", 1)[0].split()
        if fields:
            yield number, fields

# Load and validate the common configuration file
def load_common(path: Path) -> CommonConfig:
    values = {}
    for number, fields in _rows(path):
        if len(fields) != 2 or fields[0] in values:
            raise ValueError(f"{path.name}:{number}: expected a unique key and value")
        values[fields[0]] = fields[1]

    try:
        config = CommonConfig(
            int(values["NumberOfPreferredNeighbors"]),
            int(values["UnchokingInterval"]),
            int(values["OptimisticUnchokingInterval"]),
            values["FileName"],
            int(values["FileSize"]),
            int(values["PieceSize"]),
        )
    except KeyError as error:
        raise ValueError(f"{path.name}: missing {error.args[0]}") from error

    if config.preferred_neighbor_count < 0 or min(
        config.unchoking_interval, config.optimistic_unchoking_interval,
        config.file_size, config.piece_size,
    ) <= 0:
        raise ValueError("Intervals and sizes must be positive; neighbor count cannot be negative")
    if config.file_name in {".", ".."} or any(c in config.file_name for c in "/\\:"):
        raise ValueError("FileName must be a file name without directory components")
    return config

# Parse through all peers and convert into PeerInfo objects
def load_peers(path: Path) -> list[PeerInfo]:
    peers = []
    seen = set()
    for number, fields in _rows(path):
        if len(fields) != 4 or fields[3] not in {"0", "1"}:
            raise ValueError(f"{path.name}:{number}: expected ID host port has_file(0|1)")
        peer = PeerInfo(int(fields[0]), fields[1], int(fields[2]), fields[3] == "1")
        if not 1 <= peer.peer_id <= 0xFFFFFFFF or not 1 <= peer.port <= 65535:
            raise ValueError(f"{path.name}:{number}: invalid peer ID or port")
        if peer.peer_id in seen:
            raise ValueError(f"{path.name}:{number}: duplicate peer ID {peer.peer_id}")
        seen.add(peer.peer_id)
        peers.append(peer)
    if not peers:
        raise ValueError(f"{path.name}: no peers configured")
    return peers
