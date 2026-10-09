# Entry point: will accept a peer ID, load configuration, and start the peer process

import argparse
from pathlib import Path

from p2p.config import load_common, load_peers
from p2p.peer import PeerProcess


def main() -> None:
    parser = argparse.ArgumentParser(description="Initialize a P2P peer (startup base).")
    parser.add_argument("peer_id", type=int, help="ID from PeerInfo.cfg")
    args = parser.parse_args()

    # Resolve files beside this launcher even when invoked from another directory
    root = Path(__file__).resolve().parent
    try:
        common = load_common(root / "Common.cfg")
        peers = load_peers(root / "PeerInfo.cfg")
        PeerProcess(args.peer_id, common, peers, root).run()
    except (OSError, ValueError) as error:
        parser.exit(1, f"Startup failed: {error}\n")


if __name__ == "__main__":
    main()
