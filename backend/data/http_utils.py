# -*- coding: utf-8 -*-
"""Shared HTTP utilities with retry and backoff for data collection."""
import os
import logging
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

# Configurable via env
COLLECT_USER_AGENT = os.getenv(
    "COLLECT_USER_AGENT",
    "football-pred-system/1.0 (+https://github.com/football-pred)",
)
COLLECT_TIMEOUT = int(os.getenv("COLLECT_TIMEOUT", "15"))
COLLECT_MAX_RETRIES = int(os.getenv("COLLECT_MAX_RETRIES", "3"))
COLLECT_BACKOFF = float(os.getenv("COLLECT_BACKOFF", "2.0"))


def build_session() -> requests.Session:
    """Build a requests session with automatic retries and backoff."""
    session = requests.Session()
    session.headers.update({"User-Agent": COLLECT_USER_AGENT})

    retry = Retry(
        total=COLLECT_MAX_RETRIES,
        backoff_factor=COLLECT_BACKOFF,
        # 429 deliberately excluded �� retrying on rate-limit backfires
        # by amplifying the load on the upstream service.
        status_forcelist=[500, 502, 503, 504],
        allowed_methods=["GET"],
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


_shared_session: requests.Session | None = None


def get_session() -> requests.Session:
    global _shared_session
    if _shared_session is None:
        _shared_session = build_session()
    return _shared_session


def safe_get(url: str, *, params: dict | None = None,
             headers: dict | None = None, timeout: int | None = None,
             label: str = "request") -> requests.Response | None:
    """GET with retries, timeout, and structured error logging.

    Returns the Response on success (status < 400), None on failure.
    Never raises; all errors are logged and swallowed.
    """
    session = get_session()
    t = timeout or COLLECT_TIMEOUT
    try:
        r = session.get(url, params=params, headers=headers, timeout=t)
        if r.status_code < 400:
            return r
        logger.warning("[%s] HTTP %s from %s", label, r.status_code, url)
    except requests.RequestException as exc:
        logger.warning("[%s] request failed: %s", label, exc)
    return None
