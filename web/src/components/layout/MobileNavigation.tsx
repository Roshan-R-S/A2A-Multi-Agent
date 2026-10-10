import { BookOpen, Cpu, History, MessageSquare } from 'lucide-react'
import type { Page } from './WorkspaceHeader'

export function MobileNavigation({ page, onChange }: { page: Page; onChange: (next: Page) => void }) {
  return <nav className="mobile-nav" aria-label="Mobile primary navigation">
    <button aria-current={page === 'chat' ? 'page' : undefined} onClick={() => onChange('chat')}><MessageSquare size={18}/>CHAT</button>
    <button aria-current={page === 'knowledge' ? 'page' : undefined} onClick={() => onChange('knowledge')}><BookOpen size={18}/>FILES</button>
    <button aria-current={page === 'agents' ? 'page' : undefined} onClick={() => onChange('agents')}><Cpu size={18}/>AGENTS</button>
    <button aria-current={page === 'history' ? 'page' : undefined} onClick={() => onChange('history')}><History size={18}/>HISTORY</button>
  </nav>
}
