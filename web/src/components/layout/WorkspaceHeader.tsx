import { CircleHelp, Moon, Sun, Monitor } from 'lucide-react'
import type { ThemePreference } from '../../hooks/useTheme'

export type Page = 'chat' | 'knowledge' | 'agents' | 'history'
const titles: Record<Page, string> = { chat: 'CONVERSATION', knowledge: 'KNOWLEDGE BASE', agents: 'CONTROL STATION', history: 'SAVED SESSIONS' }

export function WorkspaceHeader({ page, online, preference, onThemeChange }: {
  page: Page
  online: boolean
  preference: ThemePreference
  onThemeChange: (next: ThemePreference) => void
}) {
  return <header className="workspace-header">
    <div className="header-location"><span className="eyebrow">WORKSPACE /</span> <span>{titles[page]}</span></div>
    <div className="header-controls">
      <div className="connection" role="status" aria-label={online ? 'Local web API connected' : 'Local web API disconnected'}>
        <span className={`signal ${online ? 'positive' : 'negative'}`} />
        <span className="connection-label">API {online ? 'CONNECTED' : 'OFFLINE'}</span>
      </div>
      <label className="theme-control">
        <span className="sr-only">Appearance</span>
        {preference === 'dark' ? <Moon size={15} aria-hidden="true"/> : preference === 'light' ? <Sun size={15} aria-hidden="true"/> : <Monitor size={15} aria-hidden="true"/>}
        <select aria-label="Appearance" value={preference} onChange={event => onThemeChange(event.target.value as ThemePreference)}>
          <option value="system">SYSTEM</option><option value="dark">DARK</option><option value="light">LIGHT</option>
        </select>
      </label>
      <span className="header-help" title="API status is not a check of individual agent availability"><CircleHelp size={16} aria-hidden="true"/></span>
    </div>
  </header>
}
