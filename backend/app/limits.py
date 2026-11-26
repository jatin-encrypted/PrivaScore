"""Resource caps that hold against a client that is not being helpful.

Both guards here replace a check that looked like a limit but was really a request to behave:

  * BodySizeLimit counts the bytes that actually arrive. The previous check read Content-Length,
    which a chunked request simply does not send, so any body size got through and was buffered
    into memory before the handler's character limit could reject it.

  * run_guarded holds the concurrency permit until the WORK finishes, not until the REQUEST
    finishes. asyncio.to_thread cannot be cancelled: when a client disconnects mid-analysis, the
    coroutine is cancelled but the thread keeps running its BERT pass and its Gemini call. The
    old `async with gate` released the permit at that moment, so a client that connected and
    disconnected in a loop could run unbounded analyses at once and spend the API quota.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import secrets
import time
from typing import Awaitable, TypeVar

from .errors import ApiError

log = logging.getLogger(__name__)

T = TypeVar("T")


class BodySizeLimit:
    """Pure ASGI middleware: BaseHTTPMiddleware cannot wrap `receive`, and wrapping `receive` is
    the only place the real byte count is visible."""

    def __init__(self, app, max_bytes: int):
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Two checks, because they catch different clients. The declared length rejects an
        # honest oversized request without reading a byte; the running count catches a chunked
        # request, which sends no length at all, and one that simply lies.
        if _declared_length(scope) > self.max_bytes:
            await _send_api_error(send, ApiError("BODY_TOO_LARGE", 413))
            return

        total = 0
        too_large = False

        async def counting_receive():
            nonlocal total, too_large
            message = await receive()
            if message["type"] == "http.request":
                total += len(message.get("body", b""))
                if total > self.max_bytes:
                    too_large = True
                    # Tell the application the body ended here, so it stops reading and unwinds
                    # instead of buffering the rest of whatever is being streamed at us.
                    return {"type": "http.disconnect"}
            return message

        sent_response = False

        async def guarded_send(message):
            nonlocal sent_response
            if too_large and not sent_response:
                sent_response = True
                await _send_api_error(send, ApiError("BODY_TOO_LARGE", 413))
                return
            if too_large:
                return                      # the 413 was already sent; drop the app's output
            sent_response = True
            await send(message)

        try:
            await self.app(scope, counting_receive, guarded_send)
        except Exception:
            if not too_large:
                raise
        if too_large and not sent_response:
            sent_response = True
            await _send_api_error(send, ApiError("BODY_TOO_LARGE", 413))


def _declared_length(scope) -> int:
    for name, value in scope.get("headers", ()):
        if name == b"content-length":
            try:
                return int(value)
            except ValueError:
                return 0
    return 0


async def _send_api_error(send, error: ApiError) -> None:
    response = error.response()
    await send({"type": "http.response.start", "status": response.status_code,
                "headers": [(k.lower().encode(), v.encode())
                            for k, v in response.headers.items()]})
    await send({"type": "http.response.body", "body": response.body})


async def run_guarded(gate: asyncio.Semaphore, work: Awaitable[T]) -> T:
    """Run `work` holding one permit, released when the work is genuinely finished.

    The await is shielded, so a client disconnect cancels the caller but leaves the task (and
    its uncancellable threads) running with the permit still held. The next caller therefore
    sees BUSY, which is the truth, instead of being let in alongside work that never stopped.
    """
    await gate.acquire()
    task = asyncio.ensure_future(work)

    def release(finished: asyncio.Future) -> None:
        gate.release()
        # Nobody is left to await the task after a cancellation, so retrieve any exception here
        # to avoid an "exception was never retrieved" warning at garbage-collection time.
        if not finished.cancelled() and finished.exception() is not None:
            log.info("analysis failed after the client left: %s",
                     type(finished.exception()).__name__)

    task.add_done_callback(release)
    return await asyncio.shield(task)


# --------------------------------------------------------------------------- rate limiting

def client_identity(socket_ip: str, headers, trust_proxy: bool) -> str:
    """Who to count this request against.

    Behind a reverse proxy every request arrives from the proxy, so the socket address is
    useless and X-Forwarded-For carries the real client. That header is also trivially
    spoofable, so it is believed ONLY when the deployment declares it sits behind a proxy;
    otherwise any client could mint a fresh identity per request and never hit a limit.
    """
    if trust_proxy:
        forwarded = headers.get("x-forwarded-for")
        if forwarded:
            # Left-most entry is the original client; the rest are proxies it passed through.
            first = forwarded.split(",")[0].strip()
            if first:
                return first
    return socket_ip


class RateLimiter:
    """A per-client window plus a global daily budget, both in memory.

    The daily budget is the one that actually protects the API key. A per-client limit alone
    does not: twenty clients each staying politely under their allowance can still spend far
    more than a day's quota between them.

    No client address is retained. Entries are keyed by a BLAKE2b hash under a salt generated
    at construction, so the table cannot be read back as a list of visitors, cannot be compared
    across restarts, and cannot be matched against a precomputed table of all IPv4 addresses.

    Section 6.8 forbids a database, and this needs none: it is a dict that forgets entries older
    than the window. One process holds it, which matches max_concurrent=1 single-worker
    deployment. More than one worker would give each its own counters, so the effective limit
    would multiply by the worker count.
    """

    def __init__(self, per_client: int, window_s: int = 3600, daily_budget: int = 0,
                 now=time.monotonic):
        self.per_client = per_client
        self.window_s = window_s
        self.daily_budget = daily_budget
        self._now = now
        self._salt = secrets.token_bytes(16)
        self._hits: dict[str, list[float]] = {}
        self._day_start = now()
        self._day_count = 0

    @property
    def enabled(self) -> bool:
        return self.per_client > 0 or self.daily_budget > 0

    def _key(self, client: str) -> str:
        return hashlib.blake2b(client.encode("utf-8"), key=self._salt, digest_size=16).hexdigest()

    def check(self, client: str) -> float | None:
        """None to allow (and the call is counted), or the seconds to wait before retrying."""
        now = self._now()

        if self.daily_budget > 0:
            if now - self._day_start >= 86_400:
                self._day_start, self._day_count = now, 0
            if self._day_count >= self.daily_budget:
                return round(86_400 - (now - self._day_start), 1) or 1.0

        if self.per_client > 0:
            cutoff = now - self.window_s
            # Forgetting everything stale on each call keeps the table bounded by the number of
            # distinct clients seen within one window, with no cleanup task to run.
            self._hits = {k: [t for t in ts if t > cutoff]
                          for k, ts in self._hits.items() if any(t > cutoff for t in ts)}
            key = self._key(client)
            times = self._hits.get(key, [])
            if len(times) >= self.per_client:
                return round(times[0] + self.window_s - now, 1) or 1.0
            times.append(now)
            self._hits[key] = times

        self._day_count += 1
        return None
