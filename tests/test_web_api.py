"""Web API contract tests. No network, Groq, or A2A servers required."""
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from web_api.app import create_app


@pytest.fixture
def api(tmp_path):
    calls = {"routed": [], "rag": []}

    class Routed:
        async def run(self, question):
            calls["routed"].append(question)
            return SimpleNamespace(
                final_answer="PROPOSED PLAN (not executed)\n1. Test it",
                decision=SimpleNamespace(route="plan_only"),
                verified=False,
                research=None,
            )

    class Rag:
        async def run(self, question, *, allow_cloud, save_history):
            calls["rag"].append((question, allow_cloud, save_history))
            source = SimpleNamespace(id="src_1", title="notes.txt", url="local://document/1")
            return SimpleNamespace(
                answer="A documented answer. [src_1]",
                verified=True,
                research=SimpleNamespace(sources=[source]),
            )

    app = create_app(
        db_path=tmp_path / "assistant.sqlite3",
        routed_factory=Routed,
        rag_factory=Rag,
    )
    with TestClient(app) as client:
        yield client, calls, tmp_path


def chat(client, **changes):
    payload = {
        "message": "How does the project work?",
        "conversation_id": "session1",
        "mode": "auto",
        "allow_cloud": False,
        "save_history": False,
    }
    payload.update(changes)
    return client.post("/api/chat", json=payload)


def test_api_health_and_initial_empty_state(api):
    client, _, _ = api
    assert client.get("/api/health").json()["status"] == "ok"
    assert client.get("/api/documents").json() == []
    assert client.get("/api/conversations").json() == []


def test_upload_search_and_delete_document(api):
    client, _, tmp_path = api
    uploaded = client.post("/api/documents", json={
        "filename": "my-notes.md",
        "content": "A2A agents coordinate research, writing and verification using JSONRPC.",
    })
    assert uploaded.status_code == 201
    document_id = uploaded.json()["id"]
    assert client.get("/api/documents").json()[0]["title"] == "my-notes.md"
    result = client.get("/api/search", params={"q": "verification"}).json()
    assert len(result) == 1
    assert "JSONRPC" in result[0]["snippet"]
    assert client.delete(f"/api/documents/{document_id}").json()["deleted"]
    assert client.get("/api/documents").json() == []
    assert not any((tmp_path / "uploads").rglob("*.md"))


@pytest.mark.parametrize("filename", ["../secret.md", "nested/test.md", r"C:\\secret.txt", "bad.pdf", "CON.txt", "notes:evil.txt"])
def test_upload_rejects_unsafe_or_unsupported_names(api, filename):
    client, _, _ = api
    response = client.post("/api/documents", json={"filename": filename, "content": "Hello"})
    assert response.status_code == 422


def test_upload_rejects_too_large_or_empty(api):
    client, _, _ = api
    assert client.post("/api/documents", json={"filename": "big.txt", "content": "x" * (2 * 1024 * 1024 + 1)}).status_code == 422
    assert client.post("/api/documents", json={"filename": "a.txt", "content": "  "}).status_code == 422


@pytest.mark.parametrize("mode", ["auto", "documents"])
def test_cloud_access_requires_explicit_consent(api, mode):
    client, calls, _ = api
    reply = chat(client, mode=mode)
    assert reply.status_code == 403
    assert calls["routed"] == []
    assert calls["rag"] == []


def test_local_search_never_calls_agents(api):
    client, calls, _ = api
    reply = chat(client, mode="search", allow_cloud=False)
    assert reply.status_code == 200
    assert reply.json()["route"] == "search"
    assert reply.json()["verified"] is False
    assert calls["routed"] == calls["rag"] == []


def test_planner_route_does_not_claim_verification(api):
    client, calls, _ = api
    reply = chat(client, mode="auto", allow_cloud=True)
    assert reply.status_code == 200
    assert reply.json()["route"] == "plan_only"
    assert reply.json()["verified"] is False
    assert calls["routed"] == ["How does the project work?"]
    assert client.get("/api/conversations").json() == []


def test_document_route_returns_citations_and_saves_opted_in_history(api):
    client, calls, _ = api
    reply = chat(client, mode="documents", allow_cloud=True, save_history=True)
    assert reply.status_code == 200
    data = reply.json()
    assert data["verified"] is True
    assert data["sources"][0]["id"] == "src_1"
    assert calls["rag"] == [("How does the project work?", True, False)]
    history = client.get("/api/conversations/session1").json()
    assert [item["role"] for item in history] == ["user", "assistant"]
    assert len(client.get("/api/conversations").json()) == 1
    assert client.delete("/api/conversations/session1").json()["deleted"] is True
    assert client.get("/api/conversations/session1").status_code == 404


def test_invalid_conversation_id_is_rejected(api):
    client, _, _ = api
    assert chat(client, mode="search", conversation_id="../escape").status_code == 422
    assert client.get("/api/conversations/hello%20world").status_code == 422


def test_untrusted_host_is_rejected(api):
    client, _, _ = api
    response = client.get("/api/health", headers={"host": "evil.example"})
    assert response.status_code == 400
