"""Shared SEC/EDGAR HTTP helpers for the data-gathering scripts.

SEC requires a descriptive User-Agent with a contact; any teammate may edit the email.
http_get retries transient errors (429/5xx) that EDGAR + GDELT throw intermittently.
"""
from __future__ import annotations

import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen

USER_AGENT = "UCB JPM M&A research ronaldliubc@gmail.com"


def http_get(url: str, *, timeout: int = 40, retries: int = 4, backoff: float = 1.5,
             user_agent: str = USER_AGENT) -> bytes:
    """GET a URL with a compliant User-Agent, retrying on transient HTTP errors."""
    for attempt in range(retries):
        try:
            return urlopen(Request(url, headers={"User-Agent": user_agent}), timeout=timeout).read()
        except HTTPError as exc:
            if exc.code in (429, 500, 502, 503) and attempt < retries - 1:
                time.sleep(backoff * (attempt + 1))
                continue
            raise
    raise RuntimeError("unreachable")
