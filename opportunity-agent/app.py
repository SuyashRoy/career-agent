"""
Opportunity Discovery Agent — LangGraph workflow
LinkedIn URL → company name + career page URL + open position URL
"""
from typing import List

from dotenv import load_dotenv
from langgraph.graph import StateGraph, END

from agents.career_page_finder import find_career_page
from agents.job_extractor import extract_job_url
from agents.linkedin_extractor import extract_company_info
from models.schemas import JobSourceOutput, JobSourceState

load_dotenv()


# ── LangGraph nodes ────────────────────────────────────────────────────────────

def extract_linkedin_node(state: JobSourceState) -> dict:
    try:
        company_name, company_website = extract_company_info(state.linkedin_url)
        return {"company_name": company_name, "company_website": company_website}
    except Exception as e:
        return {"errors": state.errors + [f"linkedin_extractor: {e}"]}


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


# ── Graph definition ───────────────────────────────────────────────────────────

_graph = StateGraph(JobSourceState)
_graph.add_node("extract_linkedin", extract_linkedin_node)
_graph.add_node("find_career", find_career_node)
_graph.add_node("extract_job", extract_job_node)
_graph.add_edge("extract_linkedin", "find_career")
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
        "https://www.linkedin.com/jobs/view/4290309149/",
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
