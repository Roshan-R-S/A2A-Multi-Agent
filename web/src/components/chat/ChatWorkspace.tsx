import { ArrowRight, FileSearch, Layers3, PenLine, Plus, RefreshCw } from 'lucide-react'
import type { Message, Mode } from '../../api'
import { ChatMessage } from './ChatMessage'
import { MessageComposer } from './MessageComposer'
import { useEffect, useRef } from 'react'

const prompts: { icon: typeof Layers3; title: string; prompt: string; mode: Mode }[] = [
  { icon: Layers3, title: 'RESEARCH', prompt: 'Explain the difference between RAG and fine-tuning.', mode: 'auto' },
  { icon: FileSearch, title: 'KNOWLEDGE', prompt: 'How do A2A agents communicate?', mode: 'documents' },
  { icon: PenLine, title: 'PLANNING', prompt: 'Plan how to build an intelligent AI assistant.', mode: 'auto' },
]

export function ChatWorkspace({ messages, loading, error, clearError, draft, setDraft, send, mode, setMode, cloud, setCloud, save, setSave, useContext, setUseContext, newChat }: {
  messages: Message[]; loading: boolean; error: string; clearError: () => void
  draft: string; setDraft: (next: string) => void; send: () => void
  mode: Mode; setMode: (next: Mode) => void; cloud: boolean; setCloud: (next: boolean) => void
  save: boolean; setSave: (next: boolean) => void
  useContext: boolean; setUseContext: (next: boolean) => void; newChat: () => void
}) {
  const end = useRef<HTMLDivElement>(null)
  useEffect(() => { end.current?.scrollIntoView({ behavior: 'auto', block: 'end' }) }, [messages, loading])

  return <section className="chat-workspace" aria-label="Assistant chat">
    <div className="chat-toolbar">
      <span className="eyebrow">INTELLIGENT ASSISTANT</span>
      <button className="text-button compact-new" disabled={loading} onClick={newChat}><Plus size={15}/> NEW CHAT</button>
    </div>
    <div className="chat-scroll">
      {messages.length === 0 ? <div className="welcome">
        <div className="welcome-head"><p className="eyebrow">A2A / MULTI-AGENT SYSTEM</p><h1>Think.<br/><span>Build.</span></h1><p className="welcome-description">Four specialized agents. One considered workspace for research, local knowledge, and planning.</p></div>
        <div className="welcome-prompts"><p className="eyebrow">START / SELECT A DIRECTION</p>
          {prompts.map(({ icon: Icon, title, prompt, mode: promptMode }) => <button key={title} className="prompt-row"
            onClick={() => { setMode(promptMode); setDraft(prompt) }}><Icon size={19}/><span><strong>{title}</strong><small>{prompt}</small></span><ArrowRight size={18}/></button>)}
        </div>
      </div> : <div className="chat-log" role="log" aria-live="off" aria-label="Conversation messages">
        {messages.map((message,index)=><ChatMessage message={message} key={`${index}-${message.role}`}/>)}
        {loading && <div className="workflow-running" role="status" aria-live="polite"><span className="step-loader" aria-hidden="true"><i/><i/><i/><i/><i/><i/><i/><i/></span> [WORKING] WAITING FOR AGENT RESPONSE…</div>}
        <div ref={end}/>
      </div>}
    </div>
    {error && <div className="inline-error" role="alert"><span>[ERROR] {error}</span><button type="button" onClick={clearError} aria-label="Dismiss error"><RefreshCw size={15}/><span>DISMISS</span></button></div>}
    <MessageComposer draft={draft} onDraft={setDraft} onSubmit={send} mode={mode} onMode={setMode}
      cloud={cloud} onCloud={setCloud} save={save} onSave={setSave}
      useContext={useContext} onContext={setUseContext} busy={loading}/>
  </section>
}
