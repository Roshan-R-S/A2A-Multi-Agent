# A2A Multi-Agent System

A modular multi-agent AI system built with Python, the Agent2Agent (A2A) protocol, Groq, Starlette, HTTPX, and Uvicorn.

The project currently implements two independent AI agents:

- Research Agent
- Writer Agent

An Orchestrator discovers the agents through their A2A Agent Cards, validates their capabilities, communicates with them over A2A JSON-RPC, and coordinates a complete:

```text
Research -> Writer
```

workflow.

The architecture is intentionally modular so the project can later grow into a larger AI-agent platform containing retrieval, web browsing, verification, coding, memory, planning, RAG, tools, and dynamic agent routing.

---

# Current Project Status

Current version:

```text
0.1.0
```

Current architecture:

```text
Research Agent -> Writer Agent
```

Current status:

```text
Local development prototype
```

Current automated test status:

```text
12 passed
0 failed
1 non-blocking Starlette test deprecation warning
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
                         │ • Workflow       │
                         │ • A2A Client     │
                         │ • Logging        │
                         └────────┬─────────┘
                                  │
                 ┌────────────────┴────────────────┐
                 │                                 │
                 ▼                                 ▼
        ┌─────────────────┐              ┌─────────────────┐
        │ Research Agent  │              │  Writer Agent   │
        │                 │              │                 │
        │ Port 8001       │              │ Port 8002       │
        │ research_topic  │              │write_explanation│
        └────────┬────────┘              └────────┬────────┘
                 │                                 │
                 ▼                                 ▼
              Groq LLM                          Groq LLM
```

Actual workflow:

```text
User Question
     │
     ▼
Orchestrator
     │
     ├── Discover Research Agent
     │
     ├── Validate JSONRPC support
     │
     ├── Validate research_topic skill
     │
     ▼
Research Agent
     │
     ▼
Groq
     │
     ▼
Structured Research Brief
     │
     ▼
Orchestrator
     │
     ├── Discover Writer Agent
     │
     ├── Validate JSONRPC support
     │
     ├── Validate write_explanation skill
     │
     ▼
Writer Agent
     │
     ▼
Groq
     │
     ▼
Final Polished Answer
     │
     ▼
User
```

---

# Core Features

## Independent A2A Agents

Each agent runs as its own independent HTTP service.

The Research Agent and Writer Agent do not need to know each other's Python implementation.

They expose standardized A2A interfaces that allow clients and orchestrators to discover and communicate with them.

---

## Agent Discovery

Every agent exposes:

```text
/.well-known/agent-card.json
```

Example:

```text
http://127.0.0.1:8001/.well-known/agent-card.json
```

The Agent Card describes:

```text
Agent name
Description
Version
Capabilities
Skills
Input modes
Output modes
Protocol binding
Protocol version
Service URL
Examples
```

The Orchestrator reads this information before executing the workflow.

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

The Research Agent receives a topic or question and produces a structured research brief.

Responsibilities:

```text
Analyze the requested topic
Identify important concepts
Explain technical details
Identify limitations and caveats
Avoid unnecessary filler
Avoid pretending that live web research occurred
Prepare information for the Writer Agent
Return the result as an A2A artifact
```

Typical research structure:

```text
Overview

Key Points

Important Details

Limitations / Caveats

Summary
```

Current internal flow:

```text
Question
   │
   ▼
ResearchAgentExecutor
   │
   ▼
ResearchAgent
   │
   ▼
core.llm.generate_text()
   │
   ▼
Groq
   │
   ▼
Structured Research Brief
   │
   ▼
A2A Artifact
```

## Important Research Agent Limitation

The current Research Agent is an LLM-based analysis agent.

It does **not yet perform actual live research**.

It currently does:

```text
Question
   ↓
LLM knowledge / reasoning
   ↓
Research brief
```

It does not currently perform:

```text
Live web search
Browser automation
Document retrieval
Vector search
RAG
Source verification
Automatic citations
External API research
```

These capabilities are planned for later versions.

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

The Writer Agent receives:

```text
Original user question
+
Research Agent brief
```

and turns them into a polished final response.

Responsibilities:

```text
Preserve important research facts
Improve clarity
Improve organization
Explain technical concepts simply
Remove unnecessary repetition
Preserve uncertainty
Preserve limitations and caveats
Avoid inventing new factual claims
Return a user-friendly final response
```

Current flow:

```text
Original Question
       +
Research Brief
       │
       ▼
WriterAgentExecutor
       │
       ▼
WriterAgent
       │
       ▼
Groq
       │
       ▼
Final Answer
       │
       ▼
A2A Artifact
```

---

# Orchestrator

Location:

```text
orchestrator/
```

The Orchestrator coordinates the complete system.

Current responsibilities:

```text
Discover agents
Read Agent Cards
Validate protocols
Validate required skills
Send A2A messages
Receive streaming A2A events
Extract artifacts
Sequence agents
Handle timeouts
Measure execution time
Log workflow events
Return the final response
```

Current workflow:

```text
Research -> Writer
```

The Orchestrator does not directly call Groq.

Instead:

```text
Orchestrator
    │
    ├── A2A -> Research Agent -> Groq
    │
    └── A2A -> Writer Agent   -> Groq
```

This keeps agent implementation separate from workflow orchestration.

---

# Agent2Agent Communication

Communication follows:

```text
A2A
 ↓
JSON-RPC
 ↓
HTTP
```

The A2A Python SDK internally works with typed objects such as:

```text
AgentCard
AgentInterface
AgentSkill
Message
Part
Task
Artifact
SendMessageRequest
TaskState
```

The application normally does not need to manually construct raw JSON-RPC requests.

---

# A2A Task Lifecycle

A typical agent execution looks like:

```text
Incoming Message
      │
      ▼
Create Task
      │
      ▼
TASK_STATE_WORKING
      │
      ▼
Run Agent Logic
      │
      ▼
Call Groq
      │
      ▼
Generate Result
      │
      ▼
Create Artifact
      │
      ▼
TASK_STATE_COMPLETED
```

The Orchestrator prefers actual A2A artifact output over task/status messages.

---

# A2A Agent Cards

## Research Agent Card

Advertises:

```text
Name:
Research Agent

Version:
0.1.0

Protocol:
JSONRPC

Protocol Version:
1.0

URL:
http://127.0.0.1:8001

Skill:
research_topic

Input:
text/plain

Output:
text/plain

Streaming:
true
```

## Writer Agent Card

Advertises:

```text
Name:
Writer Agent

Version:
0.1.0

Protocol:
JSONRPC

Protocol Version:
1.0

URL:
http://127.0.0.1:8002

Skill:
write_explanation

Input:
text/plain

Output:
text/plain

Streaming:
true
```

---

# Agent Discovery Validation

Before starting a workflow, the Orchestrator verifies that the discovered Research Agent advertises:

```text
research_topic
```

and the discovered Writer Agent advertises:

```text
write_explanation
```

It also validates:

```text
protocolBinding == JSONRPC
```

This prevents the Orchestrator from blindly sending work to incompatible agents.

---

# Health Endpoints

Both agents expose health endpoints.

Research Agent:

```text
GET http://127.0.0.1:8001/health
```

Writer Agent:

```text
GET http://127.0.0.1:8002/health
```

Example response:

```json
{
  "status": "ok",
  "agent": "Research Agent",
  "version": "0.1.0"
}
```

PowerShell:

```powershell
Invoke-RestMethod http://127.0.0.1:8001/health
Invoke-RestMethod http://127.0.0.1:8002/health
```

---

# HTTP Endpoints

## Research Agent

```text
GET  /health
GET  /.well-known/agent-card.json
POST /
```

## Writer Agent

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

---

# Why `/` Shows 405 in a Browser

If you open:

```text
http://127.0.0.1:8001/
```

or:

```text
http://127.0.0.1:8002/
```

in a browser, you may see:

```text
405 Method Not Allowed
```

This is expected.

Browsers send:

```text
GET /
```

but the root endpoint is designed for:

```text
POST /
```

because it is the A2A JSON-RPC endpoint.

For browser testing use:

```text
http://127.0.0.1:8001/health
http://127.0.0.1:8002/health
```

or:

```text
http://127.0.0.1:8001/.well-known/agent-card.json
http://127.0.0.1:8002/.well-known/agent-card.json
```

---

# Technology Stack

Current development environment:

| Technology | Purpose | Current Version |
|---|---|---:|
| Python | Application language | 3.10.6 |
| uv | Python environment and dependency manager | 0.11.6 during development |
| a2a-sdk | Agent2Agent protocol implementation | 1.2.1 |
| Groq SDK | LLM API client | 1.7.0 |
| HTTPX | Async HTTP communication | 0.28.1 |
| python-dotenv | Environment configuration | 1.2.4 |
| Starlette | ASGI application framework | 1.7.0 |
| Uvicorn | ASGI server | Project dependency |
| pytest | Automated testing | 9.1.1 |
| pytest-asyncio | Async testing | 1.4.0 |

Current Groq model configuration:

```text
openai/gpt-oss-120b
```

The model is configurable through environment variables and is not hard-coded into individual agents.

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
│   │   └── prompts.py
│   │
│   └── writer/
│       ├── __init__.py
│       ├── app.py
│       ├── card.py
│       ├── executor.py
│       └── prompts.py
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
│   └── main.py
│
└── tests/
    ├── __init__.py
    ├── conftest.py
    ├── test_orchestrator.py
    ├── test_research_agent.py
    └── test_writer_agent.py
```

---

# Module Responsibilities

## `core/config.py`

Responsible for application configuration.

Loads:

```text
GROQ_API_KEY
GROQ_MODEL

RESEARCH_AGENT_HOST
RESEARCH_AGENT_PORT

WRITER_AGENT_HOST
WRITER_AGENT_PORT
```

Also provides:

```text
research_agent_url
writer_agent_url
```

Configuration is loaded from:

```text
.env
```

---

# `core/llm.py`

Central LLM abstraction.

Uses:

```python
AsyncGroq
```

Agents call:

```python
generate_text(...)
```

instead of directly creating Groq clients.

Advantages:

```text
One place for model configuration
One place for provider integration
Easy future provider replacement
Cleaner agent code
Shared async implementation
```

---

# `core/logging_config.py`

Configures application logging.

Current log format:

```text
timestamp | log level | logger | message
```

Example:

```text
2026-10-04 16:48:05 | INFO | orchestrator.workflow | Workflow started
```

---

# `agents/research/prompts.py`

Contains the Research Agent's system instructions.

Separating prompts from executor code makes it easier to modify agent behavior without touching networking or task-management logic.

---

# `agents/research/card.py`

Defines the Research Agent A2A Agent Card.

Contains:

```text
Name
Description
Version
Capabilities
Interface
Skill
Examples
Input modes
Output modes
```

---

# `agents/research/executor.py`

Implements the Research Agent's A2A execution logic.

Responsible for:

```text
Reading the user message
Creating/reusing an A2A task
Setting WORKING state
Calling ResearchAgent
Calling the shared LLM layer
Creating an artifact
Setting COMPLETED state
```

---

# `agents/research/app.py`

Creates the Research Agent HTTP application.

Includes:

```text
Starlette application
A2A Agent Card routes
A2A JSON-RPC routes
/health endpoint
Uvicorn startup
```

---

# `agents/writer/prompts.py`

Contains the Writer Agent's system instructions.

Its job is to transform research into a clear final answer without inventing unsupported facts.

---

# `agents/writer/card.py`

Defines the Writer Agent A2A Agent Card.

---

# `agents/writer/executor.py`

Implements the Writer Agent A2A task lifecycle.

---

# `agents/writer/app.py`

Creates the Writer Agent HTTP application.

Includes:

```text
A2A routes
Agent Card route
Health route
Uvicorn server
```

---

# `orchestrator/client.py`

Reusable A2A client.

Responsibilities:

```text
Create A2A messages
Generate unique message IDs
Create A2A clients
Configure transport
Configure HTTP timeouts
Send messages
Consume streaming events
Extract artifacts
Extract normal messages
Prefer artifacts over status messages
Close client resources
```

---

# Client Timeout Configuration

AI requests can take longer than ordinary HTTP requests.

The current client uses approximately:

```text
Connect timeout: 10 seconds
Read timeout:    120 seconds
Write timeout:   30 seconds
Pool timeout:    10 seconds
```

The extended read timeout prevents normal LLM generation from failing because of HTTPX's shorter default timeout.

Timeouts remain finite so failed requests do not hang forever.

---

# `orchestrator/discovery.py`

Responsible for explicitly discovering A2A agents.

It fetches:

```text
/.well-known/agent-card.json
```

and extracts:

```text
Agent name
Description
Version
URL
Protocol
Protocol version
Skills
```

It handles:

```text
Connection failures
Discovery timeouts
HTTP errors
Invalid Agent Cards
Missing interfaces
Malformed data
```

---

# `orchestrator/workflow.py`

Defines the current workflow:

```text
Research -> Writer
```

Responsibilities:

```text
Validate user input
Discover required agents
Validate JSONRPC
Validate required skills
Create Research prompt
Call Research Agent
Collect research artifact
Create Writer prompt
Call Writer Agent
Collect final artifact
Measure execution time
Return WorkflowResult
```

`WorkflowResult` contains:

```text
question
research
final_answer
```

---

# `orchestrator/main.py`

Command-line entry point.

Responsibilities:

```text
Parse CLI arguments
Prompt user interactively
Configure logging
Start workflow
Handle exceptions
Optionally display research
Display final answer
```

---

# Environment Setup

## Requirements

Recommended:

```text
Python 3.10+
uv
Groq API key
```

The current development environment uses:

```text
Python 3.10.6
```

---

# Create Virtual Environment

From the project root:

```powershell
uv venv --python 3.10
```

Activate it:

```powershell
.\.venv\Scripts\Activate.ps1
```

You should see something similar to:

```text
(a2a-multi-agent) PS D:\a2a-multi-agent>
```

---

# Install Dependencies

For an existing clone containing `pyproject.toml` and `uv.lock`:

```powershell
uv sync
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

RESEARCH_AGENT_HOST=127.0.0.1
RESEARCH_AGENT_PORT=8001

WRITER_AGENT_HOST=127.0.0.1
WRITER_AGENT_PORT=8002
```

A safe template is stored in:

```text
.env.example
```

Never commit your real:

```text
.env
```

file.

---

# Running the Project

The easiest development setup uses three PowerShell windows.

---

## Terminal 1 — Research Agent

From the project root:

```powershell
uv run python -m agents.research.app
```

Expected:

```text
Starting Research Agent at http://127.0.0.1:8001
Health: http://127.0.0.1:8001/health
Agent Card: http://127.0.0.1:8001/.well-known/agent-card.json
```

---

## Terminal 2 — Writer Agent

```powershell
uv run python -m agents.writer.app
```

Expected:

```text
Starting Writer Agent at http://127.0.0.1:8002
Health: http://127.0.0.1:8002/health
Agent Card: http://127.0.0.1:8002/.well-known/agent-card.json
```

---

## Terminal 3 — Orchestrator

```powershell
uv run python -m orchestrator.main
```

Example:

```text
Ask a question: What is retrieval augmented generation?
```

---

# CLI Usage

## Interactive Mode

```powershell
uv run python -m orchestrator.main
```

---

## Pass Question Directly

```powershell
uv run python -m orchestrator.main "Explain how transformers work"
```

---

## Show Intermediate Research

```powershell
uv run python -m orchestrator.main --show-research
```

or:

```powershell
uv run python -m orchestrator.main --show-research "Explain RAG"
```

Output:

```text
======================================================================
RESEARCH BRIEF
======================================================================

...

======================================================================
FINAL ANSWER
======================================================================

...
```

---

# Workflow Logging

The project records important workflow events.

Example:

```text
Workflow started
Discovering Research Agent...
Research Agent discovered
Discovering Writer Agent...
Writer Agent discovered
Required agent capabilities validated
Research request started
Research completed in 5.90 seconds
Writer request started
Writer completed in 5.04 seconds
Workflow completed in 11.00 seconds
```

This makes it possible to identify:

```text
Discovery delays
Research latency
Writer latency
Total workflow latency
Agent failures
HTTP problems
```

---

# Example Observed Performance

During development, one test workflow completed approximately as follows:

```text
Research: ~5.90 seconds
Writer:   ~5.04 seconds
Total:    ~11.00 seconds
```

These timings are not guarantees.

They depend on:

```text
Network latency
Groq availability
Model load
Prompt size
Generated response size
Local machine conditions
```

---

# Automated Testing

The project includes automated unit/integration-style tests.

Run:

```powershell
uv run pytest -v
```

Current result:

```text
12 passed
0 failed
```

---

# Current Test Coverage

The current suite tests:

```text
Valid Agent Card discovery
Agent connection failure
Agent discovery timeout
Missing Agent Card interface
Empty workflow question
Missing Research Agent skill
Discovery failure propagation
Successful Research -> Writer workflow
Research /health endpoint
Research Agent Card endpoint
Writer /health endpoint
Writer Agent Card endpoint
```

The tests avoid making real Groq requests where possible.

Mocked components include:

```text
HTTP transport
Agent Cards
A2A client behavior
Discovery responses
Research output
Writer output
```

This makes tests:

```text
Fast
Repeatable
Free from API token usage
Independent from Groq availability
```

---

# Current Test Result

Latest successful run:

```text
collected 12 items

12 passed
1 warning
```

The current warning is:

```text
StarletteDeprecationWarning:
Using httpx with starlette.testclient is deprecated;
install httpx2 instead.
```

This warning comes from the Starlette testing layer.

It does not currently affect the running Research Agent, Writer Agent, A2A protocol, or Orchestrator.

It can be addressed later when the dependency ecosystem is updated.

---

# Error Handling

The system currently handles or detects several failure types.

```text
Missing environment configuration
Empty user questions
Agent unavailable
Agent connection failure
Agent discovery timeout
Agent Card HTTP error
Invalid Agent Card
Missing Agent interface
Wrong protocol binding
Missing required skill
A2A request timeout
Empty A2A result
Groq/API exceptions
Workflow exceptions
```

The CLI prints errors in a readable format:

```text
Workflow failed:
ExceptionType: message
```

instead of always exposing a large traceback to the user.

---

# Example Failure

If an agent cannot respond within the configured timeout:

```text
Workflow failed:
A2AClientTimeoutError: Client Request timed out
```

The client currently gives agent requests substantially more time than standard HTTP defaults.

---

# Security

## Current Security Level

The project is currently intended for:

```text
Local development
Learning
Architecture experimentation
A2A prototyping
```

It is **not yet production-secure**.

Current protections include:

```text
.env excluded from Git
Central environment configuration
No API key printed by normal configuration checks
Agent capability validation
Finite HTTP timeouts
Input validation
```

---

# `.gitignore`

Recommended ignored files:

```gitignore
# Python
__pycache__/
*.py[cod]

# Virtual environment
.venv/

# Secrets
.env

# Testing
.pytest_cache/
.coverage
htmlcov/

# IDE
.vscode/
.idea/

# OS
.DS_Store
Thumbs.db
```

---

# Production Security Requirements

Before production deployment, add:

```text
HTTPS / TLS
Agent authentication
Agent authorization
User authentication
Service-to-service authentication
Secret manager integration
API rate limiting
Request size limits
Input validation
Prompt-injection defenses
Network isolation
Audit logs
Role-based access control
Persistent secure state
Encrypted storage
Monitoring
Alerting
Data-loss-prevention controls
```

---

# Current Limitations

The project currently has several intentional limitations.

## No Live Web Research

The Research Agent does not browse the internet.

---

## No RAG Yet

Despite being able to explain RAG, the application itself does not yet perform Retrieval-Augmented Generation.

There is currently no:

```text
Document ingestion
Chunking pipeline
Embedding model
Vector database
Retriever
Re-ranker
Private knowledge base
Citation pipeline
```

---

## No Source Verification

The Research Agent can produce plausible but incorrect or outdated claims because it currently relies on the LLM's internal knowledge.

---

## No Verifier Agent

The Writer Agent's response is currently returned directly to the user.

There is no independent validation stage yet.

Current:

```text
Research
   ↓
Writer
   ↓
User
```

Planned:

```text
Research
   ↓
Writer
   ↓
Verifier
   ↓
User
```

---

## Fixed Workflow

The current workflow is hard-coded:

```text
Research -> Writer
```

The Orchestrator does not yet dynamically decide which agents are needed.

---

## In-Memory Task Storage

The agents currently use:

```text
InMemoryTaskStore
```

Task state disappears when a service restarts.

A production system should use durable task storage.

---

## No Authentication Between Agents

A2A services currently trust local requests.

Production deployments need authenticated agent-to-agent communication.

---

## Duplicate Agent Card Requests

At the moment, Agent Cards can be fetched once by explicit discovery and again internally when the A2A client is created.

This is functionally correct but can later be optimized by reusing discovered Agent Card information.

For localhost development, the overhead is negligible.

---

# Design Philosophy

Each agent should have a focused responsibility.

For example:

```text
Research Agent
    researches

Writer Agent
    writes

Verifier Agent
    verifies

Browser Agent
    browses

RAG Agent
    retrieves private knowledge

Coder Agent
    handles coding tasks

Memory Agent
    manages useful long-term context

Planner Agent
    determines what should happen next
```

The Orchestrator coordinates agents.

The goal is to avoid building one enormous monolithic agent containing every capability.

---

# Why Use A2A?

A2A provides a standardized boundary between AI agents.

Without A2A:

```text
Orchestrator
   ↓
Custom Research API
   ↓
Different Writer API
   ↓
Different Coder API
   ↓
Different Browser API
```

With A2A:

```text
Orchestrator
       │
       ├── A2A -> Research
       ├── A2A -> Writer
       ├── A2A -> Verifier
       ├── A2A -> Browser
       └── A2A -> Coder
```

Benefits include:

```text
Loose coupling
Agent discovery
Standard interfaces
Independent deployment
Independent scaling
Replaceable agents
Language / implementation flexibility
Cleaner orchestration
Capability advertisement
```

---

# Planned Verifier Agent

The next major agent planned for the project is:

```text
Verifier Agent
```

Proposed port:

```text
8003
```

Proposed skill:

```text
verify_answer
```

Responsibilities:

```text
Inspect Writer output
Compare output with Research evidence
Detect unsupported claims
Detect contradictions
Detect missing caveats
Detect excessive certainty
Identify potentially outdated claims
Return approval or revision feedback
```

Initial flow:

```text
Question
   ↓
Research Agent
   ↓
Writer Agent
   ↓
Verifier Agent
   ↓
Final Answer
```

Later:

```text
Question
   ↓
Research
   ↓
Writer
   ↓
Verifier
   │
   ├── PASS
   │      ↓
   │   Final Answer
   │
   └── FAIL
          ↓
       Revision Feedback
          ↓
       Writer
          ↓
       Verifier Again
```

A maximum revision count should eventually be used to prevent infinite loops.

---

# Planned Research Upgrade

The Research Agent should eventually evolve from:

```text
Question
   ↓
LLM Knowledge
   ↓
Research Brief
```

into:

```text
Question
   ↓
Research Planner
   │
   ├── Web Search
   ├── Browser
   ├── APIs
   ├── Documents
   └── RAG
        ↓
Source Collection
        ↓
Source Verification
        ↓
Groq
        ↓
Grounded Research Brief
        ↓
Citations / Provenance
```

---

# Planned RAG Architecture

A future RAG system may include:

```text
Documents
   ↓
Ingestion
   ↓
Parsing
   ↓
Cleaning
   ↓
Chunking
   ↓
Embedding
   ↓
Vector Store
```

Query flow:

```text
User Query
    ↓
Query Embedding
    ↓
Vector Search
    ↓
Top-K Documents
    ↓
Optional Re-ranking
    ↓
Context Builder
    ↓
LLM
    ↓
Grounded Answer
    ↓
Citations
```

---

# Future Agent Architecture

Long-term architecture:

```text
                             User
                              │
                              ▼
                     ┌─────────────────┐
                     │   Orchestrator  │
                     │ Planner/Router  │
                     └────────┬────────┘
                              │
       ┌──────────────────────┼───────────────────────┐
       │                      │                       │
       ▼                      ▼                       ▼
┌──────────────┐       ┌──────────────┐       ┌──────────────┐
│   Research   │       │   Browser    │       │    Coder     │
│    Agent     │       │    Agent     │       │    Agent     │
└──────┬───────┘       └──────┬───────┘       └──────┬───────┘
       │                      │                       │
       └──────────────┬───────┴──────────┬────────────┘
                      │                  │
                      ▼                  ▼
               ┌──────────────┐   ┌──────────────┐
               │  RAG Agent   │   │ Memory Agent │
               └──────┬───────┘   └──────┬───────┘
                      │                  │
                      └─────────┬────────┘
                                │
                                ▼
                       ┌────────────────┐
                       │ Writer Agent   │
                       └───────┬────────┘
                               │
                               ▼
                       ┌────────────────┐
                       │ Verifier Agent │
                       └───────┬────────┘
                               │
                               ▼
                          Final Answer
```

---

# Future Agent Ideas

Potential agents include:

```text
Verifier Agent
Browser Agent
Web Search Agent
RAG Agent
Planner Agent
Router Agent
Coder Agent
File Agent
Memory Agent
Vision Agent
Data Analysis Agent
API Agent
Database Agent
Critic Agent
Security Agent
Summarization Agent
Tool Execution Agent
```

Not all agents need to be used for every request.

The future Orchestrator should select agents dynamically.

---

# Dynamic Orchestration Goal

Current:

```text
Research
   ↓
Writer
```

Future:

```text
User Question
     ↓
Planner / Router
     ↓
Determine Needed Capabilities
     ↓
Discover Matching Agents
     ↓
Build Execution Plan
     ↓
Run Agents
     ├── sequentially
     ├── conditionally
     └── in parallel where appropriate
     ↓
Combine Results
     ↓
Writer
     ↓
Verifier
     ↓
Final Answer
```

---

# Reliability Roadmap

Planned reliability improvements:

```text
Retry logic
Exponential backoff
Circuit breakers
More specific exceptions
Graceful shutdown
Persistent task storage
Agent availability preflight
Health monitoring
Metrics
Distributed tracing
Request correlation IDs
Structured JSON logs
Better timeout configuration
Cancellation support
Rate limiting
```

---

# Answer Quality Roadmap

Planned quality improvements:

```text
Verifier Agent
Critic Agent
Source checking
Citation checking
Unsupported claim detection
Contradiction detection
Confidence handling
Uncertainty handling
Revision loops
Evidence-based generation
```

---

# Research Roadmap

Planned research capabilities:

```text
Web search
Browser access
Fresh-information retrieval
Source collection
Source ranking
Source credibility checks
Citation tracking
Research provenance
Multi-source synthesis
```

---

# RAG Roadmap

Planned RAG capabilities:

```text
PDF ingestion
DOCX ingestion
Text ingestion
Webpage ingestion
Chunking
Embeddings
Vector database
Hybrid retrieval
Metadata filtering
Re-ranking
Document permissions
Source citations
Private company knowledge
Incremental re-indexing
```

---

# Memory Roadmap

Possible future memory architecture:

```text
Conversation memory
User preferences
Task memory
Project memory
Semantic memory
Short-term working memory
Long-term searchable memory
```

Memory should be stored separately from agent logic so that specialized agents can reuse the same context.

---

# Deployment Roadmap

Possible future deployment structure:

```text
Docker
Docker Compose
Reverse proxy
HTTPS
Separate agent containers
Persistent database
Redis
Task queue
Observability
CI/CD
Cloud deployment
Horizontal scaling
```

Agents should eventually be deployable independently.

For example:

```text
research-agent.example.internal
writer-agent.example.internal
verifier-agent.example.internal
rag-agent.example.internal
```

instead of only:

```text
localhost:8001
localhost:8002
```

---

# Possible Future Persistence

Current:

```text
InMemoryTaskStore
```

Future options may include:

```text
PostgreSQL
Redis
Dedicated task store
Event database
Message queue
```

This would allow:

```text
Task recovery
Restart recovery
History
Auditing
Long-running workflows
Distributed agents
```

---

# Testing Roadmap

Current:

```text
12 tests
```

Future tests should include:

```text
Writer missing required skill
Wrong protocol binding
Invalid JSON Agent Card
HTTP 500 Agent Card
A2A timeout
A2A empty response
Groq failure
Writer failure after successful Research
Verifier PASS
Verifier FAIL
Revision loop
Maximum revision protection
Health-check failures
Integration tests
End-to-end tests
```

---

# Example Workflow

User asks:

```text
What are the differences between RAG and fine-tuning?
```

Execution:

```text
Orchestrator
    ↓
Discover Research Agent
    ↓
Research Agent
    ↓
Groq
    ↓
Research brief
    ↓
Writer Agent
    ↓
Groq
    ↓
Final explanation
    ↓
User
```

---

# Another Example

User asks:

```text
Design a beginner-friendly architecture for an AI assistant that can answer questions from private company documents.
```

The current system can:

```text
Research architecture concepts
Organize important components
Identify security considerations
Explain RAG
Describe scaling considerations
Send the research to Writer
Return a polished explanation
```

However, it does not yet inspect real company documents.

That requires the planned RAG layer.

---

# Useful Development Commands

## Compile Everything

```powershell
uv run python -m compileall core agents orchestrator tests
```

## Run Tests

```powershell
uv run pytest -v
```

## Start Research Agent

```powershell
uv run python -m agents.research.app
```

## Start Writer Agent

```powershell
uv run python -m agents.writer.app
```

## Start Orchestrator

```powershell
uv run python -m orchestrator.main
```

## Ask Directly

```powershell
uv run python -m orchestrator.main "Explain retrieval augmented generation"
```

## Show Research

```powershell
uv run python -m orchestrator.main --show-research "Explain retrieval augmented generation"
```

## Check Research Health

```powershell
Invoke-RestMethod http://127.0.0.1:8001/health
```

## Check Writer Health

```powershell
Invoke-RestMethod http://127.0.0.1:8002/health
```

## View Research Agent Card

```powershell
Invoke-RestMethod http://127.0.0.1:8001/.well-known/agent-card.json | ConvertTo-Json -Depth 10
```

## View Writer Agent Card

```powershell
Invoke-RestMethod http://127.0.0.1:8002/.well-known/agent-card.json | ConvertTo-Json -Depth 10
```

---

# Troubleshooting

## `405 Method Not Allowed`

Cause:

```text
GET /
```

was sent to an endpoint that expects:

```text
POST /
```

Solution:

Use:

```text
/health
```

or:

```text
/.well-known/agent-card.json
```

when checking an agent from a browser.

---

## `/favicon.ico 404`

This is harmless.

Browsers automatically request:

```text
/favicon.ico
```

The application does not currently define a favicon.

---

## `A2AClientTimeoutError`

Example:

```text
A2AClientTimeoutError: Client Request timed out
```

The client has already been configured with a longer read timeout.

If this continues, check:

```text
Agent server status
Groq availability
Internet connection
Model latency
Agent logs
Prompt size
```

---

## Research Agent Not Available

Check:

```powershell
Invoke-RestMethod http://127.0.0.1:8001/health
```

If unavailable:

```powershell
uv run python -m agents.research.app
```

---

## Writer Agent Not Available

Check:

```powershell
Invoke-RestMethod http://127.0.0.1:8002/health
```

If unavailable:

```powershell
uv run python -m agents.writer.app
```

---

## Missing Groq API Key

Ensure `.env` contains:

```env
GROQ_API_KEY=your_real_key_here
```

Never paste the real API key into:

```text
README.md
.env.example
Git
GitHub
chat logs intended for publication
```

---

## PowerShell Does Not Accept `&&`

Older Windows PowerShell versions do not support:

```powershell
command1 && command2
```

Use:

```powershell
command1; command2
```

instead.

---

# Development Principles

The project follows several architectural principles:

```text
Keep agents specialized
Keep LLM provider code centralized
Keep prompts separate from networking
Keep orchestration separate from agents
Use Agent Cards for discovery
Use A2A for communication
Validate agent capabilities
Avoid infinite timeouts
Add tests before adding large features
Keep secrets outside source code
Prefer modular expansion over monolithic growth
```

---

# Current Completed Milestones

```text
[✓] Python project structure
[✓] uv virtual environment
[✓] Groq integration
[✓] Central configuration
[✓] Shared async LLM layer
[✓] Research Agent
[✓] Research Agent Card
[✓] Research health endpoint
[✓] Writer Agent
[✓] Writer Agent Card
[✓] Writer health endpoint
[✓] A2A JSON-RPC communication
[✓] A2A streaming event handling
[✓] Artifact extraction
[✓] Reusable A2A client
[✓] Custom HTTP timeout configuration
[✓] Explicit Agent discovery
[✓] Protocol validation
[✓] Skill validation
[✓] Research -> Writer orchestration
[✓] Interactive CLI
[✓] Direct CLI questions
[✓] --show-research mode
[✓] Structured logging
[✓] Workflow timing
[✓] Health checks
[✓] Error handling foundation
[✓] Mocked automated tests
[✓] 12 tests passing
```

---

# Immediate Next Milestone

The next major feature is planned to be:

```text
Verifier Agent
```

After implementation:

```text
Research
   ↓
Writer
   ↓
Verifier
   ↓
Final Answer
```

After revision-loop support:

```text
Research
   ↓
Writer
   ↓
Verifier
   │
   ├── PASS ───────────────► Final Answer
   │
   └── FAIL
        ↓
     Feedback
        ↓
     Writer Revision
        ↓
     Verifier
```

This is the next step toward improving answer reliability rather than simply adding more infrastructure.

---

# Long-Term Goal

The goal is to evolve this prototype into a powerful modular AI-agent platform where specialized agents can collaborate over A2A.

Eventually the system should be capable of:

```text
Researching
Browsing the web
Retrieving private knowledge
Reading documents
Using RAG
Writing
Fact-checking
Verifying
Coding
Using tools
Calling APIs
Working with files
Analyzing data
Planning tasks
Remembering useful context
Routing work dynamically
Running agents in parallel
Recovering from failures
Producing source-grounded answers
```

Instead of relying on one monolithic AI process, specialized agents will work together through standardized A2A communication.

---

# Version

```text
Project: A2A Multi-Agent System
Version: 0.1.0
Stage: Development Prototype

Current Agents:
- Research Agent
- Writer Agent

Current Workflow:
Research -> Writer

Current Test Status:
12 passed

Next Planned Agent:
Verifier Agent
```
