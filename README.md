# P2P File Sharing

Python project for CNT4007 implementing a BitTorrent-style file-sharing protocol over TCP. Each peer downloads and uploads file pieces directly to other peers.

**Current status:** scaffold only. Python and configuration files contain purpose comments; functionality is not implemented yet.

## Files

| File | Planned responsibility |
| --- | --- |
| `peerProcess.py` | Entry point: accept a peer ID, load configuration, and start the peer. |
| `Common.cfg` | Shared file name, file size, piece size, preferred-neighbor count, and unchoking intervals. |
| `PeerInfo.cfg` | Peer IDs, hosts, ports, initial file ownership, and startup order. |
| `p2p/__init__.py` | Define the Python package for the implementation modules. |
| `p2p/config.py` | Parse and validate both configuration files. |
| `p2p/peer.py` | Coordinate startup, message handling, transfers, and shutdown. |
| `p2p/connection.py` | Manage TCP connections, verify handshakes, and send and receive complete messages. |
| `p2p/protocol.py` | Encode and decode the 32-byte handshake and eight protocol message types. |
| `p2p/storage.py` | Read and write pieces, maintain the local bitfield, and track file completion. |
| `p2p/neighbors.py` | Track neighbor ownership, interest, choke states, download rates, and pending requests; select upload neighbors and requested pieces. |
| `p2p/peer_logging.py` | Write required timestamped events to `log_peer_<peer_id>.log`. |
| `peer_<peer_id>/` | Store each peer's complete or partial file; `.gitkeep` preserves empty directories in Git. |
| `.gitignore` | Exclude generated logs, Python caches, environments, and peer data from Git. |

These modules separate configuration, networking, protocol encoding, storage, and scheduling so each part can be developed independently. `peer.py` connects them together.

## Planned workflow

1. `peerProcess.py` uses `config.py` to load settings and initialize `peer.py`, storage, neighbor state, and logging.
2. `connection.py` listens for later peers and connects to earlier peers in `PeerInfo.cfg`. `protocol.py` handles handshakes and message encoding.
3. Peers exchange bitfields and interest messages. `neighbors.py` selects preferred and optimistically unchoked neighbors at the configured intervals.
4. Unchoked peers request random missing pieces, with one outstanding request per neighbor and no duplicate requests across neighbors. `storage.py` saves received pieces; `peer.py` announces them with `have` messages and updates interest and logs.
5. A peer continues uploading after its own download finishes and exits only when all configured peers have the complete file.

## Planned usage

Use Python 3.11 or newer. No third-party packages are planned.

Once implemented, fill in both configuration files, place the source file in each initially complete peer's directory, and start peers in `PeerInfo.cfg` order:

```bash
python peerProcess.py 1001
```

Repeat in separate terminals or on the configured hosts with each peer's ID.
