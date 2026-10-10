import { ArrowUp, BookOpen, Cloud, Database, History, Workflow } from 'lucide-react'
import type { KeyboardEvent } from 'react'
import type { Mode } from '../../api'

const OPTIONS: { key: Mode; text: string; icon: typeof Workflow }[] = [
  { key: 'auto', text: 'AUTO', icon: Workflow },
  { key: 'documents', text: 'DOCUMENTS', icon: BookOpen },
  { key: 'search', text: 'LOCAL SEARCH', icon: Database },
]
const descriptions: Record<Mode,string> = {
  auto: 'Planner can use external AI and web research. Cloud permission required.',
  documents: 'Matching local document excerpts are sent to external AI services when permitted.',
  search: 'Keyword search on your SQLite index only. No external AI call.',
}

export function MessageComposer({ draft, onDraft, onSubmit, mode, onMode, cloud, onCloud, save, onSave, busy }: {
  draft: string
  onDraft: (value: string) => void
  onSubmit: () => void
  mode: Mode
  onMode: (mode: Mode) => void
  cloud: boolean
  onCloud: (next: boolean) => void
  save: boolean
  onSave: (next: boolean) => void
  busy: boolean
}) {
  const onKey = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault()
      if (!busy) onSubmit()
    }
  }
  return <div className="composer-area">
    <form className="composer" onSubmit={e => {e.preventDefault(); onSubmit()}}>
      <label className="sr-only" htmlFor="chat-input">Message your assistant</label>
      <textarea id="chat-input" placeholder="Ask a question, plan a task, explore your documents…" maxLength={1500}
        rows={2} disabled={busy} value={draft} onChange={event => onDraft(event.target.value)} onKeyDown={onKey}/>
      <div className="composer-controls">
        <div className="mode-selector" role="group" aria-label="Conversation mode">
          {OPTIONS.map(({ key, text, icon: Icon }) => <button type="button" key={key} aria-pressed={mode === key}
            onClick={() => onMode(key)} disabled={busy}><Icon size={15} aria-hidden="true"/>{text}</button>)}
        </div>
        <button className="submit-button" type="submit" aria-label="Send message" disabled={busy || !draft.trim()}><ArrowUp size={18} aria-hidden="true"/></button>
      </div>
    </form>
    <div className="composer-consent">
      <label><input type="checkbox" checked={cloud} onChange={event => onCloud(event.target.checked)} disabled={busy}/><Cloud size={14} aria-hidden="true"/> ALLOW EXTERNAL AI</label>
      <label><input type="checkbox" checked={save} onChange={event => onSave(event.target.checked)} disabled={busy}/><History size={14} aria-hidden="true"/> SAVE HISTORY</label>
    </div>
    <p className="composer-description">{descriptions[mode]} {mode !== 'search' && !cloud ? ' External AI is currently disabled.' : ''}</p>
  </div>
}
