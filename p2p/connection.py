# TCP connections: will listen for incoming peers, connect to earlier peers, verify handshakes, and send and receive complete messages

import socket
from dataclasses import dataclass
from queue import Queue
from threading import Event, Lock, Thread

from p2p.config import CommonConfig, PeerInfo
from p2p.protocol import HANDSHAKE_SIZE, Message, decode_handshake, encode_handshake


def receive_exact(stream: socket.socket, size: int) -> bytes:
    data = bytearray()
    while len(data) < size:
        chunk = stream.recv(size - len(data))
        if not chunk:
            raise ConnectionError("Peer closed the connection")
        data.extend(chunk)
    return bytes(data)


class PeerConnection:
    def __init__(self, peer_id: int, stream: socket.socket, outgoing: bool) -> None:
        self.peer_id = peer_id
        self.stream = stream
        self.outgoing = outgoing
        self._send_lock = Lock()

    def send(self, message: Message) -> None:
        # Two callers must not interleave their length prefixes and payloads
        with self._send_lock:
            self.stream.sendall(message.to_bytes())

    def receive(self, maximum_body: int) -> Message:
        length = int.from_bytes(receive_exact(self.stream, 4), "big")
        if not 1 <= length <= maximum_body:
            raise ValueError(f"Invalid message body length: {length}")
        return Message.from_body(receive_exact(self.stream, length))

    def close(self) -> None:
        close_socket(self.stream)


def close_socket(stream: socket.socket) -> None:
    # shutdown wakes a worker blocked in recv, close alone is not enough everywhere
    try:
        stream.shutdown(socket.SHUT_RDWR)
    except OSError:
        pass
    stream.close()


@dataclass(frozen=True)
class NetworkEvent:
    kind: str
    connection: PeerConnection | None = None
    message: Message | None = None
    detail: str = ""


class PeerNetwork:
    def __init__(self, info: PeerInfo, peers: list[PeerInfo], common: CommonConfig, events: Queue[NetworkEvent]) -> None:
        self.info = info
        self.events = events
        index = next(i for i, peer in enumerate(peers) if peer.peer_id == info.peer_id)
        self.earlier = peers[:index]
        self.later_ids = {peer.peer_id for peer in peers[index + 1:]}
        self.maximum_body = max(5 + common.piece_size, 1 + (common.piece_count + 7) // 8)
        self.stopping = Event()
        self._lock = Lock()
        self._sockets: set[socket.socket] = set()
        self._connections: dict[int, PeerConnection] = {}
        self._workers: list[Thread] = []
        self._listener: socket.socket | None = None
        self._accept_worker: Thread | None = None

    def start(self) -> None:
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            listener.bind(("0.0.0.0", self.info.port))
            listener.listen()
            listener.settimeout(0.25)
        except OSError:
            listener.close()
            raise
        self._listener = listener
        self._accept_worker = Thread(target=self._accept, name=f"accept-{self.info.peer_id}")
        self._accept_worker.start()
        for peer in self.earlier:
            self._spawn(self._dial, peer)

    def _spawn(self, target, *args) -> None:
        worker = Thread(target=target, args=args, name=f"network-{self.info.peer_id}")
        with self._lock:
            self._workers.append(worker)
        worker.start()

    def _track(self, stream: socket.socket) -> None:
        with self._lock:
            self._sockets.add(stream)

    def _release(self, stream: socket.socket) -> None:
        close_socket(stream)
        with self._lock:
            self._sockets.discard(stream)

    def _accept(self) -> None:
        while not self.stopping.is_set():
            try:
                stream, _ = self._listener.accept()
            except socket.timeout:
                continue
            except OSError as error:
                if not self.stopping.is_set():
                    self.events.put(NetworkEvent("error", detail=str(error)))
                break
            self._track(stream)
            self._spawn(self._session, stream, None)

    def _dial(self, peer: PeerInfo) -> None:
        # Earlier peers may still be binding their ports when this process starts
        while not self.stopping.is_set():
            stream = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._track(stream)
            try:
                stream.settimeout(0.5)
                stream.connect((peer.host, peer.port))
            except OSError:
                self._release(stream)
                self.stopping.wait(0.25)
                continue
            self._session(stream, peer.peer_id)
            return

    def _session(self, stream: socket.socket, expected_id: int | None) -> None:
        connection = None
        try:
            stream.settimeout(3)
            stream.sendall(encode_handshake(self.info.peer_id))
            remote_id = decode_handshake(receive_exact(stream, HANDSHAKE_SIZE))
            if expected_id is not None and remote_id != expected_id:
                raise ValueError(f"Expected peer {expected_id}, received {remote_id}")
            if expected_id is None and remote_id not in self.later_ids:
                raise ValueError(f"Unexpected incoming peer {remote_id}")
            stream.settimeout(None)
            candidate = PeerConnection(remote_id, stream, expected_id is not None)
            with self._lock:
                if remote_id in self._connections:
                    raise ValueError(f"Duplicate connection from peer {remote_id}")
                self._connections[remote_id] = candidate
                connection = candidate
            self.events.put(NetworkEvent("connected", connection))
            while not self.stopping.is_set():
                message = connection.receive(self.maximum_body)
                self.events.put(NetworkEvent("message", connection, message))
        except (OSError, ValueError) as error:
            if not self.stopping.is_set():
                self.events.put(NetworkEvent("error", connection, detail=str(error)))
        finally:
            if connection is not None:
                with self._lock:
                    self._connections.pop(connection.peer_id, None)
                self.events.put(NetworkEvent("disconnected", connection))
            self._release(stream)

    def stop(self) -> None:
        self.stopping.set()
        if self._listener is not None:
            close_socket(self._listener)
        # Finish accepting before taking the worker list so no worker is missed
        if self._accept_worker is not None:
            self._accept_worker.join()
        with self._lock:
            streams = list(self._sockets)
        for stream in streams:
            close_socket(stream)
        for worker in self._workers:
            worker.join()
