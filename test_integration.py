"""Integration test: Opportunity Agent → Resume Matching Agent."""

import sys
import logging
# from opportunity-agent.agents import JobSourceOutput

logging.basicConfig(level=logging.INFO, format="%(message)s")

# Simulate what the Opportunity Agent returns
# Replace with actual OD Agent call once verified
opportunity_agent_output = [
    {
        "company_name": "Anthropic",
        "company_website": "https://anthropic.com",
        "open_position_url": "https://boards.greenhouse.io/anthropic"
    },
    # Add more companies as needed
]

# Test 1: URL scraping path
from resume_matching_agent.agents.job_description_loader import load_job_descriptions

print("=" * 60)
print("TEST 1: URL scraping from Opportunity Agent output")
print("=" * 60)

for company in opportunity_agent_output:
    print(f"\nCompany: {company['company_name']}")
    try:
        jds = load_job_descriptions(company)
        print(f"  Scraped {len(jds)} JD(s)")
        for jd in jds:
            print(f"    - {jd['title'][:60]}...")
    except Exception as e:
        print(f"  Failed: {e}")

# Test 2: Full pipeline with scraped JDs
print("\n" + "=" * 60)
print("TEST 2: Full pipeline with OD Agent output")
print("=" * 60)

from resume_matching_agent.pipeline import match_resume_to_jobs, print_results

results = match_resume_to_jobs(
    resume_pdf_path="resume-matching-agent/test_data/resumes/Resume_AI_Fall_26.pdf",
    job_source=opportunity_agent_output[0],  # Single company dict
    top_k=5,
    candidate_extras={
        "years_experience": 2,
        "preferred_locations": ["Remote", "Los Angeles", "San Francisco"],
    },
)

print_results(results)