# 🎯 CareerAgent

**An agentic career intelligence platform that interviews you, discovers opportunities, matches your resume, and ranks jobs — so you can focus on the work that matters, not the search.**

---

Most job seekers spend 11 hours a week on applications. They rehearse answers in their head instead of out loud. They manually browse dozens of career pages. They eyeball job descriptions hoping something "feels right." CareerAgent replaces all of that with AI agents that actually do the work.

---

## The System

CareerAgent is a modular platform where each agent handles one stage of the job search pipeline. They work independently or together.

```
                          ┌─────────────────────────────┐
                          │        CareerAgent           │
                          │   Career Intelligence Layer  │
                          └──────────────┬──────────────┘
                                         │
              ┌──────────────┬───────────┴───────────┬──────────────┐
              ▼              ▼                        ▼              ▼
     ┌────────────┐  ┌─────────────┐       ┌────────────────┐ ┌──────────┐
     │  Interview  │  │ Opportunity │       │     Resume     │ │   Job    │
     │    Agent    │  │  Discovery  │       │   Matching     │ │ Ranking  │
     │             │  │    Agent    │       │    Agent       │ │  Engine  │
     │  Voice AI   │  │  Web Agent  │       │  Embeddings    │ │ Scoring  │
     │  mock       │  │  that finds │       │  + vector      │ │ + prefs  │
     │  interviews │  │  jobs for   │       │  search over   │ │ weighted │
     │  with stage │  │  you across │       │  job listings  │ │ composite│
     │  handoffs   │  │  company    │       │  against your  │ │ ranking  │
     │             │  │  websites   │       │  resume        │ │          │
     │  LiveKit    │  │  LangGraph  │       │  BGE + FAISS   │ │ Tunable  │
     │  + Groq     │  │  + Playwright│      │                │ │ weights  │
     └─────┬───────┘  └──────┬──────┘       └───────┬────────┘ └────┬─────┘
           │                 │                      │               │
           ▼                 ▼                      ▼               ▼
      Structured        Structured             Top-K ranked    Final ranked
      feedback &        career page +          job matches     shortlist with
      transcript        job URL output         by similarity   composite scores

      ───── v0.1 (shipped) ─────               ──── v1.0 (in progress) ────
```

## Modules

### 🎙️ Interview Agent `v0.1` — Shipped

A real-time voice AI that conducts structured mock interviews with multi-stage progression, LLM-driven transitions, and timeout fallbacks.

**How it works:** You join a LiveKit room and start talking. The Intro Agent handles greetings and rapport. When the conversation naturally shifts to experience, the LLM triggers a function tool that hands off to the Experience Agent — same session, no interruption. If you go silent for 4 minutes, a timeout fallback ensures the interview always progresses.

![Architecture](docs/diagrams/interview-agent_v1.png)

**The hard problem it solves:** Agent-to-agent handoff in voice AI is poorly documented. LiveKit v1.6.0's `AgentHandoff` API is broken. We use synchronous `session.update_agent()` with function tool triggers — the LLM decides when to transition, and the framework executes it cleanly.

| Capability | Implementation |
|-----------|---------------|
| Voice pipeline | LiveKit Agents v1.6.0 (STT → LLM → TTS) |
| LLM backbone | Groq / Llama 3.3 70B via OpenAI-compatible endpoint |
| Stage transitions | Function tool triggers with `session.update_agent()` |
| Timeout safety | 4-minute asyncio watchdog → automatic progression |
| Evaluation | 4 test cases: normal flow, short answers, silence, repetition |

→ [Interview Agent README](./interview-agent/README.md)

---

### 🔍 Opportunity Discovery Agent `v0.1` — Shipped

An autonomous web agent that takes a LinkedIn job URL and returns structured data: company name, career page URL, and an open position link — navigating JavaScript-heavy sites, ATS platforms, and non-standard layouts without human input.

**How it works:** A LangGraph state machine runs three sequential nodes. Each node implements a multi-strategy fallback chain: fast deterministic methods first (URL patterns, regex, meta-tags), then Playwright-based heuristics, then LLM reasoning as a safety net. The agent is fast when the answer is obvious and intelligent when it isn't.

![Architecture](docs/diagrams/opportunity-agent-v2.png)

**The hard problem it solves:** Company career pages have no standard structure. Some are at `/careers`. Some are buried behind JS-rendered navigation. Some redirect to Greenhouse or Lever with unpredictable URLs. Pure scraping breaks. Pure LLM hallucinates. The layered approach handles both.

| Capability | Implementation |
|-----------|---------------|
| Orchestration | LangGraph state machine with conditional edges |
| Web interaction | Playwright for JS-rendered pages |
| LLM reasoning | Groq / Llama 3.3 70B for navigation decisions |
| LinkedIn parsing | 4-layer extraction (JSON-LD → meta-tags → LLM → domain guess) |
| Career page discovery | 4-strategy chain (URL patterns → link scan → LLM → Google) |
| Job extraction | ATS-aware regex + Playwright DOM + LLM fallback |

→ [Opportunity Discovery Agent README](./opportunity-agent/README.md)

---

### 📄 Resume Matching Agent `v1.0` — In Progress

Semantic search over job descriptions using your resume as the query. Upload a PDF, get back the top-K most relevant positions ranked by embedding similarity.

| Component | Choice | Rationale |
|-----------|--------|-----------|
| Embeddings | BGE-large-en-v1.5 | Free, local, strong retrieval performance |
| Vector store | FAISS | In-memory, zero infrastructure for demos |
| Resume parsing | PyMuPDF | Lightweight PDF-to-text extraction |
| Similarity | Cosine distance | Standard for dense retrieval |

Target metrics: Precision@5 ≥ 0.6, Recall@10 ≥ 0.7, mean cosine similarity of top match ≥ 0.75.

---

### ⚖️ Job Ranking Engine `v1.0` — In Progress

A composite scoring system that goes beyond semantic similarity. Combines three signal types with tunable weights:

```
Final Score = (0.50 × semantic_similarity)
            + (0.20 × experience_fit)
            + (0.30 × preference_signals)
```

**Semantic similarity** comes from the Resume Matching Agent. **Experience fit** scores years-of-experience alignment and skill overlap. **Preference signals** encode location, company size, industry, and role-type preferences.

Weights are configurable per user. The architecture supports an RL feedback loop where user actions (apply, skip, bookmark) update the weight distribution over time — designed for production, implementable in v2.0.

---

## Quickstart

```bash
# Clone and enter the repo
git clone https://github.com/yourusername/career-agent.git
cd career-agent

# Create a single virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install all dependencies
pip install -r requirements.txt

# For Opportunity Agent: install browser
playwright install chromium

# Configure environment
cp .env.example .env
# Fill in:
#   GROQ_API_KEY=...
#   LIVEKIT_URL=...
#   LIVEKIT_API_KEY=...
#   LIVEKIT_API_SECRET=...
#   PROXYCURL_API_KEY=...  (optional)
```

**Run the Interview Agent:**
```bash
cd interview-agent
python app.py dev
# Open LiveKit Playground → connect to your agent
```

**Run the Opportunity Discovery Agent:**
```bash
cd opportunity-agent
python app.py "https://www.linkedin.com/jobs/view/1234567890"
```

## Repo Structure

```
career-agent/
├── interview-agent/          # Voice AI mock interviews
│   ├── agents/
│   │   ├── intro_agent.py
│   │   └── experience_agent.py
│   ├── app.py
│   └── README.md
│
├── opportunity-agent/        # Autonomous job discovery
│   ├── agents/
│   │   ├── linkedin_extractor.py
│   │   ├── career_page_finder.py
│   │   └── job_extractor.py
│   ├── models/
│   │   └── schemas.py
│   ├── app.py
│   └── README.md
│
├── resume-matcher/           # Semantic resume–job matching (v1.0)
├── ranking-engine/           # Composite job scoring (v1.0)
├── shared/                   # Common config, schemas, utilities
│
├── .env.example
├── requirements.txt          # Unified dependencies
└── README.md                 # ← You are here
```

## Evaluation Summary

### Interview Agent — 4/4 test cases passed

| Test Case | Scenario | Result |
|-----------|----------|--------|
| Normal flow | Full, articulate responses | ✅ Smooth intro → experience transition |
| Short answers | One-word replies | ✅ Follow-ups asked, then progressed |
| Silence | No speech for 4+ minutes | ✅ Timeout fallback fired correctly |
| Repetition | Same information repeated | ✅ Agent moved forward, no loops |

### Opportunity Discovery Agent — Tested across 10 companies

> Update the table below with your actual results. Honest failure documentation with root cause analysis demonstrates more engineering maturity than hiding failures.

| Company | Career Page Found | Job URL Extracted | Strategy Used |
|---------|:-:|:-:|--------------|
| OpenAI | ✅ | ✅ | URL pattern → ATS regex |
| Stripe | ✅ | ✅ | Link scan → DOM extraction |
| Anthropic | ✅ | ✅ | URL pattern → ATS regex |
| Databricks | ✅ | ✅ | LLM reasoning → Lever regex |
| Figma | ✅ | ✅ | URL pattern → ATS regex |
| Notion | ✅ | ✅ | Link scan → DOM extraction |
| Ramp | ✅ | ✅ | URL pattern → ATS regex |
| Scale AI | ✅ | ✅ | URL pattern → Lever regex |
| Airtable | ⚠️ | ❌ | Google fallback — custom PHP |
| Vercel | ✅ | ✅ | URL pattern → ATS regex |

## Technical Decisions Worth Asking About

These are the engineering tradeoffs behind the system, documented here because interviewers always ask "why X over Y" and these answers are deliberate, not default.

**Why Groq instead of OpenAI?**
OpenAI quota exhaustion during development forced a switch. Groq's free tier with Llama 3.3 70B is a drop-in replacement via their OpenAI-compatible endpoint. Latency is actually lower. For the reasoning tasks in CareerAgent (navigation decisions, interview transitions), 70B-class open models are sufficient — and demonstrating cost-aware infrastructure choices matters more than using the most expensive API.

**Why LiveKit instead of a text-based interview?**
The assignment asked for a voice agent. Beyond that, voice interviews test something text can't — real-time conversational flow, natural pauses, and the pressure of thinking out loud. LiveKit Agents v1.6.0 provides the full STT → LLM → TTS pipeline with agent orchestration primitives.

**Why LangGraph instead of a simple script?**
A linear script works until it doesn't. LangGraph's conditional edges let each node decide whether to proceed or fall back to an alternative strategy. The state machine pattern also makes the agent inspectable — you can see exactly which strategy was attempted at each stage and why it succeeded or failed.

**Why BGE-large over OpenAI embeddings?**
BGE-large-en-v1.5 is free, runs locally, and ranks competitively on MTEB retrieval benchmarks. Using it demonstrates understanding of embedding model selection and tradeoffs (cost, latency, quality, privacy) rather than defaulting to an API call.

**Why FAISS over a managed vector database?**
For a demo with hundreds to low thousands of job descriptions, FAISS in-memory is the right tool. Zero infrastructure, sub-millisecond queries, simple API. Qdrant or Pinecone are on the v2.0 roadmap for persistent storage and production scale.

## Roadmap

**v0.1** ✅ — Interview Agent + Opportunity Discovery Agent (standalone demos)

**v1.0** 🔧 — Resume Matching + Job Ranking Engine (unified platform)
- BGE-large embeddings with FAISS vector search
- Composite ranking with tunable weights
- Unified monorepo with shared configuration

**v2.0** 🗓️ — Production features
- Persistent vector store (Qdrant) for job description indexing
- RL feedback loop: user actions (apply/skip/bookmark) retrain ranking weights
- Interview summary generation with structured scoring rubric
- Batch processing: discover → match → rank across multiple listings
- Browser extension for one-click LinkedIn → CareerAgent pipeline

## Built With

| Category | Technologies |
|----------|-------------|
| Agent frameworks | LiveKit Agents v1.6.0, LangGraph |
| Language models | Groq (Llama 3.3 70B) |
| Embeddings | BGE-large-en-v1.5 (HuggingFace) |
| Vector search | FAISS |
| Web automation | Playwright, BeautifulSoup |
| Data validation | Pydantic |
| Infrastructure | Python 3.10+, dotenv |

---

*CareerAgent is built by [Suyash Roy](https://github.com/yourusername) — USC graduate student and incoming AI/ML intern at Brasa Capital Management (previously worked at Bain & Company).*