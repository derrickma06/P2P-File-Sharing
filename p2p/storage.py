# Storage: will manage files in peer_<peer_id>/, track the bitfield, and read and write file pieces

from pathlib import Path

from p2p.config import CommonConfig


class PieceStorage:
    def __init__(self, directory: Path, common: CommonConfig, has_file: bool) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        self.directory = directory
        self.file_path = directory / common.file_name

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
        return sum(self.bitfield)

    @property
    def is_complete(self) -> bool:
        return all(self.bitfield)
