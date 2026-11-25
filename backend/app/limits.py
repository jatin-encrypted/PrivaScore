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
import logging
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
