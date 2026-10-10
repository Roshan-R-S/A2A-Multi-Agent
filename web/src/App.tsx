import { useCallback, useEffect, useRef, useState } from 'react'
import { ArrowUp, BookOpen, Bot, ChevronRight, Cloud, Database, FilePlus2, FileText, Globe2, History, Menu, MessageCircle, Plus, Search, ShieldCheck, Sparkles, Trash2, X } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { service, type Conversation, type Document, type Message, type Mode } from './api'

const MODE_OPTIONS: { key: Mode; label: string; description: string }[] = [
  { key: 'auto', label: 'Auto', description: 'Planner chooses research or a proposed plan. Uses Groq and may search the web.' },
  { key: 'documents', label: 'Documents', description: 'Retrieve local passages, then use Groq Writer + Verifier. Excerpts leave your computer.' },
  { key: 'search', label: 'Local search', description: 'Search indexed files using SQLite. No network or model calls.' },
]
const uuid = () => `chat_${crypto.randomUUID().replaceAll('-', '').slice(0, 25)}`
const intro = [
  { icon: Globe2, title: 'Research a topic', prompt: 'Explain what makes multi-agent systems useful.' },
  { icon: BookOpen, title: 'Explore your files', prompt: 'What is the architecture of this project?' },
  { icon: Sparkles, title: 'Plan something', prompt: 'Plan a reliable local RAG assistant.' },
]
function markdown(text: string) {
  return <ReactMarkdown remarkPlugins={[remarkGfm]} components={{
    img: () => <span>[External image omitted]</span>,
    a: ({ href, children }) => href && /^https?:\/\//i.test(href)
      ? <a href={href} target="_blank" rel="noopener noreferrer">{children}</a>
      : <span>{children}</span>,
  }}>{text}</ReactMarkdown>
}

export default function App() {
  const [id, setId] = useState(() => localStorage.getItem('a2a-session-id') || uuid())
  const [messages, setMessages] = useState<Message[]>([])
  const [history, setHistory] = useState<Conversation[]>([])
  const [documents, setDocuments] = useState<Document[]>([])
  const [mode, setMode] = useState<Mode>('auto')
  const [cloud, setCloud] = useState(false)
  const [save, setSave] = useState(false)
  const [draft, setDraft] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [online, setOnline] = useState(false)
  const [showSidebar, setShowSidebar] = useState(false)
  const [showKnowledge, setShowKnowledge] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)
  const bottomRef = useRef<HTMLDivElement>(null)

  const refresh = useCallback(async () => {
    const results = await Promise.allSettled([service.conversations(), service.documents(), service.health()])
    if (results[0].status === 'fulfilled') setHistory(results[0].value)
    if (results[1].status === 'fulfilled') setDocuments(results[1].value)
    setOnline(results[2].status === 'fulfilled')
  }, [])

  useEffect(() => { localStorage.setItem('a2a-session-id', id) }, [id])
  useEffect(() => {
    let mounted = true
    service.history(id).then(items => { if (mounted) setMessages(items) }).catch(() => { if (mounted) setMessages([]) })
    return () => { mounted = false }
  }, [id])
  useEffect(() => { void refresh() }, [refresh])
  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages, loading])

  const newChat = () => { setId(uuid()); setMessages([]); setError(''); setShowSidebar(false) }
  const switchChat = (next: string) => { setId(next); setError(''); setShowSidebar(false) }

  async function send(text?: string) {
    const content = (text ?? draft).trim()
    if (!content || loading) return
    setError('')
    setDraft('')
    if (mode !== 'search' && !cloud) {
      setError('Enable cloud access for Auto/Documents mode, or switch to Local search.')
      setDraft(content)
      return
    }
    setMessages(current => [...current, { role: 'user', content }])
    setLoading(true)
    try {
      const reply = await service.chat({
        message: content, conversation_id: id, mode, allow_cloud: cloud, save_history: save,
      })
      setMessages(current => [...current, {
        role: 'assistant', content: reply.answer, route: reply.route,
        verified: reply.verified, sources: reply.sources,
      }])
      if (save) await refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Request failed.')
    } finally { setLoading(false) }
  }

  async function upload(file?: File) {
    if (!file) return
    setError('')
    if (!/\.(txt|md|markdown)$/i.test(file.name)) {
      setError('Only .txt, .md, and .markdown files can be indexed.'); return
    }
    if (file.size > 2 * 1024 * 1024) {
      setError('Choose a file under 2 MiB.'); return
    }
    try {
      await service.upload(file.name, await file.text())
      await refresh()
      setShowKnowledge(true)
    } catch (err) { setError(err instanceof Error ? err.message : 'Upload failed.') }
    finally { if (fileRef.current) fileRef.current.value = '' }
  }

  async function deleteDocument(document: Document) {
    if (!confirm(`Remove “${document.title}” from the knowledge index?`)) return
    try { await service.removeDocument(document.id); await refresh() }
    catch (err) { setError(err instanceof Error ? err.message : 'Delete failed.') }
  }

  async function forget(conversation: Conversation) {
    if (!confirm(`Delete saved conversation “${conversation.id}”?`)) return
    try { await service.forget(conversation.id); await refresh(); if (id === conversation.id) newChat() }
    catch (err) { setError(err instanceof Error ? err.message : 'Delete failed.') }
  }

  const active = MODE_OPTIONS.find(item => item.key === mode)!
  return <div className="shell">
    {showSidebar && <div className="scrim" onClick={() => setShowSidebar(false)} />}
    <aside className={`sidebar ${showSidebar ? 'show' : ''}`}>
      <div className="brand">
        <div className="brand-mark"><Sparkles size={21} strokeWidth={2.3} /></div>
        <div><strong>A2A <span>ASSISTANT</span></strong><small>MULTI-AGENT WORKSPACE</small></div>
        <button className="mobile-close icon-button" onClick={() => setShowSidebar(false)} aria-label="Close menu"><X size={18}/></button>
      </div>
      <button className="new-chat" onClick={newChat}><Plus size={18}/> New conversation <ChevronRight size={15}/></button>
      <div className="section-header">WORKSPACE</div>
      <button className={`nav-item ${!showKnowledge ? 'active' : ''}`} onClick={() => { setShowKnowledge(false); setShowSidebar(false) }}><MessageCircle size={17}/> Chat</button>
      <button className={`nav-item ${showKnowledge ? 'active' : ''}`} onClick={() => { setShowKnowledge(true); setShowSidebar(false) }}><Database size={17}/> Knowledge base <span className="count">{documents.length}</span></button>
      <div className="section-header history-header"><span>RECENT CONVERSATIONS</span><History size={15}/></div>
      <div className="conversation-list">
        {history.length === 0 && <p className="empty-history">Save a conversation to see it here.</p>}
        {history.map(c => <div key={c.id} className={`history-row ${c.id === id ? 'selected' : ''}`}>
          <button onClick={() => switchChat(c.id)} title={c.id}><MessageCircle size={14}/><span>{c.id.replace('chat_', 'Conversation ').slice(0, 25)}</span></button>
          <button title="Delete saved conversation" className="history-delete" onClick={() => void forget(c)}><Trash2 size={14}/></button>
        </div>)}
      </div>
      <div className="sidebar-footer">
        <div className="local-indicator"><span className={`status-dot ${online ? 'on' : ''}`}/>{online ? 'Local API connected' : 'Local API unavailable'}</div>
        <p><ShieldCheck size={14}/> Single-user development interface</p>
      </div>
    </aside>

    <main className="main">
      <header className="topbar">
        <div className="top-left"><button onClick={() => setShowSidebar(true)} className="icon-button mobile-menu" aria-label="Open menu"><Menu size={21}/></button><span className="crumb">Workspace</span><ChevronRight size={14} className="chevron"/><strong>{showKnowledge ? 'Knowledge base' : 'Assistant'}</strong></div>
        <div className="top-right"><span className="app-pill"><span className={`status-dot ${online ? 'on' : ''}`}/>{online ? 'Connected' : 'Disconnected'}</span><span className="app-pill muted"><Bot size={15}/> 4 Agents</span></div>
      </header>

      {showKnowledge ? <section className="knowledge-content">
        <div className="knowledge-head"><div><div className="eyebrow">LOCAL KNOWLEDGE</div><h1>Your documents</h1><p>Index documents locally. Searching is offline; sending excerpts to Groq requires your consent.</p></div>
          <button className="primary-button" onClick={() => fileRef.current?.click()}><FilePlus2 size={18}/> Add document</button>
        </div>
        <div className="privacy-note"><ShieldCheck size={18}/><span>Supported: TXT, Markdown · Up to 2 MiB per file · Stored in local SQLite and managed uploads</span></div>
        <div className="doc-list">{documents.length ? documents.map(doc => <div className="document-item" key={doc.id}><div className="document-icon"><FileText size={20}/></div><div className="document-meta"><strong>{doc.title}</strong><small>{doc.chunks} indexed passages · Document #{doc.id}</small></div><button aria-label={`Remove ${doc.title}`} onClick={() => void deleteDocument(doc)} className="icon-button delete"><Trash2 size={17}/></button></div>) : <div className="empty-docs"><Database size={28}/><h3>No documents indexed yet</h3><p>Upload a text or Markdown document to begin local retrieval.</p></div>}</div>
        <button className="back-chat" onClick={() => { setShowKnowledge(false); setMode('documents') }}>Ask a question about documents <ChevronRight size={16}/></button>
      </section> : <>
        <div className="conversation-scroll">
          {messages.length === 0 ? <div className="welcome"><div className="welcome-orb"><Sparkles size={33}/></div><div className="eyebrow">YOUR MULTI-AGENT SYSTEM</div><h1>What can I help you <em>build?</em></h1><p>One workspace. Four cooperating agents. Grounded answers, local knowledge, and intelligent planning.</p>
          <div className="suggestions">{intro.map(item => <button key={item.title} className="suggestion" onClick={() => { if (item.title === 'Explore your files') setMode('documents'); else setMode('auto'); setDraft(item.prompt) }}><item.icon size={20}/><strong>{item.title}</strong><span>{item.prompt}</span><ChevronRight className="suggest-chevron" size={16}/></button>)}</div></div> : <div className="message-list">
            {messages.map((message, index) => <article key={`${index}-${message.role}`} className={`message ${message.role}`}>
              <div className={`avatar ${message.role}`} >{message.role === 'assistant' ? <Sparkles size={17}/> : 'U'}</div>
              <div className="message-content"><div className="message-author">{message.role === 'assistant' ? 'A2A Assistant' : 'You'} {message.role === 'assistant' && message.route && <span className="route-tag">{message.route}{message.verified ? ' · verified' : ''}</span>}</div><div className="message-body">{message.role === 'assistant' ? markdown(message.content) : <p>{message.content}</p>}</div>
                {message.sources && message.sources.length > 0 && <div className="source-strip"><span>Sources</span>{message.sources.map((source, i) => /^https?:\/\//i.test(source.url) ? <a href={source.url} key={`${i}-${source.id}`} target="_blank" rel="noopener noreferrer">[{source.id}] {source.title}</a> : <span className="source-chip" key={`${i}-${source.id}`}>[{source.id}] {source.title}</span>)}</div>}</div>
            </article>)}
            {loading && <div className="message"><div className="avatar assistant"><Sparkles size={17}/></div><div className="thinking"><span/><span/><span/> Agent workflow running…</div></div>}
            <div ref={bottomRef}/>
          </div>}
        </div>
        <div className="composer-wrap">
          {error && <div className="error-banner"><span>{error}</span><button aria-label="Dismiss error" onClick={() => setError('')}><X size={16}/></button></div>}
          <div className="composer">
            <textarea placeholder="Ask your multi-agent assistant…" value={draft} disabled={loading} rows={2} onChange={e => setDraft(e.target.value)} onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); void send() } }}/>
            <div className="composer-toolbar"><div className="mode-switch" title={active.description}>{MODE_OPTIONS.map(item => <button key={item.key} onClick={() => setMode(item.key)} className={mode === item.key ? 'chosen' : ''}>{item.key === 'auto' ? <Sparkles size={14}/> : item.key === 'documents' ? <BookOpen size={14}/> : <Search size={14}/>} {item.label}</button>)}</div><button className="send-button" onClick={() => void send()} aria-label="Send message" disabled={loading || !draft.trim()}><ArrowUp size={18}/></button></div>
          </div>
          <div className="privacy-settings"><label title="Required for Auto or Documents modes"><input type="checkbox" checked={cloud} onChange={e => setCloud(e.target.checked)}/><Cloud size={14}/> Allow external AI/search services</label><label title="Save successful question and answer to local SQLite"><input type="checkbox" checked={save} onChange={e => setSave(e.target.checked)}/><History size={14}/> Save conversation locally</label></div>
          <p className="composer-footnote">{active.description} {mode !== 'search' && !cloud ? 'Cloud permission is off.' : ''}</p>
        </div>
      </>}
      <input type="file" ref={fileRef} className="file-hidden" accept=".txt,.md,.markdown,text/plain,text/markdown" onChange={e => void upload(e.target.files?.[0])}/>
    </main>
  </div>
}
