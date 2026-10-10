import { useRef, useState, type FormEvent } from 'react'
import { ArrowRight, Database, FilePlus2, FileText, Search, Trash2, X } from 'lucide-react'
import type { Document } from '../../api'
import { service } from '../../api'

type SearchResult = { title: string; snippet: string }

export function KnowledgeWorkspace({ documents, refresh, onAsk }: {
  documents: Document[]; refresh: () => Promise<void>; onAsk: () => void
}) {
  const uploadRef = useRef<HTMLInputElement>(null)
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<SearchResult[] | null>(null)
  const [searching, setSearching] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')

  async function upload(file?: File) {
    if (!file) return
    setError(''); setNotice('')
    if (!/\.(txt|md|markdown)$/i.test(file.name)) { setError('Only .txt, .md or .markdown files are supported.'); return }
    if (file.size > 2 * 1024 * 1024) { setError('Maximum document size is 2 MiB.'); return }
    setUploading(true)
    try {
      await service.upload(file.name, await file.text())
      await refresh()
      setNotice(`Indexed ${file.name} successfully.`)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Document upload failed.')
    } finally { setUploading(false); if (uploadRef.current) uploadRef.current.value = '' }
  }

  async function search(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!query.trim() || searching) return
    setError(''); setNotice(''); setSearching(true)
    try { setResults(await service.search(query.trim())) }
    catch (e) { setError(e instanceof Error ? e.message : 'Search failed.') }
    finally { setSearching(false) }
  }

  async function remove(doc: Document) {
    if (!window.confirm(`Delete indexed document “${doc.title}”?`)) return
    setError(''); setNotice('')
    try { await service.removeDocument(doc.id); await refresh(); setResults(null); setNotice(`Removed ${doc.title}.`) }
    catch (e) { setError(e instanceof Error ? e.message : 'Unable to delete document.') }
  }

  return <section className="content-screen knowledge-workspace" aria-label="Knowledge base">
    <div className="section-intro"><p className="eyebrow">02 / YOUR KNOWLEDGE</p><h1>Knowledge base<span className="count-suffix"> / {String(documents.length).padStart(2,'0')}</span></h1>
      <p>Index the files you choose. Local keyword retrieval requires no cloud service.</p>
    </div>
    <div className="knowledge-head">
      <div><span className="eyebrow">INDEX / DOCUMENTS</span><p className="minor-text">TXT, MD, MARKDOWN / MAX 2 MiB</p></div>
      <button className="action-button upload-button" type="button" onClick={()=>uploadRef.current?.click()} disabled={uploading}><FilePlus2 size={17}/>{uploading ? 'INDEXING…' : 'ADD DOCUMENT'}</button>
    </div>
    <input type="file" className="sr-only" tabIndex={-1} ref={uploadRef} accept=".txt,.md,.markdown,text/plain,text/markdown" onChange={e=>void upload(e.target.files?.[0])} aria-label="Choose document" />
    {error && <div className="inline-error" role="alert"><span>[ERROR] {error}</span><button aria-label="Dismiss error" onClick={()=>setError('')}><X size={16}/></button></div>}
    {notice && <p className="inline-notice" role="status">[DONE] {notice}</p>}
    <div className="document-list">
      {documents.length ? documents.map((doc, index) => <div className="document-row" key={doc.id}>
        <span className="document-index">{String(index + 1).padStart(2, '0')}</span><FileText size={18} aria-hidden="true"/>
        <div className="document-info"><strong>{doc.title}</strong><span>DOCUMENT {doc.id} / {doc.chunks} CHUNKS</span></div>
        <button className="icon-button" onClick={()=>void remove(doc)} title="Delete document" aria-label={`Remove ${doc.title}`}><Trash2 size={17}/></button>
      </div>) : <div className="empty-section"><Database size={25} aria-hidden="true"/><p>NO DOCUMENTS INDEXED</p><span>Add a Markdown or text file to create your local index.</span></div>}
    </div>
    <div className="knowledge-search-section"><div className="eyebrow">RETRIEVE / LOCAL ONLY</div>
      <h2>Search your documents.</h2>
      <form className="knowledge-search-form" onSubmit={e=>void search(e)}>
        <label htmlFor="knowledge-query" className="sr-only">Search your documents</label>
        <Search size={18} aria-hidden="true"/>
        <input id="knowledge-query" value={query} maxLength={500} placeholder="e.g. A2A orchestration" onChange={e=>setQuery(e.target.value)}/>
        <button type="submit" className="action-button" disabled={!query.trim() || searching}>{searching ? 'SEARCHING…' : 'SEARCH'}</button>
      </form>
      {results !== null && <div className="search-results" aria-live="polite">
        <p className="eyebrow">RESULTS / {String(results.length).padStart(2,'0')}</p>
        {results.length ? results.map((result, index)=><article className="search-result" key={`${result.title}-${index}`}>
          <p className="result-title"><span>[{String(index + 1).padStart(2,'0')}]</span> {result.title}</p><p>{result.snippet}</p>
        </article>) : <p className="minor-text">No indexed passages matched this query. Try different keywords.</p>}
      </div>}
    </div>
    <button className="text-button knowledge-chat-link" onClick={onAsk}>ASK THE ASSISTANT ABOUT YOUR FILES <ArrowRight size={17}/></button>
    <p className="knowledge-privacy">INDEXED FILES ARE STORED LOCALLY. DOCUMENTS MODE MAY SEND MATCHING EXCERPTS TO GROQ ONLY WITH YOUR EXPLICIT PERMISSION.</p>
  </section>
}
