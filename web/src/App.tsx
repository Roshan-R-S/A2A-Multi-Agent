import { useCallback, useEffect, useRef, useState } from 'react'
import { service, type Conversation, type Document, type Message, type Mode } from './api'
import { useTheme } from './hooks/useTheme'
import { Sidebar } from './components/layout/Sidebar'
import { WorkspaceHeader, type Page } from './components/layout/WorkspaceHeader'
import { MobileNavigation } from './components/layout/MobileNavigation'
import { ChatWorkspace } from './components/chat/ChatWorkspace'
import { KnowledgeWorkspace } from './features/knowledge/KnowledgeWorkspace'
import { AgentStation } from './features/agents/AgentStation'
import { HistoryWorkspace } from './features/conversations/HistoryWorkspace'

function makeConversationId() {
  return `chat_${crypto.randomUUID().replaceAll('-', '').slice(0, 25)}`
}
function initialConversationId() {
  try { return localStorage.getItem('a2a-session-id') || makeConversationId() }
  catch { return makeConversationId() }
}

export default function App() {
  const { preference, setPreference } = useTheme()
  const [page, setPage] = useState<Page>('chat')
  const [conversationId, setConversationId] = useState(initialConversationId)
  const [messages, setMessages] = useState<Message[]>([])
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [documents, setDocuments] = useState<Document[]>([])
  const [online, setOnline] = useState(false)
  const [mode, setMode] = useState<Mode>('auto')
  const [cloud, setCloud] = useState(false)
  const [save, setSave] = useState(false)
  const [draft, setDraft] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const currentId = useRef(conversationId)
  currentId.current = conversationId

  const refresh = useCallback(async () => {
    const [hist, docs, health] = await Promise.allSettled([service.conversations(), service.documents(), service.health()])
    if (hist.status === 'fulfilled') setConversations(hist.value)
    if (docs.status === 'fulfilled') setDocuments(docs.value)
    setOnline(health.status === 'fulfilled')
  }, [])

  useEffect(() => {
    try { localStorage.setItem('a2a-session-id', conversationId) } catch { /* storage not available */ }
    let cancelled = false
    setMessages([])
    service.history(conversationId).then(items => { if (!cancelled) setMessages(items) }).catch(() => { if (!cancelled) setMessages([]) })
    return () => { cancelled = true }
  }, [conversationId])
  useEffect(() => { void refresh() }, [refresh])

  function newChat() {
    if (loading) return
    setConversationId(makeConversationId()); setMessages([]); setDraft(''); setError(''); setPage('chat')
  }
  function switchChat(next: string) {
    if (loading) return
    setConversationId(next); setError(''); setPage('chat')
  }

  async function forget(conversation: Conversation) {
    if (loading || !window.confirm(`Delete saved conversation “${conversation.id}”?`)) return
    setError('')
    try {
      await service.forget(conversation.id)
      await refresh()
      if (conversationId === conversation.id) newChat()
    } catch (e) { setError(e instanceof Error ? e.message : 'Unable to delete conversation.'); setPage('chat') }
  }

  async function send() {
    const content = draft.trim()
    if (!content || loading) return
    if (mode !== 'search' && !cloud) {
      setError('Turn on ALLOW EXTERNAL AI for this mode, or switch to LOCAL SEARCH.')
      return
    }
    if (content.length > 1500) { setError('Message must be 1500 characters or less.'); return }
    setError('')
    setLoading(true)
    setDraft('')
    const idAtRequest = conversationId
    setMessages(previous => [...previous, { role: 'user', content }])
    try {
      const response = await service.chat({ message: content, conversation_id: idAtRequest, mode, allow_cloud: cloud, save_history: save })
      if (currentId.current === idAtRequest) {
        setMessages(previous => [...previous, { role: 'assistant', content: response.answer,
          route: response.route, verified: response.verified, sources: response.sources }])
      }
      if (save) await refresh()
    } catch (e) {
      if (currentId.current === idAtRequest) {
        setMessages(previous => previous.slice(0, -1))
        setDraft(content)
        setError(e instanceof Error ? e.message : 'Request failed. Please retry.')
      }
    } finally { setLoading(false) }
  }

  return <div className="app-shell">
    <a href="#workspace-main" className="skip-link">Skip to main content</a>
    <Sidebar page={page} changePage={setPage} conversations={conversations} currentId={conversationId}
      newChat={newChat} switchChat={switchChat} deleteChat={item => void forget(item)} disabled={loading} online={online}/>
    <div className="main-column">
      <WorkspaceHeader page={page} online={online} preference={preference} onThemeChange={setPreference}/>
      <main id="workspace-main" className="workspace-main" tabIndex={-1}>
        {page === 'chat' && <ChatWorkspace messages={messages} loading={loading} error={error} clearError={() => setError('')}
          draft={draft} setDraft={setDraft} send={() => void send()} mode={mode} setMode={setMode}
          cloud={cloud} setCloud={setCloud} save={save} setSave={setSave} newChat={newChat}/>}
        {page === 'knowledge' && <KnowledgeWorkspace documents={documents} refresh={refresh} onAsk={() => {setMode('documents');setPage('chat')}}/>}
        {page === 'agents' && <AgentStation online={online}/>}
        {page === 'history' && <HistoryWorkspace conversations={conversations} open={switchChat} remove={item => void forget(item)} busy={loading}/>}
      </main>
      <MobileNavigation page={page} onChange={setPage}/>
    </div>
  </div>
}
