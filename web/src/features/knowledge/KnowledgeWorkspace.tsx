import { useRef, useState, type FormEvent } from 'react'
import { ArrowRight, BookOpenText, Database, FilePlus2, FileText, Search, Trash2, X } from 'lucide-react'
import type { Document, DocumentSummary } from '../../api'
import { MarkdownContent } from '../../components/chat/MarkdownContent'
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
  const [allowSummaryCloud, setAllowSummaryCloud] = useState(false)
  const [summarizingId, setSummarizingId] = useState<number | null>(null)
  const [summary, setSummary] = useState<DocumentSummary | null>(null)

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

  async function summarize(doc: Document) {
    if (summarizingId !== null) return
    if (!allowSummaryCloud) {
      setError('Enable the cloud permission below before summarizing. This sends indexed document content to Groq.')
      return
    }
    setError(''); setNotice(''); setSummary(null); setSummarizingId(doc.id)
    try {
      const result = await service.summarizeDocument(doc.id, true)
      setSummary(result)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Document summarization failed.')
    } finally { setSummarizingId(null) }
  }

  async function remove(doc: Document) {
    if (!window.confirm(`Delete indexed document “${doc.title}”?`)) return
    setError(''); setNotice('')
    try { await service.removeDocument(doc.id); await refresh(); setResults(null); if (summary?.document_id === doc.id) setSummary(null); setNotice(`Removed ${doc.title}.`) }
    catch (e) { setError(e instanceof Error ? e.message : 'Unable to delete document.') }
  }

  return <section className="content-screen knowledge-workspace" aria-label="Knowledge base">
    <div className="section-intro"><p className="eyebrow">YOUR KNOWLEDGE</p><h1>Knowledge base<span className="count-suffix"> · {documents.length} files</span></h1>
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
      {documents.length ? documents.map(doc => <div className="document-row" key={doc.id}>
        <FileText size={18} aria-hidden="true"/>
        <div className="document-info"><strong>{doc.title}</strong><span>DOCUMENT {doc.id} / {doc.chunks} CHUNKS</span></div>
        <button className="action-button summary-action" type="button" disabled={summarizingId !== null}
          aria-label={`Summarize ${doc.title}`} onClick={()=>void summarize(doc)}>
          <BookOpenText size={15}/>{summarizingId === doc.id ? 'SUMMARIZING…' : 'SUMMARIZE'}
        </button>
        <button className="icon-button" onClick={()=>void remove(doc)} disabled={summarizingId !== null} title="Delete document" aria-label={`Remove ${doc.title}`}><Trash2 size={17}/></button>
      </div>) : <div className="empty-section"><Database size={25} aria-hidden="true"/><p>NO DOCUMENTS INDEXED</p><span>Add a Markdown or text file to create your local index.</span></div>}
    </div>
    <div className="summary-privacy-control">
      <label><input type="checkbox" checked={allowSummaryCloud} disabled={summarizingId !== null}
        onChange={e=>setAllowSummaryCloud(e.target.checked)}/>
        <span>ALLOW EXTERNAL AI FOR DOCUMENT SUMMARIES</span></label>
      <p>Summarizing sends all indexed content from the selected document to Groq.
        Limit: 48,000 indexed characters / 80 chunks. Local search stays offline.</p>
    </div>
    {summary && <section className="document-summary-panel" aria-label="Document summary" aria-live="polite">
      <div className="summary-panel-head"><span className="eyebrow">FULL-DOCUMENT SUMMARY / {summary.title}</span>
        <button className="icon-button" aria-label="Close summary" onClick={()=>setSummary(null)}><X size={18}/></button></div>
      <p className="minor-text">{summary.covered_chunks} CHUNKS READ / {summary.segments} SEGMENTS PROCESSED
        {summary.verified ? ' / VERIFIED AGAINST SUMMARY NOTES' : ' / NOT AGENT VERIFIED'}</p>
      {!summary.verified && <p className="inline-error" role="status">Agent verification did not pass. Showing attributed segment notes instead of a verified summary. Check the original document before relying on these notes.</p>}
      <MarkdownContent text={summary.answer}/>
      <div className="summary-source-list"><span className="eyebrow">INDEXED DOCUMENT PARTS</span>
        {summary.sources.map(item=><span key={item.id}>[{item.id}] {item.title}</span>)}
      </div>
      <p className="knowledge-privacy">Source-grounded AI summary, not a lossless reproduction or external fact-check.</p>
    </section>}
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
