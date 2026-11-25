"""Privacy-safe logging: one line per request, no bodies, no IPs, no policy text.

See _local/team.md section 6.11. HTTP and ML libraries are kept at WARNING because their
DEBUG output contains request bodies.
"""
from __future__ import annotations

import logging

QUIET = ("urllib3", "httpx", "httpcore", "transformers", "torch", "requests")


def configure(env: str = "dev") -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    for name in QUIET:
        logging.getLogger(name).setLevel(logging.WARNING)
    logging.getLogger("privascore.api").setLevel(logging.INFO)
