"""Gemini / Groq clients and the config switch, tested against a fake HTTP session (no network)."""
import pytest

from privascore.config import load_config
from privascore.llm import LLMError, LLMSettings, make_client
from privascore.llm.gemini import GeminiClient
from privascore.llm.groq import GroqClient


class FakeResp:
    def __init__(self, status, payload=None, headers=None, text=""):
        self.status_code, self._p, self.headers, self.text = status, payload, headers or {}, text

    def json(self):
        return self._p


class FakeSession:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.requests = []

    def post(self, url, headers, json, timeout):
        self.requests.append({"url": url, "headers": headers, "json": json, "timeout": timeout})
        return self.responses.pop(0)


@pytest.fixture(autouse=True)
def keys(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
    monkeypatch.setenv("GROQ_API_KEY", "test-groq-key")
    monkeypatch.setattr("time.sleep", lambda s: None)     # no real waiting in retry tests


GEMINI_OK = {"candidates": [{"content": {"parts": [{"text": '{"ok": true}'}]}, "finishReason": "STOP"}],
             "usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 3}}
GROQ_OK = {"choices": [{"message": {"role": "assistant", "content": '{"ok": true}'}, "finish_reason": "stop"}],
           "usage": {"prompt_tokens": 10, "completion_tokens": 3}}


def settings(provider, **kw):
    return LLMSettings(provider=provider, model="test-model", **kw)


def test_gemini_request_shape_and_parse():
    s = FakeSession(FakeResp(200, GEMINI_OK))
    c = GeminiClient(settings("gemini", temperature=0.0, max_output_tokens=256), session=s)
    r = c.complete_json("SYS", "USER")
    req = s.requests[0]
    assert req["url"].endswith("/v1beta/models/test-model:generateContent")
    assert req["headers"]["x-goog-api-key"] == "test-gemini-key" and "key=" not in req["url"]
    assert req["json"]["systemInstruction"]["parts"][0]["text"] == "SYS"
    assert req["json"]["contents"][0]["parts"][0]["text"] == "USER"
    assert req["json"]["generationConfig"] == {"temperature": 0.0, "maxOutputTokens": 256,
                                               "responseMimeType": "application/json"}
    assert "tools" not in req["json"]
    assert r.text == '{"ok": true}' and r.usage["promptTokenCount"] == 10


def test_groq_request_shape_and_parse():
    s = FakeSession(FakeResp(200, GROQ_OK))
    c = GroqClient(settings("groq"), session=s)
    r = c.complete_json("SYS", "USER")
    req = s.requests[0]
    assert req["url"] == "https://api.groq.com/openai/v1/chat/completions"
    assert req["headers"]["Authorization"] == "Bearer test-groq-key"
    assert req["json"]["messages"] == [{"role": "system", "content": "SYS"}, {"role": "user", "content": "USER"}]
    assert req["json"]["response_format"] == {"type": "json_object"} and req["json"]["model"] == "test-model"
    assert "tools" not in req["json"]
    assert r.text == '{"ok": true}'


@pytest.mark.parametrize("cls,ok", [(GeminiClient, GEMINI_OK), (GroqClient, GROQ_OK)])
def test_retry_on_rate_limit_then_success(cls, ok):
    s = FakeSession(FakeResp(429, text="rate limited", headers={"Retry-After": "2"}), FakeResp(500), FakeResp(200, ok))
    r = cls(settings(cls.provider, max_http_retries=3), session=s).complete_json("S", "U")
    assert r.text == '{"ok": true}' and len(s.requests) == 3


@pytest.mark.parametrize("cls", [GeminiClient, GroqClient])
def test_gives_up_after_retries(cls):
    s = FakeSession(*[FakeResp(500) for _ in range(3)])
    with pytest.raises(LLMError, match="gave up after 3 attempts"):
        cls(settings(cls.provider, max_http_retries=2), session=s).complete_json("S", "U")


@pytest.mark.parametrize("cls", [GeminiClient, GroqClient])
def test_client_errors_not_retried_and_key_not_leaked(cls):
    s = FakeSession(FakeResp(401, text="invalid api key"))
    with pytest.raises(LLMError) as e:
        cls(settings(cls.provider), session=s).complete_json("S", "U")
    assert len(s.requests) == 1
    assert "test-gemini-key" not in str(e.value) and "test-groq-key" not in str(e.value)


def test_gemini_blocked_and_empty():
    with pytest.raises(LLMError, match="blockReason=SAFETY"):
        GeminiClient(settings("gemini"), session=FakeSession(FakeResp(200, {"promptFeedback": {"blockReason": "SAFETY"}}))
                     ).complete_json("S", "U")
    empty = {"candidates": [{"content": {"parts": []}, "finishReason": "MAX_TOKENS"}]}
    with pytest.raises(LLMError, match="MAX_TOKENS"):
        GeminiClient(settings("gemini"), session=FakeSession(FakeResp(200, empty))).complete_json("S", "U")


def test_missing_key(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY")
    with pytest.raises(LLMError, match="GROQ_API_KEY"):
        GroqClient(settings("groq"))


def test_custom_key_env(monkeypatch):
    monkeypatch.setenv("MY_KEY", "k2")
    c = GeminiClient(settings("gemini", api_key_env="MY_KEY"), session=FakeSession(FakeResp(200, GEMINI_OK)))
    c.complete_json("S", "U")
    assert c.session.requests[0]["headers"]["x-goog-api-key"] == "k2"


CFG = """
[llm]
provider = "{provider}"
temperature = 0.0
min_interval_seconds = 0
[llm.gemini]
model = "gem-model"
[llm.groq]
model = "groq-model"
[extractor]
max_candidates = 12
"""


@pytest.mark.parametrize("provider,model,cls", [("gemini", "gem-model", GeminiClient), ("groq", "groq-model", GroqClient)])
def test_config_switch(tmp_path, provider, model, cls):
    p = tmp_path / "privascore.toml"
    p.write_text(CFG.format(provider=provider))
    cfg = load_config(p)
    assert cfg.llm.provider == provider and cfg.llm.model == model and cfg.extractor.max_candidates == 12
    assert isinstance(make_client(cfg.llm), cls)


def test_config_provider_override_and_validation(tmp_path):
    p = tmp_path / "c.toml"
    p.write_text(CFG.format(provider="gemini"))
    assert load_config(p, provider="groq").llm.model == "groq-model"
    assert load_config(p, provider="mock").llm.provider == "mock"
    p.write_text(CFG.format(provider="openai"))
    with pytest.raises(ValueError, match="provider must be"):
        load_config(p)
    p.write_text(CFG.format(provider="gemini").replace('model = "gem-model"', 'model = ""'))
    with pytest.raises(ValueError, match="model is required"):
        load_config(p)
    p.write_text(CFG.format(provider="gemini") + "\nbogus_key = 1\n")
    with pytest.raises(ValueError, match="unknown ExtractorSettings keys"):
        load_config(p)


def test_example_config_loads():
    cfg = load_config()      # privascore.toml if present, else privascore.example.toml
    assert cfg.llm.provider in ("mock", "gemini", "groq")


def test_dotenv_loading(tmp_path, monkeypatch):
    from privascore.config import load_dotenv
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.setenv("ALREADY_SET", "shell")
    monkeypatch.delenv("QUOTED", raising=False)
    env = tmp_path / ".env"
    env.write_text('# comment\nGEMINI_API_KEY=abc123  # my key\nexport QUOTED="x y"\nGROQ_API_KEY=\nALREADY_SET=file\nnot a line\n')
    loaded = load_dotenv(env)
    import os
    assert os.environ["GEMINI_API_KEY"] == "abc123" and os.environ["QUOTED"] == "x y"
    assert "GROQ_API_KEY" not in os.environ          # blank values are skipped
    assert os.environ["ALREADY_SET"] == "shell"       # shell wins over .env
    assert sorted(loaded) == ["GEMINI_API_KEY", "QUOTED"]
    monkeypatch.delenv("QUOTED")


def test_429_waits_65s_then_succeeds(monkeypatch):
    from privascore.llm import QuotaExhausted  # noqa: F401
    slept = []
    monkeypatch.setattr("time.sleep", lambda s: slept.append(s))
    s = FakeSession(FakeResp(429, text='{"error": {"message": "Resource exhausted, retry later"}}'), FakeResp(200, GEMINI_OK))
    r = GeminiClient(settings("gemini"), session=s).complete_json("S", "U")
    assert r.text == '{"ok": true}' and 65.0 in slept


def test_daily_quota_stops_immediately(monkeypatch):
    from privascore.llm import QuotaExhausted
    s = FakeSession(FakeResp(429, text='{"error": {"details": [{"quotaId": "GenerateRequestsPerDayPerProjectPerModel-FreeTier"}]}}'))
    with pytest.raises(QuotaExhausted, match="daily quota"):
        GeminiClient(settings("gemini"), session=s).complete_json("S", "U")
    assert len(s.requests) == 1


def test_persistent_429_stops_after_waits(monkeypatch):
    from privascore.llm import QuotaExhausted
    s = FakeSession(*[FakeResp(429, text="slow down") for _ in range(3)])
    with pytest.raises(QuotaExhausted, match="after 2 waits"):
        GroqClient(settings("groq"), session=s).complete_json("S", "U")
    assert len(s.requests) == 3


def test_overload_503_waits_then_stops_run(monkeypatch):
    from privascore.llm import ProviderOverloaded, QuotaExhausted
    slept = []
    monkeypatch.setattr("time.sleep", lambda s: slept.append(s))
    s = FakeSession(*[FakeResp(503, text="high demand") for _ in range(3)])
    with pytest.raises(ProviderOverloaded) as e:
        GeminiClient(settings("gemini"), session=s).complete_json("S", "U")
    assert isinstance(e.value, QuotaExhausted)              # extractor stops the run, flags are NOT rejected
    assert len(s.requests) == 3 and slept == [20.0, 60.0]   # 3 attempts, not 4+, so free quota is spared


def test_overload_recovers(monkeypatch):
    s = FakeSession(FakeResp(503, text="high demand"), FakeResp(200, GEMINI_OK))
    assert GeminiClient(settings("gemini"), session=s).complete_json("S", "U").text == '{"ok": true}'
