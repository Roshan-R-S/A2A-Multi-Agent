import type { Page } from './components/layout/WorkspaceHeader'

const pages: Record<string, Page> = {
  '/': 'chat',
  '/chat': 'chat',
  '/knowledge': 'knowledge',
  '/agents': 'agents',
  '/history': 'history',
}

/** Resolve only known UI paths; never interpret arbitrary paths as IDs. */
export function pageFromPath(pathname: string): Page | null {
  const normalized = pathname === '/' ? '/' : pathname.replace(/\/+$/, '')
  return Object.prototype.hasOwnProperty.call(pages, normalized) ? pages[normalized] : null
}

/** Use fixed URLs instead of constructing paths from untrusted user text. */
export function pathForPage(page: Page): string {
  switch (page) {
    case 'chat': return '/'
    case 'knowledge': return '/knowledge'
    case 'agents': return '/agents'
    case 'history': return '/history'
  }
}
