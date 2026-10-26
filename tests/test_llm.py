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


def test_transport_schema_and_cache_with_local_stub(tmp_path):
    class Handler(BaseHTTPRequestHandler):
        calls = 0

        def log_message(self, *args):
            pass

        def do_POST(self):
            type(self).calls += 1
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            assert body["model"] == "stub-contract-test"
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
            "model": "stub-contract-test",
            "api_key": "",
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
