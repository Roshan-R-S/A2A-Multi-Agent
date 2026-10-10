import { ArrowRight, History, MessageSquare, Pencil, Trash2 } from 'lucide-react'
import type { Conversation } from '../../api'

export function HistoryWorkspace({ conversations, open, remove, rename, busy }: {
  conversations: Conversation[]
  open: (id: string) => void
  remove: (item: Conversation) => void
  rename: (item: Conversation) => void
  busy: boolean
}) {
  return <section className="content-screen" aria-label="Saved conversations">
    <div className="section-intro"><p className="eyebrow">SAVED CONVERSATIONS</p><h1>History<span className="count-suffix"> · {conversations.length} chats</span></h1>
      <p>These conversations were saved to your local SQLite database when SAVE HISTORY was enabled.</p>
    </div>
    <div className="document-list history-list">
      {conversations.length === 0 && <div className="empty-section"><History size={25} aria-hidden="true"/><p>NO SAVED SESSIONS</p><span>Enable SAVE HISTORY in chat to keep your conversations.</span></div>}
      {conversations.map(item=><div className="document-row" key={item.id}>
        <MessageSquare size={18} aria-hidden="true"/>
        <div className="document-info"><strong>{item.title}</strong>
          <span>{item.messages} MESSAGES {item.updated_at ? ` / ${item.updated_at.slice(0,16).replace('T',' ')}` : ''}</span></div>
        <button className="icon-button" onClick={() => open(item.id)} aria-label={`Open conversation ${item.title}`} disabled={busy}><ArrowRight size={18}/></button>
        <button className="icon-button" onClick={() => rename(item)} aria-label={`Rename conversation ${item.title}`} disabled={busy}><Pencil size={17}/></button>
        <button className="icon-button" onClick={() => remove(item)} aria-label={`Delete conversation ${item.title}`} disabled={busy}><Trash2 size={18}/></button>
      </div>)}
    </div>
  </section>
}
