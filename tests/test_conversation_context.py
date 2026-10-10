"""Context-aware memory remains local unless request explicitly opts in."""
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from memory.store import ConversationMemory
from orchestrator.conversation_context import (
    MAX_HISTORY_MESSAGES,
    MAX_HISTORY_CHARS,
    MAX_MESSAGE_CHARS,
    contextualize,
)
from web_api.app import create_app


def test_no_saved_messages_returns_unchanged_question(tmp_path):
    store = ConversationMemory(tmp_path / 'db.sqlite3')
    context = contextualize(store, 'one', 'What next?')
    assert context.prompt == 'What next?'
    assert context.message_count == 0


def test_recent_is_bounded_and_ordered(tmp_path):
    store = ConversationMemory(tmp_path / 'db.sqlite3')
    for i in range(9):
        store.add_exchange('one', f'user{i} ' + ('x' * 800), f'bot{i} ' + ('y' * 800))
    context = contextualize(store, 'one', 'What does it mean?')
    assert 1 <= context.message_count <= MAX_HISTORY_MESSAGES
    assert len(context.prompt) < 4000
    assert 'user8' in context.prompt
    assert 'user0' not in context.prompt
    assert 'CURRENT USER QUESTION:\nWhat does it mean?' in context.prompt
    assert 'user8' in context.prompt and context.prompt.index('user8') < context.prompt.index('bot8')
    assert len('x'*800) > MAX_MESSAGE_CHARS


def test_context_isolation_and_deletion(tmp_path):
    store = ConversationMemory(tmp_path / 'db.sqlite3')
    store.add_exchange('alpha', 'private alpha', 'answer alpha')
    store.add_exchange('beta', 'private beta', 'answer beta')
    context = contextualize(store, 'alpha', 'What next?')
    assert 'private alpha' in context.prompt
    assert 'private beta' not in context.prompt
    store.delete_conversation('alpha')
    after = contextualize(store, 'alpha', 'What next?')
    assert after.message_count == 0
    assert 'private alpha' not in after.prompt


def test_invalid_conversation_id_and_empty_question(tmp_path):
    store = ConversationMemory(tmp_path / 'db.sqlite3')
    with pytest.raises(ValueError):
        contextualize(store, '../traversal', 'hello')
    with pytest.raises(ValueError):
        contextualize(store, 'valid', '  ')


@pytest.fixture
def api(tmp_path):
    calls = []

    class Routed:
        async def run(self, question):
            calls.append(('auto', question))
            return SimpleNamespace(final_answer='Answer.', decision=SimpleNamespace(route='plan_only'), verified=False, research=None)

    class Rag:
        async def run(self, question, *, allow_cloud, save_history):
            calls.append(('documents', question, allow_cloud, save_history))
            source = SimpleNamespace(id='src_1', title='notes.md', url='local://document/1')
            return SimpleNamespace(answer='Document answer. [src_1]', verified=True,
                                   research=SimpleNamespace(sources=[source]))

    db = tmp_path / 'db.sqlite3'
    memory = ConversationMemory(db)
    app = create_app(db_path=db, memory=memory, routed_factory=Routed, rag_factory=Rag)
    with TestClient(app) as client:
        yield client, memory, calls


def post(client, **changes):
    body = {'conversation_id':'alpha','message':'What are its limitations?', 'mode':'auto',
            'allow_cloud':True, 'save_history':False, 'use_context':False}
    body.update(changes)
    return client.post('/api/chat',json=body)


def test_context_is_off_by_default_and_fails_closed_without_cloud(api):
    client, memory, calls = api
    memory.add_exchange('alpha','Explain RAG.','RAG is retrieval augmented generation.')
    response=post(client)
    assert response.status_code == 200
    assert calls[-1][1] == 'What are its limitations?'
    assert response.json()['context_used'] is False
    denied = post(client, allow_cloud=False, use_context=True)
    assert denied.status_code == 403
    assert len(calls) == 1


def test_explicit_context_auto_includes_previous_messages_not_current(api):
    client, memory, calls = api
    memory.add_exchange('alpha','Explain RAG.','RAG retrieves relevant passages.')
    response=post(client, use_context=True, save_history=True)
    assert response.status_code == 200
    assert response.json()['context_used'] is True
    assert response.json()['context_message_count'] == 2
    assert 'Explain RAG.' in calls[-1][1]
    assert calls[-1][1].endswith('What are its limitations?')
    assert [m.content for m in memory.history('alpha')][-2:] == ['What are its limitations?', 'Answer.']


def test_context_document_route_is_opt_in_and_keeps_local_citations(api):
    client, memory, calls = api
    memory.add_exchange('alpha', 'Discuss the four agents', 'The planner chooses workflows')
    result=post(client, use_context=True, mode='documents')
    assert result.status_code == 200
    assert result.json()['context_used'] is True
    assert result.json()['sources'][0]['id'] == 'src_1'
    assert 'four agents' in calls[-1][1]
    assert calls[-1][2:] == (True, False)


def test_other_conversation_never_leaks_even_if_requested(api):
    client, memory, calls = api
    memory.add_exchange('other', 'another conversation private text', 'another private answer')
    result=post(client, use_context=True)
    assert result.status_code == 200
    assert result.json()['context_used'] is False
    assert calls[-1][1] == 'What are its limitations?'


def test_local_search_rejects_context_even_with_cloud_permission(api):
    client, memory, calls = api
    memory.add_exchange('alpha','confidential previous message','confidential answer')
    assert post(client, mode='search', use_context=True).status_code == 422
    assert calls == []
    result=post(client, mode='search', allow_cloud=False)
    assert result.status_code == 200
    assert result.json()['context_used'] is False


def test_saved_conversation_does_not_implicitly_enable_context(api):
    client, memory, calls = api
    memory.add_exchange('alpha', 'Old private question', 'Old private answer')
    result=post(client, save_history=True, use_context=False)
    assert result.status_code == 200
    assert calls[-1][1] == 'What are its limitations?'
    assert result.json()['context_message_count'] == 0
