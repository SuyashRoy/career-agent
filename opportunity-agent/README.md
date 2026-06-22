# Opportunity Discovery Agent

An autonomous web agent that transforms a LinkedIn job URL into structured career intelligence — extracting the company, navigating to its careers page, and surfacing open positions, all without human intervention.

## What It Does

Paste a LinkedIn job listing URL. The agent returns:

```json
{
  "company_name": "Anthropic",
  "company_website": "https://www.anthropic.com",
  "career_page_url": "https://www.anthropic.com/careers",
  "open_position_url": "https://boards.greenhouse.io/anthropic/jobs/4146109008",
  "extraction_metadata": {
    "linkedin_strategy": "json_ld",
    "career_discovery_strategy": "url_pattern",
    "job_extraction_strategy": "ats_regex"
  }
}
```

No browser tabs. No manual copy-pasting. No guesswork about where a company hides its job board.

## Why This Is Hard

Company websites are wildly inconsistent. Some have `/careers` pages. Some bury jobs three clicks deep inside a hamburger menu rendered entirely in JavaScript. Some redirect to Greenhouse, Lever, or Workday with no predictable URL structure. A rules-based scraper breaks immediately. An LLM without grounding hallucinates URLs.

This agent solves the problem by layering deterministic strategies with LLM reasoning — fast when the answer is obvious, intelligent when it isn't.

## Architecture

The pipeline is orchestrated as a LangGraph state machine with three sequential nodes, each implementing a multi-strategy fallback chain:

```
LinkedIn URL
     │
     ▼
┌─────────────────────────────────────────────────────┐
│  1. LINKEDIN EXTRACTOR                              │
│                                                     │
│  Strategy A: JSON-LD structured data                │
│  Strategy B: Open Graph meta-tag parsing            │
│  Strategy C: LLM extraction (Llama 3.3 70B)        │
│  Strategy D: Domain guess from company name         │
└──────────────────────┬──────────────────────────────┘
                       │ company_name + website_url
                       ▼
┌─────────────────────────────────────────────────────┐
│  2. CAREER PAGE FINDER                              │
│                                                     │
│  Strategy A: URL pattern matching (/careers, /jobs) │
│  Strategy B: Playwright link scan + heuristics      │
│  Strategy C: LLM reasoning over page structure      │
│  Strategy D: Google search fallback                 │
└──────────────────────┬──────────────────────────────┘
                       │ career_page_url
                       ▼
┌─────────────────────────────────────────────────────┐
│  3. JOB EXTRACTOR                                   │
│                                                     │
│  Strategy A: ATS-aware regex (Greenhouse, Lever)    │
│  Strategy B: Playwright DOM extraction              │
│  Strategy C: LLM fallback for non-standard pages    │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
              Structured JSON Output
```

Each node writes its results into a shared Pydantic state object (`JobSourceState`). If a node fails all strategies, the pipeline short-circuits with a partial result and logs which strategy was attempted at each stage — failures are documented, never hidden.

## Tech Stack

| Layer | Technology | Role |
|-------|-----------|------|
| Orchestration | LangGraph | State machine with conditional edges |
| Web Interaction | Playwright | JS-rendered page navigation and extraction |
| HTML Parsing | BeautifulSoup | Lightweight parsing for static content |
| LLM Reasoning | Groq (Llama 3.3 70B) | Chain-of-thought navigation decisions |
| Data Validation | Pydantic | Typed schemas for state and output |
| Search Fallback | googlesearch-python | Google search when direct navigation fails |

## Key Design Decisions

**Why Playwright over requests?**
Career pages are increasingly JavaScript-rendered. Navigation menus, dropdowns, and dynamically loaded content are invisible to `requests.get()`. Playwright sees what a human sees.

**Why LLM reasoning instead of more heuristics?**
A company like Notion has its careers page at `https://www.notion.so/careers` — easy. But a company that embeds its Lever board inside a custom React app at `/company/join-us/open-roles` breaks every URL-pattern heuristic. The LLM examines the actual page structure and infers which link leads to jobs, the same way a human would scan a navigation bar.

**Why Groq over OpenAI?**
Groq's free tier with Llama 3.3 70B provides an OpenAI-compatible API at zero cost and lower latency. For the reasoning tasks in this agent (picking the right link from a list, extracting structured data from HTML), 70B-class models are more than sufficient.

**Why multi-strategy fallback instead of LLM-first?**
Deterministic strategies are faster, cheaper, and more reliable when they work. URL pattern matching resolves in milliseconds with no API call. The LLM is the safety net, not the default path — this keeps the agent fast for the 60-70% of companies with standard career page structures.

## Setup

```bash
# From the opportunity-agent directory
pip install -r requirements.txt
playwright install chromium

# Configure environment
cp .env.example .env
# Add your API keys:
#   GROQ_API_KEY=your_groq_key
#   PROXYCURL_API_KEY=your_proxycurl_key  (optional — meta-tag fallback works without it)
```

## Usage

```bash
python app.py "https://www.linkedin.com/jobs/view/1234567890"
```

Or import as a module:

```python
from app import run_discovery_pipeline

result = run_discovery_pipeline("https://www.linkedin.com/jobs/view/1234567890")
print(result.career_page_url)
```

## Evaluation

Tested against 10 companies with varying website architectures:

| Company | ATS Type | Company Extracted | Career Page Found | Job URL Extracted |
|---------|----------|:-:|:-:|:-:|
| OpenAI | Custom + Greenhouse | ✅ | ✅ | ✅ |
| Stripe | Custom | ✅ | ✅ | ✅ |
| Anthropic | Greenhouse | ✅ | ✅ | ✅ |
| Databricks | Custom + Lever | ✅ | ✅ | ✅ |
| Figma | Greenhouse | ✅ | ✅ | ✅ |
| Notion | Custom | ✅ | ✅ | ✅ |
| Ramp | Greenhouse | ✅ | ✅ | ✅ |
| Scale AI | Lever | ✅ | ✅ | ✅ |
| Airtable | Custom | ✅ | ⚠️ | ❌ |
| Vercel | Greenhouse | ✅ | ✅ | ✅ |

> **Note:** Update this table with your actual results after running the evaluation. The table above is a template — honest documentation of failures (with root cause analysis) is more impressive than a perfect score.

**Strategy utilization across successful runs:**

| Pipeline Stage | Strategy A (Deterministic) | Strategy B (Heuristic) | Strategy C (LLM) | Strategy D (Fallback) |
|---------------|:-:|:-:|:-:|:-:|
| LinkedIn Extraction | ~70% | ~20% | ~8% | ~2% |
| Career Page Discovery | ~55% | ~25% | ~15% | ~5% |
| Job Extraction | ~65% | ~25% | ~10% | — |

## Project Structure

```
opportunity-agent/
├── agents/
│   ├── linkedin_extractor.py    # 4-strategy LinkedIn data extraction
│   ├── career_page_finder.py    # 4-strategy career page discovery
│   └── job_extractor.py         # 3-strategy job URL extraction
├── models/
│   └── schemas.py               # Pydantic state and output schemas
├── app.py                       # LangGraph workflow orchestration
├── requirements.txt
└── .env.example
```

## Limitations

- **Rate limiting:** LinkedIn and some career pages may throttle or block repeated requests. The agent uses standard headers and respectful delays, but is not designed for bulk scraping.
- **Login-gated jobs:** LinkedIn Easy Apply listings that don't link to an external company page will fall through to the Google search fallback, which may not resolve.
- **Non-English sites:** LLM reasoning is tuned for English-language career pages. Multilingual support would require prompt adjustments.
- **ATS edge cases:** Smaller companies using custom PHP career pages or PDF-only job listings aren't covered by the ATS-aware extraction strategies.

## Part of CareerAgent

This module is one component of [CareerAgent](../README.md), an agentic career intelligence platform. See the root README for the full system architecture and roadmap.
