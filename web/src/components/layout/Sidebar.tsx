import { BookOpen, Cpu, History, MessageSquare, Plus, Trash2 } from 'lucide-react'
import type { Conversation } from '../../api'
import type { Page } from './WorkspaceHeader'
import { Brand } from '../ui/Brand'

export function Sidebar({ page, changePage, conversations, currentId, newChat, switchChat, deleteChat, disabled, online }: {
  page: Page
  changePage: (page: Page) => void
  conversations: Conversation[]
  currentId: string
  newChat: () => void
  switchChat: (id: string) => void
  deleteChat: (item: Conversation) => void
  disabled: boolean
  online: boolean
}) {
  return <aside className="sidebar" aria-label="Workspace navigation">
    <div className="sidebar-brand"><Brand/><span className="eyebrow">LOCAL ASSISTANT / V0.4</span></div>
    <button className="action-button new-conversation" onClick={newChat} disabled={disabled}><Plus size={17} aria-hidden="true"/> NEW CONVERSATION</button>
    <div className="sidebar-group">
      <p className="eyebrow nav-label">01 / NAVIGATION</p>
      <nav className="primary-nav" aria-label="Primary">
        <button className={page === 'chat' ? 'selected' : ''} onClick={() => changePage('chat')} aria-current={page === 'chat' ? 'page' : undefined}><MessageSquare size={18}/> CHAT</button>
        <button className={page === 'knowledge' ? 'selected' : ''} onClick={() => changePage('knowledge')} aria-current={page === 'knowledge' ? 'page' : undefined}><BookOpen size={18}/> KNOWLEDGE</button>
        <button className={page === 'agents' ? 'selected' : ''} onClick={() => changePage('agents')} aria-current={page === 'agents' ? 'page' : undefined}><Cpu size={18}/> AGENTS</button>
        <button className={page === 'history' ? 'selected' : ''} onClick={() => changePage('history')} aria-current={page === 'history' ? 'page' : undefined}><History size={18}/> HISTORY</button>
      </nav>
    </div>
    <div className="sidebar-group conversations">
      <p className="eyebrow nav-label">02 / SAVED SESSIONS <span className="mono-number">{String(conversations.length).padStart(2,'0')}</span></p>
      <div className="session-list">
        {conversations.length === 0 && <p className="minor-text">No saved conversations yet. Enable SAVE HISTORY in chat.</p>}
        {conversations.map((c, index) => <div className={`session-item ${c.id === currentId ? 'active' : ''}`} key={c.id}>
          <button className="session-select" onClick={() => switchChat(c.id)} disabled={disabled} title={c.id}>
            <span className="session-number">{String(index+1).padStart(2,'0')}</span>
            <span className="session-name">{c.id.replace(/^chat_/, 'Session ').slice(0, 26)}</span>
          </button>
          <button className="icon-button session-remove" onClick={() => deleteChat(c)} aria-label={`Delete conversation ${c.id}`} title="Delete saved conversation" disabled={disabled}><Trash2 size={16}/></button>
        </div>)}
      </div>
    </div>
    <div className="sidebar-foot"><span className={`signal ${online ? 'positive' : 'negative'}`} /><span>LOCAL API {online ? 'CONNECTED' : 'UNAVAILABLE'}</span><span className="mono-number">/ 001</span></div>
  </aside>
}
