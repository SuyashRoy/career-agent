# Resume Matching Agent

Semantic job matching powered by BGE-large embeddings and FAISS vector search. Upload your resume PDF, point it at a directory of job descriptions (or a live URL), and get back the top-K most relevant positions ranked by a composite scoring system — in seconds, running entirely locally with no paid API calls.

## What It Does

The agent takes a resume PDF and any source of job descriptions, then returns a ranked list like this:

```
======================================================
  RESUME MATCHING RESULTS — 5 match(es)
======================================================

  #1  ML Engineer
       Composite Score:  0.8921
       ├── Semantic:     0.8743
       ├── Experience:   1.0000
       ├── Location:     1.0000
       └── Preference:   0.8500
       URL: https://example.com/jobs/ml-engineer

  #2  AI Engineer
       Composite Score:  0.8614
       ...

  #5  Marketing Manager
       Composite Score:  0.4823
       ├── Semantic:     0.3201
       ...
```

Relevant roles rank at the top. Irrelevant roles (Marketing Manager, Frontend Developer) fall to the bottom based on semantic distance from the resume's content — no keyword lists, no manual tagging.

## Why It's Hard

Job matching sounds simple until you think about what "relevant" really means. A resume that says "built recommendation systems with PyTorch" should match "deep learning engineer for personalization" even though those phrases share zero keywords. Keyword matching fails entirely. Simple regex breaks on synonyms. The only approach that works at this semantic level is dense vector embeddings — converting both the resume and each JD into a high-dimensional vector and measuring the angle between them.

The secondary challenge is that job source formats are wildly inconsistent. The same agent needs to accept a URL, a folder of `.txt` files, a raw string, a dict from the Opportunity Agent, or nothing at all (defaulting to the test directory) — without the caller needing to know which path it took.

## Architecture

```
Resume PDF + Job Source (URL / files / dict / text)
        │                       │
        ▼                       ▼
┌───────────────┐    ┌──────────────────────────┐
│ resume_parser │    │  job_description_loader   │
│               │    │                           │
│ PyMuPDF →     │    │  Path A: URL → requests   │
│ full_text     │    │           + BeautifulSoup  │
│ + sections    │    │  Path B: .txt / .json files│
│ dict          │    │  Path C: dict / raw text   │
└──────┬────────┘    └──────────────┬────────────┘
       │                            │
       ▼                            ▼
┌──────────────────────────────────────────────────┐
│               embedding_engine                   │
│                                                  │
│  BGE-large-en-v1.5 (BAAI/bge-large-en-v1.5)    │
│  Resume: is_query=True  → adds query prefix      │
│  JDs:    is_query=False → plain encoding         │
│  normalize_embeddings=True  (unit vectors)       │
└────────────────────┬─────────────────────────────┘
                     │  (1024-dim float32 arrays)
        ┌────────────┴────────────┐
        ▼                         ▼
  resume_embedding          jd_embeddings
  shape: (1, 1024)          shape: (N, 1024)
        └────────────┬────────────┘
                     ▼
          ┌──────────────────┐
          │     matcher      │
          │                  │
          │  FAISS           │
          │  IndexFlatIP     │
          │  inner product   │
          │  on L2-normalized│
          │  = cosine sim    │
          │  → top-K results │
          └────────┬─────────┘
                   │
                   ▼
        ┌──────────────────────┐
        │   job_ranking_engine │
        │                      │
        │  Composite score:    │
        │  0.50 × semantic     │
        │  0.20 × experience   │
        │  0.15 × location     │
        │  0.15 × preference   │
        └──────────┬───────────┘
                   │
                   ▼
          Ranked list[dict]
```

## Tech Stack

| Component | Technology | Why |
|---|---|---|
| Embeddings | BGE-large-en-v1.5 | Free, local, top MTEB retrieval benchmark performance |
| Vector search | FAISS IndexFlatIP | In-memory, sub-millisecond, zero infra for demo scale |
| Resume parsing | PyMuPDF (fitz) | Lightweight PDF-to-text, handles multi-page resumes |
| JD loading | requests + BeautifulSoup | Flexible multi-source loader (URL, file, raw text) |
| Similarity | Cosine via inner product | Standard for normalized dense retrieval vectors |
| Ranking | Custom composite scorer | Tunable multi-signal weighting beyond pure semantics |

## Key Design Decisions

**Why BGE-large over OpenAI embeddings?**
BGE-large-en-v1.5 from BAAI ranks competitively on the MTEB retrieval benchmark while being free and running fully locally. No API costs, no rate limits, no data leaving the machine. For a resume-matching use case where the dataset fits in memory, this is the clear choice.

**Why cosine similarity via FAISS IndexFlatIP?**
All embeddings are L2-normalized to unit vectors before indexing. On unit vectors, inner product equals cosine similarity. `IndexFlatIP` (inner product) is therefore exact cosine search with no approximation error — important for a small-to-medium corpus where precision matters more than speed.

**Why a composite score instead of pure semantic similarity?**
Semantic similarity measures relevance of the resume text to the JD text, but not fit. A candidate with 1 year of experience might have a high semantic similarity score for a 7+ year role. The composite layer adds: years-of-experience alignment (does the candidate meet the floor?), location compatibility (is the job in a preferred city, or remote?), and explicit skill keyword overlap (as a complement to the semantic score, not a replacement).

**Why a universal `load_job_descriptions()` entry point?**
The agent is designed to work both standalone (reading from test files) and wired into the Opportunity Agent (receiving a dict with `company_name` and `open_position_url`). Rather than having two separate code paths, a single entry point detects the input format and routes accordingly — the caller doesn't need to know which path was taken.

**Why the BGE query prefix?**
BGE-large is trained with asymmetric retrieval in mind. For queries (the resume), prepending `"Represent this sentence: "` improves retrieval recall by signaling to the model that this vector should be used for search, not indexing. Job descriptions are indexed without the prefix. This is the recommended inference pattern from the BAAI documentation.

## Setup

```bash
# From the repo root
pip install -r requirements.txt

# BGE-large downloads automatically on first run (~1.3 GB)
# No additional setup needed
```

## Usage

**Standalone pipeline:**
```bash
python -m resume_matching_agent.pipeline path/to/resume.pdf
# Loads JDs from resume_matching_agent/test_data/job_descriptions/

python -m resume_matching_agent.pipeline resume.pdf path/to/jd_folder/
```

**As a module:**
```python
from resume_matching_agent.pipeline import match_resume_to_jobs, print_results

results = match_resume_to_jobs(
    resume_pdf_path="path/to/resume.pdf",
    job_source=None,                            # None = load from test_data/
    top_k=5,
    candidate_extras={
        "years_experience": 3,
        "preferred_locations": ["Remote", "San Francisco"],
    },
)
print_results(results)
```

**Accepting Opportunity Agent output directly:**
```python
from opportunity_agent.app import run_pipeline
from resume_matching_agent.pipeline import match_resume_to_jobs

opp_result = run_pipeline("https://www.linkedin.com/jobs/view/...")
results = match_resume_to_jobs(
    resume_pdf_path="resume.pdf",
    job_source=opp_result.model_dump(),  # Opportunity Agent dict format
)
```

## Evaluation

Target metrics: Precision@5 ≥ 0.6 · Recall@10 ≥ 0.7 · Mean cosine similarity of top match ≥ 0.75

**Test setup:** 3 resumes × 6 JDs (3 relevant: ML Engineer, Data Scientist, AI Engineer · 2 irrelevant: Marketing Manager, Frontend Developer · 1 ambiguous: Social Media Manager)

**Expected behavior:** All three relevant JDs should rank in the top 3 for a technical resume. The irrelevant JDs should rank 4th and 5th, with composite scores at least 0.15 below the top match.

## Project Structure

```
resume_matching_agent/
├── agents/
│   ├── embedding_engine.py       # BGE-large model wrapper with lazy loading
│   ├── job_description_loader.py # Universal multi-source JD loader
│   ├── matcher.py                # FAISS index build + cosine search
│   ├── job_ranking_engine.py     # Composite multi-signal ranking
│   └── resume_parser.py          # PyMuPDF PDF parser + section extractor
├── pipeline.py                   # Public API: match_resume_to_jobs()
├── test_data/
│   ├── resumes/                  # Sample resume PDFs
│   └── job_descriptions/         # Sample JD .txt files
└── README.md
```

## Part of CareerAgent

This module is one component of [CareerAgent](../README.md), an agentic career intelligence platform. Its output feeds directly into the [Resume Tailor Agent](../resume_tailor_agent/README.md), which generates per-job ATS scores, critiques, and improvement suggestions for the top-K matches returned here.
