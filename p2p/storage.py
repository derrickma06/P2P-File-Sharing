# Storage: will manage files in peer_<peer_id>/, track the bitfield, and read and write file pieces

from pathlib import Path
from threading import RLock

from p2p.config import CommonConfig


class PieceStorage:
    def __init__(self, directory: Path, common: CommonConfig, has_file: bool) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        self.directory = directory
        self.file_path = directory / common.file_name
        self.common = common
        self._lock = RLock()

        # Only advertise a complete file after checking the configured source
        if has_file:
            if not self.file_path.is_file():
                raise ValueError(f"Source file required: {self.file_path}")
            if self.file_path.stat().st_size != common.file_size:
                raise ValueError(f"Source file must be {common.file_size} bytes: {self.file_path}")

        # Boolean entries are the local representation; wire encoding comes later
        self.bitfield = [has_file] * common.piece_count

    @property
    def completed_piece_count(self) -> int:
        with self._lock:
            return sum(self.bitfield)

    @property
    def is_complete(self) -> bool:
        with self._lock:
            return all(self.bitfield)

    def snapshot(self) -> list[bool]:
        with self._lock:
            return self.bitfield.copy()

    def expected_piece_size(self, index: int) -> int:
        if not 0 <= index < self.common.piece_count:
            raise ValueError(f"Piece index out of range: {index}")
        return min(self.common.piece_size, self.common.file_size - index * self.common.piece_size)

    def read_piece(self, index: int) -> bytes:
        size = self.expected_piece_size(index)
        with self._lock:
            if not self.bitfield[index]:
                raise ValueError(f"Peer does not own piece {index}")
            with self.file_path.open("rb") as source:
                source.seek(index * self.common.piece_size)
                data = source.read(size)
            if len(data) != size:
                raise OSError(f"Stored piece {index} is incomplete")
            return data

    def write_piece(self, index: int, data: bytes) -> bool:
        # Return whether ownership changed, repeated writes leave owned pieces intact
        if len(data) != self.expected_piece_size(index):
            raise ValueError(f"Incorrect data length for piece {index}")
        with self._lock:
            if self.bitfield[index]:
                return False
            mode = "r+b" if self.file_path.exists() else "w+b"
            with self.file_path.open(mode) as destination:
                destination.truncate(self.common.file_size)
                destination.seek(index * self.common.piece_size)
                destination.write(data)
                destination.flush()
            # A failed write must never result in a 'have' announcement
            self.bitfield[index] = True
            return True
