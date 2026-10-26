import json
import select
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

import pytest

from microbind.engine import Analyzer
from microbind.evidence_tools import EvidenceTools
from microbind.frontend import Project
from microbind.smart import review_one

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def evidence():
    p = Project(ROOT / "demo/project.yml")
    report = Analyzer(p).run()
    return EvidenceTools(p, report), next(
        f for f in report["results"] if f["status"] == "suspected"
    )


def test_model_tool_loop_evidence_and_cache(evidence, tmp_path):
    tools, finding = evidence
    queries = []

    def sender(messages, schemas, **options):
        queries.append(messages.copy())
        if len(queries) == 1:
            msg = {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "t1",
                        "type": "function",
                        "function": {
                            "name": "get_method",
                            "arguments": json.dumps({"method_id": finding["entry"]}),
                        },
                    }
                ],
            }
        else:
            assert messages[-1]["role"] == "tool"
            assert finding["entry"] in json.loads(messages[-1]["content"])["evidence_ids"]
            msg = {
                "content": json.dumps(
                    {
                        "verdict": "suspected",
                        "explanation": "入口缺少目标归属检查。",
                        "required_conditions": ["owner"],
                        "evidence_ids": [finding["entry"]],
                        "suggested_test": "交换同租户用户后读取该订单。",
                    }
                )
            }
        return {"choices": [{"message": msg}], "usage": {"total_tokens": 100}}

    kw = {
        "sender": sender,
        "base_url": "https://model.example/v1",
        "model": "test-stub",
        "api_key": "",
    }
    result = review_one(tools, finding, tmp_path, **kw)
    assert len(result["tool_calls"]) == 1
    assert not result["cache_hit"]
    assert review_one(tools, finding, tmp_path, **kw)["cache_hit"]
    assert len(queries) == 2
    assert finding["status"] == "suspected"


def test_model_cannot_invent_evidence(evidence, tmp_path):
    tools, finding = evidence

    def sender(*a, **k):
        return {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "verdict": "covered",
                                "explanation": "ok",
                                "required_conditions": [],
                                "evidence_ids": ["invented-evidence"],
                                "suggested_test": "test",
                            }
                        )
                    }
                }
            ]
        }

    with pytest.raises(ValueError, match="absent evidence"):
        review_one(
            tools,
            finding,
            tmp_path,
            sender=sender,
            base_url="https://model.example/v1",
            model="stub",
        )


def test_tool_budget_and_no_arbitrary_read(evidence, tmp_path):
    tools, finding = evidence
    with pytest.raises(ValueError):
        tools.call("read_file", {"path": "/etc/passwd"})
    with pytest.raises(KeyError):
        tools.call("get_method", {"method_id": "../../secret"})

    def sender(*a, **k):
        return {
            "choices": [
                {
                    "message": {
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "t",
                                "function": {
                                    "name": "get_policy",
                                    "arguments": json.dumps({"finding_id": finding["id"]}),
                                },
                            }
                        ],
                    }
                }
            ]
        }

    with pytest.raises(ValueError, match="budget"):
        review_one(
            tools,
            finding,
            tmp_path,
            sender=sender,
            base_url="https://model.example/v1",
            model="stub",
            rounds=1,
        )


def test_official_mcp_stdio_roundtrip():
    p = subprocess.Popen(
        [sys.executable, "-m", "microbind.mcp_server", str(ROOT / "demo/project.yml")],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )

    def send(value):
        p.stdin.write(json.dumps(value) + "\n")
        p.stdin.flush()

    def read():
        assert select.select([p.stdout], [], [], 20)[0], "MCP response timed out"
        return json.loads(p.stdout.readline())

    try:
        send(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-11-25",
                    "capabilities": {},
                    "clientInfo": {"name": "microbind-test", "version": "1.0"},
                },
            }
        )
        assert "tools" in read()["result"]["capabilities"]
        send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        send({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        assert len(read()["result"]["tools"]) == 5
        send(
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": "search_methods", "arguments": {"query": "requireOwner"}},
            }
        )
        result = read()["result"]
        assert not result.get("isError", False)
        assert "requireOwner" in json.dumps(result)
    finally:
        p.terminate()
        try:
            p.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            p.kill()
            p.communicate()


def test_chat_completions_http_transport(evidence, tmp_path):
    tools, finding = evidence
    received = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            assert self.path == "/v1/chat/completions"
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            received.append(body)
            if len(received) == 1:
                assert {t["function"]["name"] for t in body["tools"]} == {
                    s["name"] for s in tools.schemas()
                }
                msg = {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "http-call",
                            "type": "function",
                            "function": {
                                "name": "get_sql",
                                "arguments": json.dumps(
                                    {"method_id": finding["operation"]["method"]}
                                ),
                            },
                        }
                    ],
                }
            else:
                msg = {
                    "role": "assistant",
                    "content": json.dumps(
                        {
                            "verdict": "needs_review",
                            "explanation": "传输与工具协议测试，不代表真实模型判断。",
                            "required_conditions": [],
                            "evidence_ids": ["sql:" + finding["operation"]["method"]],
                            "suggested_test": "检查对象归属。",
                        }
                    ),
                }
            raw = json.dumps({"choices": [{"message": msg}]}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        result = review_one(
            tools,
            finding,
            tmp_path,
            base_url=f"http://127.0.0.1:{server.server_port}/v1",
            model="protocol-test",
            api_key="dummy",
        )
        assert len(received) == 2
        assert result["review"]["verdict"] == "needs_review"
        assert result["tool_calls"][0]["name"] == "get_sql"
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


@pytest.fixture(autouse=True)
def enable_protocol_test_model(monkeypatch):
    monkeypatch.setenv("MICROBIND_LLM_ENABLED", "1")
