import { ExternalLink } from 'lucide-react'
import type { Source } from '../../api'

export function CitationList({ sources }: { sources: Source[] }) {
  if (!sources.length) return null
  return <section className="citations" aria-label="Answer sources">
    <p className="eyebrow citation-heading">SOURCES / {String(sources.length).padStart(2,'0')}</p>
    <ul>{sources.map((source, index) => <li key={`${source.id}-${index}`}>
      {/^https?:\/\//i.test(source.url)
        ? <a href={source.url} rel="noopener noreferrer" target="_blank"><span>[{source.id}]</span><span className="citation-title">{source.title}</span><ExternalLink size={14} aria-label="Opens a new tab"/></a>
        : <div className="citation-local"><span>[{source.id}]</span><span className="citation-title">{source.title}</span><span>LOCAL</span></div>}
    </li>)}</ul>
  </section>
}
