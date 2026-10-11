# Protocol: will encode and decode the 32-byte handshake and eight length-prefixed message types

from dataclasses import dataclass
from enum import IntEnum


HANDSHAKE_HEADER = b"P2PFILESHARINGPROJ"
HANDSHAKE_SIZE = 32


class MessageType(IntEnum):
    CHOKE = 0
    UNCHOKE = 1
    INTERESTED = 2
    NOT_INTERESTED = 3
    HAVE = 4
    BITFIELD = 5
    REQUEST = 6
    PIECE = 7


def encode_handshake(peer_id: int) -> bytes:
    if not 1 <= peer_id <= 0xFFFFFFFF:
        raise ValueError("Peer ID must be a positive four-byte integer")
    return HANDSHAKE_HEADER + bytes(10) + peer_id.to_bytes(4, "big")


def decode_handshake(data: bytes) -> int:
    if len(data) != HANDSHAKE_SIZE:
        raise ValueError("Handshake must contain exactly 32 bytes")
    if data[:18] != HANDSHAKE_HEADER or data[18:28] != bytes(10):
        raise ValueError("Invalid handshake header or reserved bytes")
    peer_id = int.from_bytes(data[28:], "big")
    if peer_id == 0:
        raise ValueError("Handshake peer ID cannot be zero")
    return peer_id


@dataclass(frozen=True)
class Message:
    kind: MessageType
    payload: bytes = b""

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", MessageType(self.kind))
        if not isinstance(self.payload, bytes):
            raise TypeError("Message payload must be bytes")
        if self.kind.value <= MessageType.NOT_INTERESTED and self.payload:
            raise ValueError("Control messages cannot carry a payload")
        if self.kind in {MessageType.HAVE, MessageType.REQUEST} and len(self.payload) != 4:
            raise ValueError("Have and request messages require a four-byte index")
        if self.kind == MessageType.PIECE and len(self.payload) <= 4:
            raise ValueError("Piece messages require an index and nonempty data")

    def to_bytes(self) -> bytes:
        body = bytes([self.kind]) + self.payload
        # The prefix measures type + payload, not the prefix itself.
        return len(body).to_bytes(4, "big") + body

    @classmethod
    def from_body(cls, body: bytes) -> "Message":
        if not body:
            raise ValueError("Message body cannot be empty")
        return cls(MessageType(body[0]), body[1:])

    @classmethod
    def from_bytes(cls, frame: bytes) -> "Message":
        if len(frame) < 5 or int.from_bytes(frame[:4], "big") != len(frame) - 4:
            raise ValueError("Message length does not match the frame")
        return cls.from_body(frame[4:])

    @classmethod
    def indexed(cls, kind: MessageType, index: int, data: bytes = b"") -> "Message":
        if kind not in {MessageType.HAVE, MessageType.REQUEST, MessageType.PIECE}:
            raise ValueError("This message type does not contain a piece index")
        if not 0 <= index <= 0xFFFFFFFF:
            raise ValueError("Piece index must fit in four bytes")
        return cls(kind, index.to_bytes(4, "big") + data)

    @property
    def piece_index(self) -> int:
        if self.kind not in {MessageType.HAVE, MessageType.REQUEST, MessageType.PIECE}:
            raise ValueError("This message has no piece index")
        return int.from_bytes(self.payload[:4], "big")


def encode_bitfield(pieces: list[bool]) -> bytes:
    packed = bytearray((len(pieces) + 7) // 8)
    for index, present in enumerate(pieces):
        if present:
            packed[index // 8] |= 1 << (7 - index % 8)
    return bytes(packed)


def decode_bitfield(payload: bytes, piece_count: int) -> list[bool]:
    if piece_count <= 0 or len(payload) != (piece_count + 7) // 8:
        raise ValueError("Bitfield length does not match the configured piece count")
    spare_bits = (-piece_count) % 8
    if spare_bits and payload[-1] & ((1 << spare_bits) - 1):
        raise ValueError("Unused bitfield bits must be zero")
    return [bool(payload[i // 8] & (1 << (7 - i % 8))) for i in range(piece_count)]
