import json

import pytest

import orchestrator.local_rag as local_rag_module
from knowledge.store import KnowledgeStore
from memory.store import ConversationMemory
from orchestrator.local_rag import (
    LocalRAGWorkflow, NoLocalEvidenceError, build_local_research,
)
from orchestrator.discovery import DiscoveredAgent, AgentDiscoveryError


class FakeClient:
    def __init__(self):
        self.calls = []

    async def send_text(self, url, text):
        self.calls.append((url, text))
        return "Knowledge can be retrieved locally. [src_1]"


def agent(url, skill, protocol="JSONRPC"):
    return DiscoveredAgent(
        name=skill, description="test", version="0.1", url=url,
        protocol_binding=protocol, protocol_version="1.0", skills=(skill,)
    )


def setup_stores(tmp_path):
    db = tmp_path / "data.sqlite3"
    knowledge = KnowledgeStore(db)
    memory = ConversationMemory(db)
    doc = tmp_path / "notes.md"
    doc.write_text("RAG retrieves project knowledge locally for answers.", encoding="utf-8")
    knowledge.ingest_file(doc)
    return knowledge, memory


def test_research_schema_and_citations(tmp_path):
    knowledge, _ = setup_stores(tmp_path)
    hits = knowledge.search("RAG knowledge")
    result = build_local_research("What is RAG knowledge?", hits)
    assert result.sources[0].id == "src_1"
    assert result.sources[0].url.startswith("local://document/")
    assert result.claims[0].evidence_ids == ["evidence_1"]
    assert result.evidence[0].source_id == "src_1"
    assert "retrieves" in result.evidence[0].text


@pytest.mark.asyncio
async def test_cloud_opt_in_is_required(tmp_path):
    knowledge, memory = setup_stores(tmp_path)
    fake = FakeClient()
    workflow = LocalRAGWorkflow(knowledge=knowledge, memory=memory, client=fake)
    with pytest.raises(PermissionError, match="allow-cloud"):
        await workflow.run("RAG knowledge")
    assert fake.calls == []


@pytest.mark.asyncio
async def test_no_hits_never_calls_network(tmp_path):
    knowledge, memory = setup_stores(tmp_path)
    fake = FakeClient()
    workflow = LocalRAGWorkflow(knowledge=knowledge, memory=memory, client=fake)
    with pytest.raises(NoLocalEvidenceError):
        await workflow.run("unmatchableuniquekeyword", allow_cloud=True)
    assert fake.calls == []


@pytest.mark.asyncio
async def test_uses_writer_and_verifier_with_opt_in(tmp_path, monkeypatch):
    knowledge, memory = setup_stores(tmp_path)
    fake = FakeClient()
    discovered = []

    async def fake_discover(url):
        discovered.append(url)
        if url == local_rag_module.settings.writer_agent_url:
            return agent(url, "write_explanation")
        return agent(url, "verify_answer")

    class FakeRevisionLoop:
        def __init__(self, **kwargs):
            assert kwargs["writer_url"] == local_rag_module.settings.writer_agent_url
            assert kwargs["verifier_url"] == local_rag_module.settings.verifier_agent_url

        async def run(self, research_json, initial_draft):
            research = json.loads(research_json)
            assert research["sources"][0]["id"] == "src_1"
            assert initial_draft.endswith("[src_1]")
            return initial_draft

    monkeypatch.setattr(local_rag_module, "discover_agent", fake_discover)
    monkeypatch.setattr(local_rag_module, "RevisionLoop", FakeRevisionLoop)
    workflow = LocalRAGWorkflow(knowledge=knowledge, memory=memory, client=fake)
    result = await workflow.run(
        "RAG knowledge", allow_cloud=True,
        conversation_id="sprint", save_history=True,
    )
    assert result.verified
    assert len(discovered) == 2
    assert len(fake.calls) == 1
    assert fake.calls[0][0] == local_rag_module.settings.writer_agent_url
    assert [m.role for m in memory.history("sprint")] == ["user", "assistant"]


@pytest.mark.asyncio
async def test_rejects_incompatible_writer(tmp_path, monkeypatch):
    knowledge, memory = setup_stores(tmp_path)
    fake = FakeClient()

    async def fake_discover(url):
        return agent(url, "write_explanation", protocol="NOT_JSONRPC")

    monkeypatch.setattr(local_rag_module, "discover_agent", fake_discover)
    workflow = LocalRAGWorkflow(knowledge=knowledge, memory=memory, client=fake)
    with pytest.raises(AgentDiscoveryError):
        await workflow.run("RAG knowledge", allow_cloud=True)
    assert fake.calls == []


@pytest.mark.asyncio
async def test_history_not_saved_without_opt_in(tmp_path, monkeypatch):
    knowledge, memory = setup_stores(tmp_path)
    fake = FakeClient()

    async def fake_discover(url):
        if url == local_rag_module.settings.writer_agent_url:
            return agent(url, "write_explanation")
        return agent(url, "verify_answer")

    class FakeRevisionLoop:
        def __init__(self, **kwargs):
            pass
        async def run(self, research_json, initial_draft):
            return initial_draft

    monkeypatch.setattr(local_rag_module, "discover_agent", fake_discover)
    monkeypatch.setattr(local_rag_module, "RevisionLoop", FakeRevisionLoop)
    workflow = LocalRAGWorkflow(knowledge=knowledge, memory=memory, client=fake)
    await workflow.run("RAG knowledge", allow_cloud=True, conversation_id="sprint")
    assert memory.history("sprint") == []
