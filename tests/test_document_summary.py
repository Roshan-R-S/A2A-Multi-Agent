"""Phase 3 full-document summary tests; no network or paid model calls."""
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from knowledge.store import KnowledgeStore, SummaryLimitError
from web_api.app import create_app


def _seed(tmp_path: Path, content: str = "Intro explains the project.\nResearch agents gather citations.\nVerifier checks facts."):
    kb = KnowledgeStore(tmp_path / "summary.sqlite3")
    path = tmp_path / "guide.md"
    path.write_text(content, encoding="utf-8")
    entry = kb.ingest_file(path)
    return kb, entry.document_id


def test_ordered_full_document_retrieval(tmp_path):
    text = " ".join(f"topic{i}" for i in range(900))
    kb, doc_id = _seed(tmp_path, text)
    document = kb.read_document_for_summary(doc_id)
    assert document is not None
    assert document.title == "guide.md"
    assert len(document.chunks) >= 4
    assert [c.position for c in document.chunks] == list(range(len(document.chunks)))
    assert document.chunks[0].body.startswith("topic0 ")
    assert "topic899" in document.chunks[-1].body
    assert kb.read_document_for_summary(doc_id + 1234) is None
    assert kb.read_document_for_summary(-4) is None


def test_summary_rejects_large_document_but_search_still_works(tmp_path):
    kb, doc_id = _seed(tmp_path, "research " * 11000)
    with pytest.raises(SummaryLimitError, match="too large"):
        kb.read_document_for_summary(doc_id)
    assert kb.search("research")


def test_split_batches_includes_every_ordered_chunk(tmp_path):
    from orchestrator.document_summary import BATCH_CHARS, split_into_batches
    kb, doc_id = _seed(tmp_path, " ".join(f"word{i}" for i in range(2500)))
    document = kb.read_document_for_summary(doc_id)
    batches = split_into_batches(document)
    combined = "".join(batches)
    assert len(batches) > 1
    assert all(0 < len(b) <= BATCH_CHARS for b in batches)
    for chunk in document.chunks:
        assert f"[INDEXED CHUNK {chunk.position + 1}]\n{chunk.body}" in combined


@pytest.mark.asyncio
async def test_summary_requires_consent_before_reading_or_calling_model(tmp_path):
    from orchestrator.document_summary import DocumentSummaryWorkflow
    kb, doc_id = _seed(tmp_path)
    seen = []

    async def segment(text):
        seen.append(text)
        return "notes"

    workflow = DocumentSummaryWorkflow(knowledge=kb, summarize_segment=segment)
    with pytest.raises(PermissionError, match="consent"):
        await workflow.run(doc_id, allow_cloud=False)
    assert seen == []
    with pytest.raises(LookupError, match="not found"):
        await workflow.run(999999, allow_cloud=True)
    assert seen == []


@pytest.mark.asyncio
async def test_summary_uses_all_batches_then_writer_and_verifier(tmp_path, monkeypatch):
    import orchestrator.document_summary as module
    from agents.research.schemas import ResearchResult

    kb, doc_id = _seed(tmp_path, " ".join(f"topic{i}" for i in range(3200)))
    seen = []
    researches = []
    async def map_stage(text):
        seen.append(text)
        return "The segment records some documented implementation details."

    async def fake_discover(url):
        skill = "write_explanation" if "8002" in url else "verify_answer"
        return SimpleNamespace(protocol_binding="JSONRPC", skills={skill}, url=url)

    class Client:
        async def send_text(self, url, payload):
            researches.append(ResearchResult.model_validate_json(payload))
            return "A draft based on indexed evidence. [src_1]"

    class Loop:
        def __init__(self, **kwargs):
            pass
        async def run(self, *, research_json, initial_draft):
            assert initial_draft
            return "Verified summary. [src_1]"

    monkeypatch.setattr(module, "discover_agent", fake_discover)
    monkeypatch.setattr(module, "RevisionLoop", Loop)
    # Use a lightweight config stub to avoid relying on a live .env.
    monkeypatch.setattr(module, "settings", SimpleNamespace(
        writer_agent_url="http://127.0.0.1:8002",
        verifier_agent_url="http://127.0.0.1:8003",
    ))
    summary = await module.DocumentSummaryWorkflow(
        knowledge=kb, client=Client(), summarize_segment=map_stage,
    ).run(doc_id, allow_cloud=True)
    assert len(seen) >= 2
    assert summary.segments == len(seen)
    assert summary.covered_chunks == len(kb.read_document_for_summary(doc_id).chunks)
    assert summary.verified
    assert len(summary.sources) == len(seen)
    assert [s["id"] for s in summary.sources] == [f"src_{i}" for i in range(1, len(seen) + 1)]
    assert len(researches) == 1
    assert len(researches[0].evidence) == len(seen)
    assert [ev.text for ev in researches[0].evidence] == [
        "The segment records some documented implementation details."
        for _ in seen
    ]
    assert all(len(ev.text) <= module.MAX_NOTE_CHARS for ev in researches[0].evidence)


def test_summary_api_consent_and_success(tmp_path):
    calls = []
    class FakeSummary:
        async def run(self, document_id, *, allow_cloud):
            calls.append((document_id, allow_cloud))
            return SimpleNamespace(
                document_id=document_id, title="guide.md", answer="This is a cited summary. [src_1]",
                covered_chunks=3, segments=1, verified=True,
                sources=[{"id": "src_1", "title": "guide.md part 1", "url": "local://document/1#part-1"}],
            )

    app = create_app(db_path=tmp_path / "web.sqlite3", summary_factory=FakeSummary)
    with TestClient(app) as client:
        denied = client.post("/api/documents/1/summary", json={"allow_cloud": False})
        assert denied.status_code == 403
        assert calls == []
        assert client.post("/api/documents/0/summary", json={"allow_cloud": True}).status_code == 404
        assert calls == []
        accepted = client.post("/api/documents/1/summary", json={"allow_cloud": True})
        assert accepted.status_code == 200
        assert accepted.json()["covered_chunks"] == 3
        assert accepted.json()["verified"] is True
        assert calls == [(1, True)]


def test_summary_api_missing_oversized_and_failed_workflow(tmp_path):
    class FakeSummary:
        async def run(self, document_id, *, allow_cloud):
            if document_id == 1:
                raise LookupError("Indexed document not found.")
            if document_id == 2:
                raise SummaryLimitError("Document is too large")
            raise RuntimeError("Private provider traceback details must not leak")

    app = create_app(db_path=tmp_path / "web.sqlite3", summary_factory=FakeSummary)
    with TestClient(app) as client:
        assert client.post("/api/documents/1/summary", json={"allow_cloud": True}).status_code == 404
        assert client.post("/api/documents/2/summary", json={"allow_cloud": True}).status_code == 413
        failure = client.post("/api/documents/3/summary", json={"allow_cloud": True})
        assert failure.status_code == 502
        assert "Private provider" not in failure.text

@pytest.mark.asyncio
async def test_overlong_segment_notes_are_compressed_without_truncating(tmp_path, monkeypatch):
    """Oversized Groq notes should be repaired once, not rejected or sliced."""
    import orchestrator.document_summary as module

    kb, document_id = _seed(tmp_path)
    attempts = []
    long_notes = "section details " * 450  # Over 5,000 characters
    short_notes = "Introduction, architecture, setup and important limitations."

    async def map_stage(_segment):
        return long_notes

    async def compress(notes):
        attempts.append(notes)
        return short_notes

    async def fake_discover(url):
        skill = "write_explanation" if "8002" in url else "verify_answer"
        return SimpleNamespace(protocol_binding="JSONRPC", skills={skill}, url=url)

    class Client:
        async def send_text(self, url, payload):
            research = module.ResearchResult.model_validate_json(payload)
            assert research.claims[0].text == short_notes
            return "Draft. [src_1]"

    class Loop:
        def __init__(self, **kwargs):
            pass

        async def run(self, *, research_json, initial_draft):
            return initial_draft

    monkeypatch.setattr(module, "discover_agent", fake_discover)
    monkeypatch.setattr(module, "RevisionLoop", Loop)
    monkeypatch.setattr(module, "settings", SimpleNamespace(
        writer_agent_url="http://127.0.0.1:8002",
        verifier_agent_url="http://127.0.0.1:8003",
    ))

    result = await module.DocumentSummaryWorkflow(
        knowledge=kb, client=Client(),
        summarize_segment=map_stage, compress_notes=compress,
    ).run(document_id, allow_cloud=True)

    assert result.verified
    assert attempts == [long_notes.strip()]
    assert result.covered_chunks == 1


@pytest.mark.asyncio
async def test_recovery_still_enforces_safety_limit_and_stops_before_agents(tmp_path, monkeypatch):
    """If the model refuses to shorten notes, fail explicitly and safely."""
    import orchestrator.document_summary as module

    kb, document_id = _seed(tmp_path)
    calls = []

    async def map_stage(_segment):
        return "x" * (module.MAX_NOTE_CHARS + 100)

    async def compress(notes):
        calls.append(len(notes))
        return notes  # The retry did not help.

    async def unexpected_discover(_url):
        raise AssertionError("Agents must not be contacted for invalid notes")

    monkeypatch.setattr(module, "discover_agent", unexpected_discover)
    with pytest.raises(RuntimeError, match="safety limit"):
        await module.DocumentSummaryWorkflow(
            knowledge=kb, summarize_segment=map_stage,
            compress_notes=compress,
        ).run(document_id, allow_cloud=True)
    assert calls == [module.MAX_NOTE_CHARS + 100]


@pytest.mark.asyncio
async def test_empty_segment_notes_fail_without_retrying(tmp_path):
    from orchestrator.document_summary import DocumentSummaryWorkflow

    kb, document_id = _seed(tmp_path)

    async def map_stage(_segment):
        return "   "

    async def compress(_notes):
        raise AssertionError("Do not attempt to compress empty notes")

    with pytest.raises(RuntimeError, match="empty notes"):
        await DocumentSummaryWorkflow(
            knowledge=kb, summarize_segment=map_stage,
            compress_notes=compress,
        ).run(document_id, allow_cloud=True)


@pytest.mark.asyncio
async def test_large_document_reduction_keeps_revision_payload_compact(tmp_path, monkeypatch):
    """All raw batches are read, but they are NOT copied into A2A evidence."""
    import orchestrator.document_summary as module
    from agents.research.schemas import ResearchResult

    kb, document_id = _seed(tmp_path, " ".join("section" + str(i) for i in range(3000)))
    seen = []
    research_payloads = []
    compact_note = "Technical overview. Architecture and configuration. " * 8

    async def summarize(batch):
        seen.append(batch)
        return compact_note

    async def fake_discover(url):
        skill = "write_explanation" if "8002" in url else "verify_answer"
        return SimpleNamespace(protocol_binding="JSONRPC", skills={skill}, url=url)

    class Client:
        async def send_text(self, url, payload):
            research_payloads.append(payload)
            return "Draft with supported citations. [src_1]"

    class Loop:
        def __init__(self, **kwargs):
            pass

        async def run(self, *, research_json, initial_draft):
            assert len(research_json) <= module.MAX_RESEARCH_JSON_CHARS
            return initial_draft

    monkeypatch.setattr(module, "discover_agent", fake_discover)
    monkeypatch.setattr(module, "RevisionLoop", Loop)
    monkeypatch.setattr(module, "settings", SimpleNamespace(
        writer_agent_url="http://127.0.0.1:8002",
        verifier_agent_url="http://127.0.0.1:8003",
    ))
    result = await module.DocumentSummaryWorkflow(
        knowledge=kb, client=Client(), summarize_segment=summarize,
    ).run(document_id, allow_cloud=True)

    assert len(seen) > 1
    assert result.segments == len(seen)
    research = ResearchResult.model_validate_json(research_payloads[0])
    assert len(research.evidence) == len(seen)
    assert sum(len(item.text) for item in research.evidence) <= module.MAX_TOTAL_NOTE_CHARS
    assert all("[INDEXED CHUNK" not in item.text for item in research.evidence)
    assert all(len(item.text) <= module.MAX_NOTE_CHARS for item in research.evidence)
    assert any("[INDEXED CHUNK" in item for item in seen)


@pytest.mark.asyncio
async def test_per_segment_budget_still_enforced_for_many_segments(tmp_path, monkeypatch):
    import orchestrator.document_summary as module
    kb, document_id = _seed(tmp_path, " ".join("topic" + str(i) for i in range(3600)))
    document = kb.read_document_for_summary(document_id)
    segment_count = len(module.split_into_batches(document))
    limit = min(module.MAX_NOTE_CHARS, module.MAX_TOTAL_NOTE_CHARS // segment_count)
    attempts = []

    async def summarize(_batch):
        return "x" * (limit + 1)

    async def compress(_notes):
        attempts.append(1)
        return "y" * (limit + 1)

    async def fail_if_discover(_url):
        raise AssertionError("Over-budget evidence must be rejected before agents")

    monkeypatch.setattr(module, "discover_agent", fail_if_discover)
    with pytest.raises(RuntimeError, match="safety limit"):
        await module.DocumentSummaryWorkflow(
            knowledge=kb, summarize_segment=summarize, compress_notes=compress,
        ).run(document_id, allow_cloud=True)
    assert len(attempts) == 1


def test_summary_api_groq_rate_limit_is_clear_and_sanitized(tmp_path):
    class FakeSummary:
        async def run(self, document_id, *, allow_cloud):
            raise RuntimeError(
                "Groq error code: 413 - Request too large for model "
                "on tokens per minute: Limit 8000, Requested 8780; "
                "organization org_PRIVATE_VALUE"
            )

    app = create_app(db_path=tmp_path / "web.sqlite3", summary_factory=FakeSummary)
    with TestClient(app) as client:
        reply = client.post("/api/documents/1/summary", json={"allow_cloud": True})
        assert reply.status_code == 429
        assert "oversized model request" in reply.json()["detail"]
        assert "org_PRIVATE_VALUE" not in reply.text


def test_extractive_fallback_is_bounded_and_reaches_later_topics():
    from orchestrator.document_summary import _extractive_notes

    original = '\n'.join(
        f'## Chapter {i}: {topic}\nThis chapter documents {topic} for the project. '
        f'It describes setup and limitations affecting {topic}.'
        for i, topic in enumerate(
            ['overview', 'architecture', 'services', 'search', 'security',
             'frontend', 'memory', 'deployment', 'testing', 'conclusion'], start=1
        )
    )
    result = _extractive_notes(original, 550)
    assert len(result) <= 550
    assert 'Selected note excerpts (details omitted)' in result
    assert 'Chapter 1' in result or 'overview' in result
    assert 'conclusion' in result


@pytest.mark.asyncio
async def test_empty_groq_compression_reuses_existing_notes_locally(tmp_path, monkeypatch):
    """Exact observed production error must not abort the whole workflow."""
    import orchestrator.document_summary as module

    kb, document_id = _seed(tmp_path)
    extracted = (
        '## Overview\nThe README describes a local A2A multi-agent system and its goals.\n'
        '## Architecture\nFour cooperating agents organize research, writing and verification.\n'
        '## Configuration\nThe README describes port mappings and settings for Windows.\n'
        '## Security\nThe README documents privacy consent, local storage and caveats.\n'
        '## Testing\nThe README lists validation commands and build checks.\n'
    ) * 4
    assert len(extracted) > module.MAX_NOTE_CHARS
    compressed_calls = []
    collected = []

    async def map_stage(_segment):
        return extracted

    async def compress(_notes):
        compressed_calls.append(1)
        raise RuntimeError('Groq returned an empty response.')

    async def fake_discover(url):
        skill = 'write_explanation' if '8002' in url else 'verify_answer'
        return SimpleNamespace(protocol_binding='JSONRPC', skills={skill}, url=url)

    class Client:
        async def send_text(self, url, payload):
            research = module.ResearchResult.model_validate_json(payload)
            collected.append(research)
            assert 'Selected note excerpts (details omitted)' in research.evidence[0].text
            assert len(research.evidence[0].text) <= module.MAX_NOTE_CHARS
            assert any('extractive snippets' in caveat for caveat in research.caveats)
            return 'Grounded draft. [src_1]'

    class Loop:
        def __init__(self, **kwargs):
            pass
        async def run(self, *, research_json, initial_draft):
            return initial_draft

    monkeypatch.setattr(module, 'discover_agent', fake_discover)
    monkeypatch.setattr(module, 'RevisionLoop', Loop)
    monkeypatch.setattr(module, 'settings', SimpleNamespace(
        writer_agent_url='http://127.0.0.1:8002',
        verifier_agent_url='http://127.0.0.1:8003',
    ))

    result = await module.DocumentSummaryWorkflow(
        knowledge=kb, client=Client(), summarize_segment=map_stage,
        compress_notes=compress,
    ).run(document_id, allow_cloud=True)
    assert result.verified
    assert len(compressed_calls) == result.segments
    assert len(collected) == 1


@pytest.mark.asyncio
async def test_empty_text_compression_also_uses_local_fallback(tmp_path, monkeypatch):
    import orchestrator.document_summary as module
    kb, document_id = _seed(tmp_path)

    async def segment(_text):
        return ('Introduction explains the platform.\n'
                'Architecture documents the cooperating agents.\n'
                'Privacy requires user consent.\n') * 15

    async def empty(_notes):
        return '  '

    async def sentinel_discover(_url):
        raise RuntimeError('AFTER_FALLBACK')

    monkeypatch.setattr(module, 'discover_agent', sentinel_discover)
    monkeypatch.setattr(module, 'settings', SimpleNamespace(
        writer_agent_url='http://127.0.0.1:8002',
        verifier_agent_url='http://127.0.0.1:8003',
    ))
    with pytest.raises(RuntimeError, match='AFTER_FALLBACK'):
        await module.DocumentSummaryWorkflow(
            knowledge=kb, summarize_segment=segment, compress_notes=empty,
        ).run(document_id, allow_cloud=True)


@pytest.mark.asyncio
async def test_provider_errors_other_than_empty_are_not_swallowed(tmp_path, monkeypatch):
    import orchestrator.document_summary as module
    kb, document_id = _seed(tmp_path)

    async def long_map(_text):
        return 'Meaningful notes about the architecture and deployment. ' * 25

    async def rate_limit(_text):
        raise RuntimeError('Error code: 429 - rate_limit_exceeded')

    async def should_not_discover(_url):
        raise AssertionError('Must not contact agents after quota failure')

    monkeypatch.setattr(module, 'discover_agent', should_not_discover)
    with pytest.raises(RuntimeError, match='rate_limit_exceeded'):
        await module.DocumentSummaryWorkflow(
            knowledge=kb, summarize_segment=long_map, compress_notes=rate_limit,
        ).run(document_id, allow_cloud=True)


@pytest.mark.asyncio
async def test_citation_rejection_returns_unverified_attributed_notes(tmp_path, monkeypatch):
    """A failed citation check must not become a false VERIFIED response."""
    import orchestrator.document_summary as module

    kb, doc_id = _seed(tmp_path, "Architecture explains the Reader and Writer agents.")
    async def map_stage(_):
        return "The project includes a reader and a writer."
    async def fake_discover(url):
        skill = "write_explanation" if "8002" in url else "verify_answer"
        return SimpleNamespace(protocol_binding="JSONRPC", skills={skill}, url=url)
    class Client:
        async def send_text(self, url, payload):
            return "An uncited draft."
    class Loop:
        def __init__(self, **kwargs):
            assert kwargs["max_revisions"] == 0  # avoid extra costly revision
        async def run(self, **kwargs):
            raise RuntimeError("Verification failed after 0 revision attempts. "
                               "Final feedback: Add source citations to statements.")
    monkeypatch.setattr(module, "discover_agent", fake_discover)
    monkeypatch.setattr(module, "RevisionLoop", Loop)
    monkeypatch.setattr(module, "settings", SimpleNamespace(
        writer_agent_url="http://127.0.0.1:8002",
        verifier_agent_url="http://127.0.0.1:8003",
    ))
    output = await module.DocumentSummaryWorkflow(
        knowledge=kb, client=Client(), summarize_segment=map_stage,
    ).run(doc_id, allow_cloud=True)
    assert output.verified is False
    assert "NOT AGENT VERIFIED" in output.answer
    assert "reader and a writer" in output.answer
    assert "[src_1]" in output.answer
    assert output.covered_chunks == 1


@pytest.mark.asyncio
async def test_non_citation_verification_or_provider_errors_propagate(tmp_path, monkeypatch):
    """Never turn non-citation failures into an apparently usable summary."""
    import orchestrator.document_summary as module
    kb, doc_id = _seed(tmp_path)
    async def map_stage(_):
        return "Research agents collect source citations."
    async def fake_discover(url):
        skill = "write_explanation" if "8002" in url else "verify_answer"
        return SimpleNamespace(protocol_binding="JSONRPC", skills={skill}, url=url)
    class Client:
        async def send_text(self, url, payload):
            return "A draft."
    class Loop:
        def __init__(self, **kwargs):
            pass
        async def run(self, **kwargs):
            raise RuntimeError("Verifier returned invalid JSON.")
    monkeypatch.setattr(module, "discover_agent", fake_discover)
    monkeypatch.setattr(module, "RevisionLoop", Loop)
    monkeypatch.setattr(module, "settings", SimpleNamespace(
        writer_agent_url="http://127.0.0.1:8002",
        verifier_agent_url="http://127.0.0.1:8003",
    ))
    with pytest.raises(RuntimeError, match="invalid JSON"):
        await module.DocumentSummaryWorkflow(
            knowledge=kb, client=Client(), summarize_segment=map_stage,
        ).run(doc_id, allow_cloud=True)


@pytest.mark.asyncio
async def test_default_overlong_notes_use_local_compression_no_second_groq(tmp_path, monkeypatch):
    """Default oversized-note handling avoids a second model call."""
    import orchestrator.document_summary as module
    kb, doc_id = _seed(tmp_path)
    calls = []
    async def map_stage(_):
        calls.append("segment")
        return ("Architecture covers several cooperating agents and endpoints. " * 32)
    async def fake_discover(url):
        skill = "write_explanation" if "8002" in url else "verify_answer"
        return SimpleNamespace(protocol_binding="JSONRPC", skills={skill}, url=url)
    class Client:
        async def send_text(self, url, payload):
            research = module.ResearchResult.model_validate_json(payload)
            assert "Selected note excerpts (details omitted)" in research.evidence[0].text
            return "Cited draft. [src_1]"
    class Loop:
        def __init__(self, **kwargs):
            pass
        async def run(self, **kwargs):
            return "Verified draft. [src_1]"
    monkeypatch.setattr(module, "discover_agent", fake_discover)
    monkeypatch.setattr(module, "RevisionLoop", Loop)
    monkeypatch.setattr(module, "settings", SimpleNamespace(
        writer_agent_url="http://127.0.0.1:8002",
        verifier_agent_url="http://127.0.0.1:8003",
    ))
    output = await module.DocumentSummaryWorkflow(
        knowledge=kb, client=Client(), summarize_segment=map_stage,
    ).run(doc_id, allow_cloud=True)
    assert output.verified is True
    assert calls == ["segment"]
