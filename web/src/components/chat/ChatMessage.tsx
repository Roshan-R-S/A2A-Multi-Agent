import { CheckCircle2, FileText } from 'lucide-react'
import type { Message } from '../../api'
import { CitationList } from './CitationList'
import { MarkdownContent } from './MarkdownContent'

const routeLabel: Record<string, string> = {
  research: 'RESEARCH', plan_only: 'PROPOSED PLAN', documents: 'DOCUMENTS', search: 'LOCAL SEARCH',
}

export function ChatMessage({ message, index }: { message: Message; index: number }) {
  const assistant = message.role === 'assistant'
  return <article className={`chat-message ${assistant ? 'assistant' : 'user'}`}>
    <div className="message-meta">
      <span>{assistant ? 'A2A / ASSISTANT' : 'YOU / REQUEST'}</span>
      <span>{String(index+1).padStart(2,'0')}</span>
    </div>
    <div className="message-body">
      {assistant ? <MarkdownContent text={message.content}/> : <p>{message.content}</p>}
    </div>
    {assistant && <div className="message-flags">
      <span><FileText size={13} aria-hidden="true"/> {routeLabel[message.route ?? ''] ?? (message.route?.toUpperCase() || 'ANSWER')}</span>
      {message.verified && <span className="verified-label"><CheckCircle2 size={13} aria-hidden="true"/> VERIFIED BY AGENT</span>}
    </div>}
    {assistant && <CitationList sources={message.sources ?? []}/>}
  </article>
}
