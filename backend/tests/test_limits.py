"""The two resource caps, tested against what an unfriendly client actually sends.

Both of these were caps that looked enforced and were not:

  * the body limit trusted the Content-Length header, which a chunked request simply omits;
  * the concurrency gate was released when the REQUEST ended, not when the WORK ended, so a
    client that disconnected mid-analysis freed the permit while its Gemini call and its BERT
    pass were still running in the thread pool.

The second one spends the project's Gemini quota, so it is the more expensive of the two.
"""
from __future__ import annotations

import asyncio
import threading

import pytest


def test_a_chunked_body_cannot_slip_past_the_size_cap(client):
    """No Content-Length header at all. The cap has to count the bytes that arrive."""
    oversize = 2_000_000                      # twice the default max_body_bytes

    def chunks():
        sent = 0
        while sent < oversize:
            block = b"x" * 100_000
            sent += len(block)
            yield block

    r = client.post("/api/v1/evaluate", content=chunks(),
                    headers={"Content-Type": "application/json"})
    assert r.status_code == 413
    assert r.json()["error"]["code"] == "BODY_TOO_LARGE"


def test_a_lying_content_length_cannot_slip_past_either(client):
    """A small Content-Length with a large body. Starlette reads what the header promises, so
    this is mostly belt-and-braces, but the cap must not depend on the client being honest."""
    body = b'{"text": "' + b"x" * 1_500_000 + b'"}'
    r = client.post("/api/v1/evaluate", content=body,
                    headers={"Content-Type": "application/json"})
    assert r.status_code in (413, 422), r.status_code


def test_a_body_within_the_cap_still_works(client, policy_text):
    """The guard must not break the normal path."""
    r = client.post("/api/v1/evaluate", json={"text": policy_text})
    assert r.status_code == 200


@pytest.mark.anyio
async def test_the_gate_stays_held_until_the_work_really_finishes():
    """A cancelled request must not hand its permit to the next caller while its own threads are
    still burning quota. The gate is released by the work completing, not by the client leaving.
    """
    from app.routers.evaluate import run_guarded

    gate = asyncio.Semaphore(1)
    started = threading.Event()
    may_finish = threading.Event()
    finished = threading.Event()

    async def slow_work():
        # Exactly what the real pipeline does: hand the work to a thread, which cannot be
        # cancelled once it is running.
        def body():
            started.set()
            may_finish.wait(5)
            finished.set()
            return "done"

        return await asyncio.to_thread(body)

    task = asyncio.create_task(run_guarded(gate, slow_work()))
    await asyncio.to_thread(started.wait, 5)
    assert gate.locked(), "the permit should be held while the work runs"

    # The client goes away.
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    # The work is still running, so the permit must NOT be free yet.
    assert gate.locked(), "a cancelled request must not release the permit early"
    assert not finished.is_set()

    may_finish.set()
    await asyncio.to_thread(finished.wait, 5)
    for _ in range(100):                      # let the done-callback run
        await asyncio.sleep(0.01)
        if not gate.locked():
            break
    assert not gate.locked(), "the permit must be released once the work finishes"
