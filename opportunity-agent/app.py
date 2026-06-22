"""
Opportunity Discovery Agent — LangGraph workflow
LinkedIn URL → company name + career page URL + open position URL
"""
import sys
from pathlib import Path
from typing import List

# Add career-agent/ to path so shared/ is importable when running from this directory
_REPO_ROOT = Path(__file__).parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from langgraph.graph import StateGraph, END

from agents.career_page_finder import find_career_page, _google_search_career_page
from agents.job_extractor import extract_job_url
from agents.linkedin_extractor import extract_company_info
from models.schemas import JobSourceOutput, JobSourceState


# ── LangGraph nodes ────────────────────────────────────────────────────────────

def extract_linkedin_node(state: JobSourceState) -> dict:
    try:
        company_name, company_website = extract_company_info(state.linkedin_url)
        return {"company_name": company_name, "company_website": company_website}
    except Exception as e:
        return {"errors": state.errors + [f"linkedin_extractor: {e}"]}


def search_website_node(state: JobSourceState) -> dict:
    """Fallback: when LinkedIn extraction found company name but no website,
    try Google to find the career page directly."""
    try:
        career_url = _google_search_career_page(state.company_name)
        return {"career_page_url": career_url}
    except Exception as e:
        return {"errors": state.errors + [f"search_website: {e}"]}


def find_career_node(state: JobSourceState) -> dict:
    try:
        career_url = find_career_page(state.company_name, state.company_website)
        return {"career_page_url": career_url}
    except Exception as e:
        return {"errors": state.errors + [f"career_page_finder: {e}"]}


def extract_job_node(state: JobSourceState) -> dict:
    try:
        job_url = extract_job_url(state.career_page_url)
        return {"open_position_url": job_url}
    except Exception as e:
        return {"errors": state.errors + [f"job_extractor: {e}"]}


# ── Routing ────────────────────────────────────────────────────────────────────

def _route_after_linkedin(state: JobSourceState) -> str:
    if state.company_website:
        return "find_career"
    elif state.company_name:
        return "search_website"  # no website found — try Google directly
    else:
        return END  # total extraction failure


# ── Graph definition ───────────────────────────────────────────────────────────

_graph = StateGraph(JobSourceState)
_graph.add_node("extract_linkedin", extract_linkedin_node)
_graph.add_node("search_website", search_website_node)
_graph.add_node("find_career", find_career_node)
_graph.add_node("extract_job", extract_job_node)
_graph.add_conditional_edges("extract_linkedin", _route_after_linkedin)
_graph.add_edge("search_website", "extract_job")  # skip find_career — Google gave us the career URL
_graph.add_edge("find_career", "extract_job")
_graph.add_edge("extract_job", END)
_graph.set_entry_point("extract_linkedin")
workflow = _graph.compile()


# ── Public API ─────────────────────────────────────────────────────────────────

def run_pipeline(linkedin_url: str) -> JobSourceOutput:
    """Run the full discovery pipeline for one LinkedIn job URL."""
    initial_state = JobSourceState(linkedin_url=linkedin_url)
    result = workflow.invoke(initial_state)
    return JobSourceOutput(
        company_name=result["company_name"],
        career_page_url=result["career_page_url"],
        open_position_url=result["open_position_url"],
    )


def run_pipeline_batch(linkedin_urls: List[str]) -> List[JobSourceOutput]:
    return [run_pipeline(url) for url in linkedin_urls]


# ── Standalone demo ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    test_urls = [
        "https://www.linkedin.com/jobs/view/4407396152/",
        "https://www.linkedin.com/jobs/view/4428315173/",
        "https://www.linkedin.com/jobs/view/4417327642/",
        "https://www.linkedin.com/jobs/view/4402828508/",
        "https://www.linkedin.com/jobs/view/4322163827/",
    ]

    print("=" * 60)
    print("Opportunity Discovery Agent — Pipeline Demo")
    print("=" * 60)

    for url in test_urls:
        print(f"\nInput:  {url}")
        result = run_pipeline(url)
        print(f"Company:     {result.company_name}")
        print(f"Career page: {result.career_page_url}")
        print(f"Job URL:     {result.open_position_url}")
        print("-" * 60)
