import { ArrowDown, CheckCheck, FileSearch, Network, PenLine, Route } from 'lucide-react'

const agents = [
  { index:'01', name:'PLANNER', skill:'plan_or_route', port:'8004', icon:Route, text:'Decides between research and a proposed plan. Does not execute UI actions or tools.' },
  { index:'02', name:'RESEARCH', skill:'research_topic', port:'8001', icon:FileSearch, text:'Collects external evidence and structured research for the Writer.' },
  { index:'03', name:'WRITER', skill:'write_explanation', port:'8002', icon:PenLine, text:'Turns research or local document passages into a cited response.' },
  { index:'04', name:'VERIFIER', skill:'verify_answer', port:'8003', icon:CheckCheck, text:'Checks citations and evidence consistency; failures may trigger revisions.' },
]

export function AgentStation({ online }: { online: boolean }) {
  return <section className="content-screen agents-workspace" aria-label="Agent control station">
    <div className="section-intro"><p className="eyebrow">03 / SYSTEM ARCHITECTURE</p><h1>Control station<span className="count-suffix"> / 04</span></h1>
      <p>Understand the agents behind your assistant. This is a capability map, not a live execution monitor.</p>
    </div>
    <div className="station-overview"><div><p className="eyebrow">REGISTERED ROLES</p><div className="station-metric">04<span> / AGENTS</span></div></div>
      <div className="station-endpoint"><p className="eyebrow">WEB API CONNECTION</p><p className={online?'connected':'disconnected'}>{online?'CONNECTED':'UNAVAILABLE'}</p><span>Individual agent status is not measured by this endpoint.</span></div>
    </div>
    <p className="eyebrow station-label">AGENT DIRECTORY / DECLARED CAPABILITIES</p>
    <div className="agent-list">{agents.map(({index,name,skill,port,icon:Icon,text})=><article className="agent-row" key={name}>
      <span className="agent-index">{index}</span><div className="agent-icon"><Icon size={21} aria-hidden="true"/></div><div className="agent-description">
        <h2>{name}</h2><p>{text}</p><span className="agent-meta">SKILL: {skill} · PORT: {port}</span>
      </div><span className="agent-unknown">STATUS / UNCHECKED</span>
    </article>)}</div>
    <div className="flow-section"><p className="eyebrow">REQUEST FLOW / SUPPORTED PATHS</p>
      <div className="flow-steps"><span><Network size={17}/> PLANNER</span><ArrowDown size={17}/><span>RESEARCH → WRITER → VERIFIER</span></div>
      <p>Planning-only requests return a proposed plan without execution. Documents mode uses local retrieval → Writer → Verifier. Local Search uses SQLite without an LLM.</p>
    </div>
  </section>
}
