# A2A Multi-Agent System

A modular multi-agent AI system built with Python, the Agent2Agent (A2A) protocol, Groq, Tavily, Starlette, HTTPX, and Uvicorn.

The current MVP runs three independent A2A agents:

- Research Agent
- Writer Agent
- Verifier Agent

An Orchestrator discovers those agents through their A2A Agent Cards, validates their capabilities, communicates with them over A2A JSON-RPC, and coordinates a source-grounded workflow with automatic Writer ↔ Verifier revision.

---

# Current Project Status

Current version:

```text
0.1.0
```

Current stage:

```text
Development prototype / core MVP ~96% complete
```

Current live workflow:

```text
User Question
    ↓
Research Agent
    ↓
Writer Agent
    ↓
Verifier Agent
    │
    ├── PASS ───────────────► Final Answer
    │
    └── FAIL
          ↓
      Verifier Feedback
          ↓
      Writer Revision
          ↓
      Verifier Again
          ↓
      PASS or Revision #2
```

Current automated test status:

```text
154 passed
0 failed
1 non-blocking Starlette/httpx test deprecation warning
```

The real live A2A workflow has also been validated with:

```text
Verification attempt 1: FAIL
Revision 1 requested
Revision 1 completed

Verification attempt 2: FAIL
Revision 2 requested
Revision 2 completed

Verification attempt 3: PASS
Draft accepted after 3 verification attempt(s) and 2 revision(s)
```

---

# High-Level Architecture

```text
                           ┌──────────────────┐
                           │       User       │
                           └────────┬─────────┘
                                    │
                                    ▼
                           ┌──────────────────┐
                           │   Orchestrator   │
                           │                  │
                           │ • Discovery      │
                           │ • Validation     │
                           │ • A2A Client     │
                           │ • Workflow       │
                           │ • Revision Loop  │
                           │ • Logging        │
                           └────────┬─────────┘
                                    │
                    ┌───────────────┼────────────────┐
                    │               │                │
                    ▼               ▼                ▼
            ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
            │   Research   │ │    Writer    │ │   Verifier   │
            │    Agent     │ │    Agent     │ │    Agent     │
            │              │ │              │ │              │
            │ Port 8001    │ │ Port 8002    │ │ Port 8003    │
            └──────┬───────┘ └──────┬───────┘ └──────┬───────┘
                   │                │                │
                   ▼                ▼                ▼
              Tavily + Groq      Groq LLM         Groq LLM
```

---

# Current Agent Contracts

| Agent | Port | Skill | Input | Output |
|---|---:|---|---|---|
| Research Agent | 8001 | `research_topic` | `text/plain` | `application/json` |
| Writer Agent | 8002 | `write_explanation` | `application/json` | `text/plain` |
| Verifier Agent | 8003 | `verify_answer` | `application/json` | `application/json` |

All three agents advertise:

```text
protocolBinding = JSONRPC
protocolVersion = 1.0
streaming = true
```

---

# Research Agent

Location:

```text
agents/research/
```

Default URL:

```text
http://127.0.0.1:8001
```

A2A skill:

```text
research_topic
```

The Research Agent now performs real Tavily-backed web research and returns a structured `ResearchResult`.

Current research flow:

```text
Question
   ↓
SearchService
   ↓
TavilySearchProvider
   ↓
Search Hits
   ↓
Source Normalization / Deduplication
   ↓
Evidence Extraction
   ↓
LLM Claim Generation
   ↓
LLM Research Synthesis
   ↓
ResearchResult
```

The structured result contains:

```text
question
summary
sources[]
evidence[]
claims[]
caveats[]
```

The provenance chain is:

```text
Claim
  ↓
Evidence
  ↓
Source
```

This allows downstream agents to trace claims back to evidence and source URLs.

## Current Research Limitation

Evidence is currently built primarily from Tavily result content/snippets.

The project does **not yet fetch and parse the full body of every webpage or PDF** before extracting evidence.

Planned upgrade:

```text
Search
  ↓
Fetch Page / Document
  ↓
Content-Type + Size Validation
  ↓
HTML / PDF Extraction
  ↓
Chunking
  ↓
Relevant Passage Selection
  ↓
Evidence
  ↓
Claims
```

---

# Writer Agent

Location:

```text
agents/writer/
```

Default URL:

```text
http://127.0.0.1:8002
```

A2A skill:

```text
write_explanation
```

The Writer Agent consumes a structured `ResearchResult` and produces a polished answer with source citations such as:

```text
[src_1]
[src_2]
```

Current Writer capabilities:

```text
Use only supplied research
Preserve important caveats
Use source IDs from the ResearchResult
Reject unknown source citations
Require citations when research claims/sources exist
Perform one automatic repair attempt for citation-validation failure
Produce user-facing prose instead of JSON
```

The Writer also supports verifier-driven revision requests.

Revision request structure:

```text
mode = "revise"
research = ResearchResult
draft = previous Writer answer
feedback = Verifier feedback
issues[] = structured Verifier issues
```

Revision flow:

```text
Existing Draft
    +
Verifier Issues
    +
Verifier Feedback
    +
Structured Research
    ↓
Writer Revision
    ↓
Citation Validation
    ↓
Revised Draft
```

---

# Verifier Agent

Location:

```text
agents/verifier/
```

Default URL:

```text
http://127.0.0.1:8003
```

A2A skill:

```text
verify_answer
```

The Verifier receives:

```text
ResearchResult
+
Writer Draft
```

and returns a structured result:

```json
{
  "verdict": "PASS",
  "issues": [],
  "feedback": ""
}
```

or:

```json
{
  "verdict": "FAIL",
  "issues": [
    {
      "type": "citation_mismatch",
      "statement": "Example statement",
      "source_ids": ["src_1"],
      "feedback": "Explain what must be corrected."
    }
  ],
  "feedback": "Concise revision guidance."
}
```

Supported issue types currently include:

```text
missing_citation
unknown_citation
unsupported_claim
citation_mismatch
changed_fact
overstated_certainty
dropped_caveat
contradiction
other
```

The Verifier uses two layers:

```text
1. Deterministic checks
2. Evidence-aware LLM semantic verification
```

Deterministic checks currently catch:

```text
Unknown source citations
Research-based drafts with zero citations
```

Semantic verification checks:

```text
Unsupported claims
Citation mismatch
Changed facts
Overstated certainty
Dropped caveats
Contradictions
Invented information
Missing citations
```

## Current Verifier Limitation

The next planned improvement is stricter **sentence-level citation coverage**.

Current deterministic behavior catches a draft with zero citations, but a draft can still contain:

```text
Sentence 1 has a factual claim. [src_1]
Sentence 2 has another factual claim.
Sentence 3 has a factual claim. [src_2]
```

and sentence 2 currently depends mainly on the semantic LLM verifier to be caught.

This is the immediate next task.

---

# Automatic Revision Loop

Location:

```text
orchestrator/revision_loop.py
```

The revision loop is fully integrated into the real orchestrator.

Default maximum revisions:

```text
2
```

Flow:

```text
Initial Writer Draft
      ↓
Verifier
      │
      ├── PASS
      │     ↓
      │  Final Answer
      │
      └── FAIL
            ↓
        Build Revision Request
            ↓
        Writer Revision
            ↓
        Verifier Again
            ↓
      PASS or another revision
```

The loop now logs each attempt:

```text
Verification attempt 1 started.
Verification attempt 1: FAIL
Revision 1 requested.
Revision 1 completed.
Verification attempt 2 started.
Verification attempt 2: PASS
Draft accepted after 2 verification attempt(s) and 1 revision(s).
```

This makes live agent behavior visible and easier to debug.

---

# Orchestrator

Location:

```text
orchestrator/
```

The Orchestrator does not directly call Groq or Tavily.

Instead, it coordinates independent agents over A2A.

Responsibilities:

```text
Validate user input
Discover required agents
Read Agent Cards
Validate JSONRPC support
Validate required skills
Send A2A messages
Consume A2A streaming events
Extract artifacts
Sequence Research -> Writer -> Verifier
Run automatic revision loop
Measure execution time
Log workflow events
Return WorkflowResult
```

Current workflow:

```text
Question
   ↓
Research Agent
   ↓
Structured ResearchResult JSON
   ↓
Writer Agent
   ↓
Citation-backed Draft
   ↓
Verifier Agent
   ↓
PASS / FAIL
   ↓
Automatic Revision if needed
   ↓
Final Answer
```

`WorkflowResult` contains:

```text
question
research
final_answer
```

---

# Agent Discovery

Each agent exposes:

```text
/.well-known/agent-card.json
```

Examples:

```text
http://127.0.0.1:8001/.well-known/agent-card.json
http://127.0.0.1:8002/.well-known/agent-card.json
http://127.0.0.1:8003/.well-known/agent-card.json
```

The Orchestrator validates:

```text
JSONRPC protocol binding
Required skill
Service URL
Agent interface
```

Required skills:

```text
Research Agent -> research_topic
Writer Agent   -> write_explanation
Verifier Agent -> verify_answer
```

---

# Health Endpoints

Research Agent:

```text
GET http://127.0.0.1:8001/health
```

Writer Agent:

```text
GET http://127.0.0.1:8002/health
```

Verifier Agent:

```text
GET http://127.0.0.1:8003/health
```

PowerShell:

```powershell
Invoke-RestMethod http://127.0.0.1:8001/health
Invoke-RestMethod http://127.0.0.1:8002/health
Invoke-RestMethod http://127.0.0.1:8003/health
```

---

# HTTP Endpoints

Each agent exposes:

```text
GET  /health
GET  /.well-known/agent-card.json
POST /
```

Purpose:

```text
GET /health
    Development / monitoring health check

GET /.well-known/agent-card.json
    A2A discovery

POST /
    A2A JSON-RPC communication
```

Opening the root URL in a browser may show:

```text
405 Method Not Allowed
```

That is expected because browsers normally send:

```text
GET /
```

while the A2A task endpoint expects:

```text
POST /
```

---

# Technology Stack

Current development environment:

| Technology | Purpose | Current Version |
|---|---|---:|
| Python | Application language | 3.10.6 |
| uv | Environment / dependency manager | 0.11.6 |
| a2a-sdk | Agent2Agent protocol | 1.2.1 |
| Groq SDK | LLM API client | 1.7.0 |
| HTTPX | Async HTTP communication | 0.28.1 |
| python-dotenv | Environment configuration | 1.2.4 |
| pytest | Automated testing | 9.1.1 |
| pytest-asyncio | Async test support | 1.4.0 |
| Starlette | ASGI app framework | project dependency |
| Uvicorn | ASGI server | project dependency |
| Tavily | Web search provider | API integration |

Current Groq model:

```text
openai/gpt-oss-120b
```

---

# Project File Structure

```text
a2a-multi-agent/
│
├── .env
├── .env.example
├── .gitignore
├── pyproject.toml
├── README.md
├── uv.lock
│
├── agents/
│   ├── __init__.py
│   │
│   ├── research/
│   │   ├── __init__.py
│   │   ├── app.py
│   │   ├── card.py
│   │   ├── executor.py
│   │   ├── factory.py
│   │   ├── prompts.py
│   │   ├── schemas.py
│   │   ├── search.py
│   │   ├── sources.py
│   │   ├── evidence.py
│   │   ├── claims.py
│   │   ├── assembler.py
│   │   ├── pipeline.py
│   │   ├── synthesizer.py
│   │   └── providers/
│   │       ├── __init__.py
│   │       └── tavily.py
│   │
│   ├── writer/
│   │   ├── __init__.py
│   │   ├── app.py
│   │   ├── card.py
│   │   ├── executor.py
│   │   ├── prompts.py
│   │   ├── context.py
│   │   ├── generator.py
│   │   └── revision.py
│   │
│   └── verifier/
│       ├── __init__.py
│       ├── app.py
│       ├── card.py
│       ├── executor.py
│       ├── prompts.py
│       ├── schemas.py
│       ├── context.py
│       └── generator.py
│
├── core/
│   ├── __init__.py
│   ├── config.py
│   ├── llm.py
│   └── logging_config.py
│
├── orchestrator/
│   ├── __init__.py
│   ├── client.py
│   ├── discovery.py
│   ├── workflow.py
│   ├── revision_loop.py
│   └── main.py
│
└── tests/
    ├── conftest.py
    ├── test_orchestrator.py
    ├── test_revision_loop.py
    ├── test_research_agent.py
    ├── test_research_schemas.py
    ├── test_research_search.py
    ├── test_research_sources.py
    ├── test_research_evidence.py
    ├── test_research_claims.py
    ├── test_research_assembler.py
    ├── test_research_pipeline.py
    ├── test_research_synthesizer.py
    ├── test_tavily_search_provider.py
    ├── test_writer_context.py
    ├── test_writer_generator.py
    ├── test_writer_revision.py
    ├── test_writer_agent.py
    ├── test_verifier_context.py
    ├── test_verifier_generator.py
    └── test_verifier_agent.py
```

---

# Environment Variables

Create:

```text
.env
```

Example:

```env
GROQ_API_KEY=your_groq_api_key_here
GROQ_MODEL=openai/gpt-oss-120b

TAVILY_API_KEY=your_tavily_api_key_here

RESEARCH_AGENT_HOST=127.0.0.1
RESEARCH_AGENT_PORT=8001

WRITER_AGENT_HOST=127.0.0.1
WRITER_AGENT_PORT=8002

VERIFIER_AGENT_HOST=127.0.0.1
VERIFIER_AGENT_PORT=8003
```

A safe template should remain in:

```text
.env.example
```

Never commit the real:

```text
.env
```

Never place real API keys in:

```text
README.md
.env.example
Git
GitHub
public logs
screenshots intended for sharing
```

---

# Environment Setup

Recommended project Python:

```text
Python 3.10
```

Create the virtual environment:

```powershell
uv venv --python 3.10
```

Activate it if desired:

```powershell
.\.venv\Scripts\Activate.ps1
```

For an existing clone:

```powershell
uv sync
```

Most commands can also be run directly through:

```powershell
uv run ...
```

---

# Running the Project

Use four PowerShell windows during development.

## Terminal 1 — Research Agent

```powershell
cd D:\a2a-multi-agent
uv run python -m agents.research.app
```

## Terminal 2 — Writer Agent

```powershell
cd D:\a2a-multi-agent
uv run python -m agents.writer.app
```

## Terminal 3 — Verifier Agent

```powershell
cd D:\a2a-multi-agent
uv run python -m agents.verifier.app
```

## Terminal 4 — Orchestrator

```powershell
cd D:\a2a-multi-agent
uv run python -m orchestrator.main
```

Interactive example:

```text
Ask a question: What is retrieval augmented generation and why is it useful?
```

---

# Useful Development Commands

Compile everything:

```powershell
uv run python -m compileall core agents orchestrator tests
```

Run all tests:

```powershell
uv run pytest -v
```

Run revision-loop tests:

```powershell
uv run pytest tests\test_revision_loop.py -v
```

Run orchestrator tests:

```powershell
uv run pytest tests\test_orchestrator.py -v
```

Run Verifier tests:

```powershell
uv run pytest tests\test_verifier_generator.py -v
```

Check all health endpoints:

```powershell
Invoke-RestMethod http://127.0.0.1:8001/health
Invoke-RestMethod http://127.0.0.1:8002/health
Invoke-RestMethod http://127.0.0.1:8003/health
```

View Research Agent Card:

```powershell
Invoke-RestMethod http://127.0.0.1:8001/.well-known/agent-card.json |
    ConvertTo-Json -Depth 10
```

View Writer Agent Card:

```powershell
Invoke-RestMethod http://127.0.0.1:8002/.well-known/agent-card.json |
    ConvertTo-Json -Depth 10
```

View Verifier Agent Card:

```powershell
Invoke-RestMethod http://127.0.0.1:8003/.well-known/agent-card.json |
    ConvertTo-Json -Depth 10
```

---

# Automated Testing

Current latest successful run:

```text
154 passed
1 warning
```

The current warning is non-blocking:

```text
StarletteDeprecationWarning:
Using httpx with starlette.testclient is deprecated;
install httpx2 instead.
```

This does not currently break:

```text
Research Agent
Writer Agent
Verifier Agent
A2A communication
Orchestrator
Revision loop
```

The test suite now covers:

```text
Agent discovery
Connection failures
Discovery timeout
Agent Card validation
Research structured schemas
Search service
Source normalization
Evidence extraction
Claim generation
Research assembly
Research pipeline
Research synthesis
Tavily provider
Research Agent A2A behavior
Writer context
Writer citation validation
Writer automatic citation repair
Writer revision requests
Writer Agent normal/revision routing
Verifier request parsing
Verifier deterministic checks
Verifier semantic verification
Verifier Agent A2A behavior
Revision-loop PASS path
Revision-loop FAIL -> revision -> PASS
Maximum two-revision protection
Revision-loop logging
Complete orchestrator workflow
```

---

# Current Live Validation

The real three-agent system has been run successfully.

Validated live:

```text
Research Agent discovered
Writer Agent discovered
Verifier Agent discovered
Research request completed
Writer produced draft
Verifier evaluated draft
Writer revision was requested
Writer returned revision
Verifier re-evaluated revision
Maximum revision logic worked
Final PASS returned a final answer
```

A real observed revision sequence:

```text
Verification attempt 1: FAIL
Revision 1 requested
Revision 1 completed
Verification attempt 2: FAIL
Revision 2 requested
Revision 2 completed
Verification attempt 3: PASS
```

This proves the automatic correction loop works across real A2A services, not only mocked tests.

---

# Current Limitations

## 1. Sentence-Level Citation Coverage

This is the **immediate next task**.

The Verifier currently has strong citation and semantic checks, but deterministic citation coverage is not yet sentence-aware.

Goal:

```text
Factual sentence [src_1]     -> valid
Factual sentence             -> missing_citation
Another factual sentence [src_2] -> valid
```

Likely files to modify next:

```text
agents/verifier/generator.py
tests/test_verifier_generator.py
```

## 2. Full-Page / Document Evidence Extraction

Research currently relies primarily on Tavily result content/snippets.

Next research upgrade should add:

```text
Webpage fetching
Timeouts
Maximum response size
Content-Type validation
HTML text extraction
PDF handling
Chunking
Relevant-passage selection
Evidence-from-chunks
```

## 3. Reliability Hardening

Still desirable:

```text
Retry logic
Exponential backoff
More specific exception types
Graceful degradation
Agent availability preflight
Better malformed-response handling
Request correlation IDs
Structured metrics
```

## 4. Production Security

The current system is intended for:

```text
Local development
Learning
Architecture experimentation
A2A prototyping
```

It is not yet production-secure.

Production would require:

```text
HTTPS / TLS
Authentication
Authorization
Secret management
Rate limiting
Network isolation
Audit logs
Persistent task storage
Monitoring
Alerting
Prompt-injection defenses
```

---

# Current Completed Milestones

```text
[✓] Python 3.10 project environment
[✓] uv environment management
[✓] Groq integration
[✓] Central configuration
[✓] Shared async LLM layer

[✓] Research Agent
[✓] Research Agent Card
[✓] Research health endpoint
[✓] Tavily web search integration
[✓] Structured Source model
[✓] Structured Evidence model
[✓] Structured Claim model
[✓] Structured ResearchResult
[✓] Claim -> Evidence -> Source provenance
[✓] Research pipeline
[✓] Research synthesis
[✓] Research card text/plain -> application/json contract

[✓] Writer Agent
[✓] Writer Agent Card
[✓] Writer health endpoint
[✓] Structured research parsing
[✓] Citation-aware generation
[✓] Unknown citation rejection
[✓] Missing-citation validation
[✓] One automatic citation repair
[✓] Writer revision request schema
[✓] Verifier-feedback revision support
[✓] Writer A2A normal/revision routing

[✓] Verifier Agent
[✓] Verifier Agent Card
[✓] Verifier health endpoint
[✓] Structured verification request
[✓] Structured verification result
[✓] Unknown citation detection
[✓] Missing citation detection
[✓] Unsupported claim checking
[✓] Citation mismatch checking
[✓] Changed-fact checking
[✓] Overstated-certainty checking
[✓] Dropped-caveat checking
[✓] Contradiction checking
[✓] Evidence-aware semantic verification

[✓] A2A JSON-RPC communication
[✓] Streaming event handling
[✓] Artifact extraction
[✓] Reusable A2A client
[✓] Explicit agent discovery
[✓] Protocol validation
[✓] Skill validation

[✓] Research -> Writer -> Verifier orchestration
[✓] Automatic Writer revision loop
[✓] Maximum 2 revisions
[✓] Revision-loop logging
[✓] Live FAIL -> revision -> FAIL -> revision -> PASS validation

[✓] 154 automated tests passing
```

---

# Immediate Next Milestone

When development resumes, continue with:

```text
Stricter sentence-level citation coverage in the Verifier
```

Start by reviewing:

```powershell
Get-Content agents\verifier\generator.py
Get-Content tests\test_verifier_generator.py
```

Desired behavior:

```text
Draft contains factual sentence with citation
    ↓
OK

Draft contains factual sentence without citation
    ↓
FAIL
type = missing_citation
```

After that:

```text
Sentence-level citation coverage
        ↓
Full webpage/document evidence extraction
        ↓
Retry/error hardening
        ↓
README/final cleanup
        ↓
Final end-to-end validation
```

Estimated current MVP completion:

```text
~96%
```

---

# Recommended Git Checkpoint Before Shutdown

Check what changed:

```powershell
git status
```

Confirm `.env` is not staged.

Then, if the changes look correct:

```powershell
git add .
git status
git commit -m "feat: add evidence-aware verification and automatic revision loop"
```

Do **not** commit `.env`.

---

# Resume Checklist

After turning the machine back on:

```powershell
cd D:\a2a-multi-agent
uv run pytest -v
```

Expected baseline:

```text
154 passed
1 warning
```

Then start:

```powershell
uv run python -m agents.research.app
```

```powershell
uv run python -m agents.writer.app
```

```powershell
uv run python -m agents.verifier.app
```

Finally:

```powershell
uv run python -m orchestrator.main
```

Immediate coding task after resume:

```text
Sentence-level citation coverage in EvidenceAwareVerifier
```

---

# Long-Term Direction

The long-term goal is to evolve this project into a modular AI-agent platform where specialized agents collaborate over A2A.

Potential future capabilities:

```text
Planner / Router Agent
Browser Agent
RAG Agent
Coder Agent
File Agent
Memory Agent
Vision Agent
Data Analysis Agent
API Agent
Database Agent
Security Agent
Parallel agent execution
Persistent workflows
Private knowledge retrieval
Source-grounded answers
Dynamic agent selection
```

The design principle remains:

```text
Specialized agents
+
Standard A2A interfaces
+
Explicit orchestration
+
Evidence-backed generation
+
Independent verification
```

rather than one large monolithic agent.

---

# Version

```text
Project: A2A Multi-Agent System
Version: 0.1.0
Stage: Development Prototype / Core MVP

Current Agents:
- Research Agent
- Writer Agent
- Verifier Agent

Current Workflow:
Research -> Writer -> Verifier
                    ↓
               Revision Loop

Current Test Status:
154 passed
1 warning

Current Live Status:
Three-agent A2A workflow operational
Automatic two-revision loop operational

Immediate Next Task:
Sentence-level citation coverage in Verifier

Estimated MVP Completion:
~96%
```
