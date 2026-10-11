# P2P File Sharing

Derrick Ma and Vivian Li

Python project for CNT4007 implementing a BitTorrent-style file-sharing protocol over TCP. Each peer downloads and uploads file pieces directly to other peers.

**Current status:** midpoint implementation. Peers establish TCP connections, verify handshakes, exchange bitfields and interest messages, handle `have` updates, and log events. Piece storage supports reads and writes, including a smaller final piece. File transfers, neighbor-selection timers, and automatic completion shutdown remain pending.

## Files

| File | Responsibility |
| --- | --- |
| `peerProcess.py` | Entry point: accept a peer ID, load configuration, and start the peer. |
| `Common.cfg` | Shared file name, file size, piece size, preferred-neighbor count, and unchoking intervals. |
| `PeerInfo.cfg` | Peer IDs, hosts, ports, initial file ownership, and startup order. |
| `p2p/__init__.py` | Define the Python package for the implementation modules. |
| `p2p/config.py` | Parse and validate both configuration files. |
| `p2p/peer.py` | Process queued network events, update ownership and interest, and coordinate shutdown. |
| `p2p/connection.py` | Manage TCP connections, verify handshakes, and send and receive complete messages. |
| `p2p/protocol.py` | Encode and decode the 32-byte handshake and eight protocol message types. |
| `p2p/storage.py` | Read and write pieces, maintain the local bitfield, and track file completion. |
| `p2p/neighbors.py` | Track ownership, interest, and choke states; rate tracking and neighbor selection are planned. |
| `p2p/peer_logging.py` | Show timestamped events in the terminal and write them to `log_peer_<peer_id>.log`. |
| `peer_<peer_id>/` | Store each peer's complete or partial file; `.gitkeep` preserves empty directories in Git. |
| `.gitignore` | Exclude generated logs, Python caches, environments, and peer data from Git. |

These modules separate configuration, networking, protocol encoding, storage, and scheduling so each part can be developed independently. `peer.py` connects them together.

## Workflow

1. `peerProcess.py` uses `config.py` to load settings and initialize `peer.py`, storage, neighbor state, and logging.
2. `connection.py` listens for later peers and connects to earlier peers in `PeerInfo.cfg`. `protocol.py` handles handshakes and message encoding.
3. Network workers enqueue messages; the peer's event loop updates neighbor bitfields and sends interest changes. Storage reads and writes are available independently of networking.
4. **Next phase:** select preferred and optimistic neighbors, request and transfer pieces, announce downloads, and exit once all peers have the complete file.

## Run

Use Python 3.11 or newer. No third-party packages are required.

The included configs define three local peers with no initial file. Open three terminals in the project directory and run these commands in order, one per terminal:

```bash
python3 peerProcess.py 1001
python3 peerProcess.py 1002
python3 peerProcess.py 1003
```

Each peer stays running and creates `log_peer_<peer_id>.log`. Press Ctrl+C to close sockets and stop its workers.

The terminals show initialization, successful connections, and received interest messages. With the default empty peers, messages say `not interested`. Stopping a peer shows disconnection events in the remaining peers.
