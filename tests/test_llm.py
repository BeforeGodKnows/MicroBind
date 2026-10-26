import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from microbind.llm import review, validate

CONTEXT = {
    "finding_id": "test",
    "snippets": [{"evidence_id": "source:1", "code": "test data only"}],
}
VALID = {
    "verdict": "suspected",
    "explanation": "接口契约测试，不是模型实验。",
    "required_conditions": ["owner"],
    "evidence_ids": ["source:1"],
    "suggested_test": "不同用户访问同一对象",
}


def test_unknown_evidence_rejected():
    with pytest.raises(ValueError, match="absent evidence"):
        validate({**VALID, "evidence_ids": ["invented"]}, CONTEXT)


def test_invalid_model_verdict_rejected():
    with pytest.raises(ValueError):
        validate({**VALID, "verdict": "proven_secure"}, CONTEXT)


@pytest.mark.parametrize(
    "model,thinking",
    [("stub-contract-test", True), ("deepseek-flash", True), ("deepseek-flash", False)],
)
def test_transport_schema_and_cache_with_local_stub(tmp_path, model, thinking):
    class Handler(BaseHTTPRequestHandler):
        calls = 0

        def log_message(self, *args):
            pass

        def do_POST(self):
            type(self).calls += 1
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            assert body["model"] == model
            if model == "deepseek-flash":
                assert body["thinking"] == {"type": "enabled" if thinking else "disabled"}
                assert ("temperature" not in body) is thinking
            else:
                assert "thinking" not in body
            assert body["response_format"]["type"] == "json_object"
            self.send_response(200)
            self.end_headers()
            self.wfile.write(
                json.dumps(
                    {
                        "choices": [{"message": {"content": json.dumps(VALID)}}],
                        "usage": {"total_tokens": 12},
                    }
                ).encode()
            )

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        kwargs = {
            "base_url": f"http://127.0.0.1:{server.server_port}/v1",
            "model": model,
            "api_key": "",
            "thinking": thinking,
        }
        first = review(CONTEXT, tmp_path, **kwargs)
        second = review(CONTEXT, tmp_path, **kwargs)
        assert not first["cache_hit"] and second["cache_hit"]
        assert Handler.calls == 1
    finally:
        server.shutdown()
        thread.join()
        server.server_close()


@pytest.fixture(autouse=True)
def enable_protocol_test_model(monkeypatch):
    monkeypatch.setenv("MICROBIND_LLM_ENABLED", "1")
