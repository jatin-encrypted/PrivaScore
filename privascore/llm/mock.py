"""Mock LLM for tests and dry runs: no network, no key, deterministic.

Two modes:
  MockClient(script=...)  replies from a script: {flag_id: [reply, reply, ...]} where each reply
                          is a dict (sent as JSON) or a raw string (to test broken output).
                          Successive calls for the same flag pop successive replies.
  MockClient()            "dry-run" mode: cites the first candidate sentence verbatim and answers
                          Unclear. Exercises the whole pipeline; its labels mean nothing.
"""
import json
import re

from .base import LLMClient, LLMResponse, LLMSettings

FLAG_RE = re.compile(r"^FLAG: (\S+)", re.MULTILINE)
CAND_RE = re.compile(r"^\[(p\d{3}\.s\d+)\] \(section: .*?\) (.+)$", re.MULTILINE)


class MockClient(LLMClient):
    provider = "mock"

    def __init__(self, settings: LLMSettings | None = None, script: dict | None = None, default: str = "dry_run"):
        """default: what to answer for flags not in `script`: "dry_run", "absent" or "error"."""
        super().__init__(settings or LLMSettings(provider="mock", model="mock"))
        self.script = {k: list(v) for k, v in (script or {}).items()}
        self.default = default
        self.calls = []

    def _batch(self, user: str) -> LLMResponse:
        """Batch prompts: script key "BATCH" holds whole replies; otherwise answer every flag asked
        (default "absent": Absent for all; "dry_run": cite each flag's first relevant sentence verbatim)."""
        flags = FLAG_RE.findall(user)
        self.calls.append({"flag": "BATCH", "flags": flags, "user": user})
        if "BATCH" in self.script:
            if not self.script["BATCH"]:
                raise AssertionError("mock script has no BATCH reply left")
            reply = self.script["BATCH"].pop(0)
            if callable(reply):
                reply = reply(flags, user)
        else:
            sent = dict(CAND_RE.findall(user))
            answers = []
            for f in flags:
                m = re.search(rf"^MOST RELEVANT SENTENCE IDS FOR {re.escape(f)}: (\S+?)[,\n]", user + "\n", re.MULTILINE)
                if self.default == "dry_run" and m and m.group(1) in sent:
                    answers.append({"flag": f, "presence": "Unclear", "state": None,
                                    "evidence": [{"id": m.group(1), "quote": sent[m.group(1)]}], "rationale": "mock"})
                else:
                    answers.append({"flag": f, "presence": "Absent", "state": None, "evidence": [], "rationale": "mock"})
            reply = {"answers": answers}
        text = reply if isinstance(reply, str) else json.dumps(reply)
        return LLMResponse(text, "mock", self.settings.model, {}, {})

    def complete_json(self, system: str, user: str) -> LLMResponse:
        if user.startswith("MODE: BATCH"):
            return self._batch(user)
        flag = FLAG_RE.search(user).group(1)
        self.calls.append({"flag": flag, "system": system, "user": user})
        if flag in self.script:
            replies = self.script[flag]
            if not replies:
                raise AssertionError(f"mock script has no reply left for {flag}")
            reply = replies.pop(0)
        elif self.default == "error":
            raise AssertionError(f"mock: unexpected call for {flag}")
        elif self.default == "absent":
            reply = {"flag": flag, "presence": "Absent", "state": None, "evidence": [], "rationale": "mock"}
        else:
            m = CAND_RE.search(user)
            reply = ({"flag": flag, "presence": "Unclear", "state": None,
                      "evidence": [{"id": m.group(1), "quote": m.group(2)}],
                      "rationale": "mock dry run"} if m else
                     {"flag": flag, "presence": "Absent", "state": None, "evidence": [], "rationale": "mock dry run"})
        text = reply if isinstance(reply, str) else json.dumps(reply)
        return LLMResponse(text, "mock", self.settings.model, {}, {})
