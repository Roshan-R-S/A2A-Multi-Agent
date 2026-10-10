import { ArrowLeft, Home, ShieldAlert } from 'lucide-react'
import { Brand } from '../../components/ui/Brand'

export function NotFoundPage({ onReturnHome }: { onReturnHome: () => void }) {
  return <main className="not-found-screen" id="workspace-main">
    <div className="not-found-panel">
      <Brand />
      <p className="eyebrow not-found-label"><ShieldAlert size={15} aria-hidden="true"/> INVALID WORKSPACE ROUTE</p>
      <p className="not-found-code" aria-hidden="true">404</p>
      <h1>Page not found.</h1>
      <p>This address does not match a workspace page. No conversation or document has been opened.</p>
      <p className="not-found-note" role="status">Returning to your workspace in 5 seconds.</p>
      <button className="not-found-home" onClick={onReturnHome} type="button"><Home size={17} aria-hidden="true"/> RETURN HOME <ArrowLeft size={16} aria-hidden="true"/></button>
    </div>
  </main>
}
