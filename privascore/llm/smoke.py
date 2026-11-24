"""One-call check that the configured provider, model and API key work.

  .venv/bin/python -m privascore.llm.smoke [--config privascore.toml]

Sends a tiny JSON request (no policy text) and prints the reply, latency and token usage.
"""
import argparse
import json
import sys
import time

from ..config import load_config
from . import LLMError, make_client


def list_models(provider: str) -> int:
    """Print the models this API key can call (Gemini: those supporting generateContent)."""
    import os
    import requests
    if provider == "gemini":
        key = os.environ.get("GEMINI_API_KEY", "")
        if not key:
            print("GEMINI_API_KEY is not set")
            return 1
        names, token = [], None
        while True:
            params = {"pageSize": 100, **({"pageToken": token} if token else {})}
            r = requests.get("https://generativelanguage.googleapis.com/v1beta/models",
                             headers={"x-goog-api-key": key}, params=params, timeout=30)
            if r.status_code != 200:
                print(f"FAILED: HTTP {r.status_code}: {r.text[:300]}")
                return 1
            d = r.json()
            names += [m["name"].removeprefix("models/") for m in d.get("models", [])
                      if "generateContent" in m.get("supportedGenerationMethods", [])]
            token = d.get("nextPageToken")
            if not token:
                break
    elif provider == "groq":
        key = os.environ.get("GROQ_API_KEY", "")
        if not key:
            print("GROQ_API_KEY is not set")
            return 1
        r = requests.get("https://api.groq.com/openai/v1/models", headers={"Authorization": f"Bearer {key}"}, timeout=30)
        if r.status_code != 200:
            print(f"FAILED: HTTP {r.status_code}: {r.text[:300]}")
            return 1
        names = [m["id"] for m in r.json().get("data", [])]
    else:
        print("--list-models needs --provider gemini or groq")
        return 1
    print("\n".join(sorted(names)))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config")
    ap.add_argument("--list-models", action="store_true", help="list models your key can call, then exit")
    ap.add_argument("--provider", choices=["gemini", "groq"], help="with --list-models")
    ap.add_argument("--model", help="override the configured model")
    args = ap.parse_args(argv)
    if args.list_models:
        from ..config import load_dotenv
        load_dotenv()
        return list_models(args.provider or "gemini")
    cfg = load_config(args.config, model=args.model)
    print(f"config {cfg.source}: provider={cfg.llm.provider} model={cfg.llm.model}")
    try:
        client = make_client(cfg.llm)
        t = time.monotonic()
        if cfg.llm.provider == "mock":
            print("mock provider: nothing to check. Set [llm] provider to gemini or groq.")
            return 0
        resp = client.complete_json('Reply with JSON only: {"ok": true, "model": "<your model name>"}',
                                    "Health check. Reply now.")
        dt = time.monotonic() - t
    except LLMError as e:
        print("FAILED:", e)
        return 1
    try:
        parsed = json.loads(resp.text)
    except json.JSONDecodeError:
        parsed = None
    print(f"OK in {dt:.1f}s | JSON parsed: {parsed is not None} | usage: {resp.usage}")
    print("reply:", resp.text[:300])
    return 0 if parsed is not None else 1


if __name__ == "__main__":
    sys.exit(main())
