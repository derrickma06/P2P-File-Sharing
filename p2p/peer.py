# Peer lifecycle: will coordinate startup, TCP connections, message handling, transfers, and shutdown when all peers finish

from pathlib import Path
from queue import Empty, Queue
from threading import Event

from p2p.config import CommonConfig, PeerInfo
from p2p.connection import NetworkEvent, PeerConnection, PeerNetwork
from p2p.neighbors import NeighborState
from p2p.peer_logging import PeerLog
from p2p.protocol import Message, MessageType, decode_bitfield, encode_bitfield
from p2p.storage import PieceStorage


class PeerProcess:
    def __init__(self, peer_id: int, common: CommonConfig, peers: list[PeerInfo], root: Path) -> None:
        index = next((i for i, peer in enumerate(peers) if peer.peer_id == peer_id), None)
        if index is None:
            raise ValueError(f"Peer {peer_id} is not listed in PeerInfo.cfg")

        self.info = peers[index]
        self.common = common
        # File order determines future outbound connections rather than numeric ID
        self.earlier_peers = peers[:index]
        self.neighbors = {peer.peer_id: NeighborState(peer) for peer in peers if peer.peer_id != peer_id}
        self.storage = PieceStorage(root / f"peer_{peer_id}", common, self.info.has_file)
        self.log = PeerLog(root, peer_id)
        self.events: Queue[NetworkEvent] = Queue()
        self.network = PeerNetwork(self.info, peers, common, self.events)
        self.connections: dict[int, PeerConnection] = {}
        self.stopping = Event()

    def run(self) -> None:
        # Run until interrupted, global download completion is coming later
        try:
            self.network.start()
            message = (
                f"Peer {self.info.peer_id} initialized at {self.info.host}:{self.info.port}; "
                f"pieces {self.storage.completed_piece_count}/{self.common.piece_count}; "
                f"neighbors {len(self.neighbors)}."
            )
            self.log.logger.info(message)
            print("Listening for peers. Press Ctrl+C to stop; file transfers are pending.", flush=True)
            while not self.stopping.is_set():
                try:
                    event = self.events.get(timeout=0.2)
                except Empty:
                    continue
                self._handle_event(event)
        except KeyboardInterrupt:
            print("Stopping peer...", flush=True)
        finally:
            self.stop()
            self.network.stop()
            self.log.logger.info("Peer %s stopped.", self.info.peer_id)
            self.log.close()

    def stop(self) -> None:
        # Request shutdown from the console or a caller running this peer in a thread
        self.stopping.set()

    def _handle_event(self, event: NetworkEvent) -> None:
        connection = event.connection
        if event.kind == "error":
            self.log.logger.warning("Network: %s", event.detail)
            return
        if connection is None:
            return
        remote_id = connection.peer_id
        state = self.neighbors[remote_id]
        try:
            if event.kind == "connected":
                self.connections[remote_id] = connection
                state.reset_connection(self.common.piece_count)
                self.log.connection(remote_id, connection.outgoing)
                connection.send(Message(MessageType.BITFIELD, encode_bitfield(self.storage.snapshot())))
            elif self.connections.get(remote_id) is connection:
                if event.kind == "message":
                    self._handle_message(connection, event.message)
                elif event.kind == "disconnected":
                    del self.connections[remote_id]
                    state.connected = False
                    self.log.logger.info("Peer %s disconnected from %s.", self.info.peer_id, remote_id)
        except (OSError, ValueError) as error:
            self.log.logger.warning("Peer %s: %s", remote_id, error)
            connection.close()

    def _handle_message(self, connection: PeerConnection, message: Message) -> None:
        state = self.neighbors[connection.peer_id]
        if message.kind == MessageType.BITFIELD:
            if state.received_message_count:
                raise ValueError("Bitfield must be the first message after handshaking")
            state.bitfield = decode_bitfield(message.payload, self.common.piece_count)
            self._update_interest(connection)
        elif message.kind == MessageType.HAVE:
            index = message.piece_index
            self.storage.expected_piece_size(index)
            state.bitfield[index] = True
            self.log.have(connection.peer_id, index)
            self._update_interest(connection)
        elif message.kind in {MessageType.INTERESTED, MessageType.NOT_INTERESTED}:
            state.neighbor_is_interested = message.kind == MessageType.INTERESTED
            self.log.interest(connection.peer_id, state.neighbor_is_interested)
        elif message.kind in {MessageType.CHOKE, MessageType.UNCHOKE}:
            state.neighbor_chokes_us = message.kind == MessageType.CHOKE
            self.log.choke(connection.peer_id, state.neighbor_chokes_us)
        else:
            self.log.logger.warning("%s handling is not implemented yet.", message.kind.name)
        state.received_message_count += 1

    def _update_interest(self, connection: PeerConnection) -> None:
        state = self.neighbors[connection.peer_id]
        interested = state.has_interesting_pieces(self.storage.snapshot())
        state.we_are_interested = interested
        if state.last_interest_sent is None or state.last_interest_sent != interested:
            kind = MessageType.INTERESTED if interested else MessageType.NOT_INTERESTED
            connection.send(Message(kind))
            state.last_interest_sent = interested
