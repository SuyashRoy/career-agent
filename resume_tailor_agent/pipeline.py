"""Resume Tailor Agent — end-to-end pipeline.

Takes a resume PDF and matched jobs from the Resume Matching Agent, then runs
ATS scoring + LLM critique + LLM suggestions for each of the top-K jobs,
returning a structured per-job tailoring report.

Usage (chained from Resume Matching Agent):
    from resume_matching_agent.pipeline import match_resume_to_jobs
    from resume_tailor_agent.pipeline import tailor_resume, print_all_reports

    matches = match_resume_to_jobs(resume_pdf_path, job_source)
    reports = tailor_resume(resume_pdf_path, matched_jobs=matches, top_k=3)
    print_all_reports(reports)

Usage (standalone with test data):
    python -m resume_tailor_agent.pipeline path/to/resume.pdf
"""

import logging
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).parent.parent  # career-agent/
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from resume_matching_agent.agents.resume_parser import parse_resume
from resume_tailor_agent.agents.ats_scorer import score_resume
from resume_tailor_agent.agents.critique_engine import critique_resume
from resume_tailor_agent.agents.suggestion_generator import generate_suggestions

logger = logging.getLogger(__name__)


def tailor_resume(
    resume_pdf_path: str,
    matched_jobs: list[dict],
    top_k: int = 3,
) -> list[dict]:
    """Generate per-job tailoring reports for the top-K matched jobs.

    Args:
        resume_pdf_path: Path to the candidate's resume PDF.
        matched_jobs: list[dict] from match_resume_to_jobs(). Each dict must
                      have a 'job' key containing the full JD dict with 'description'.
        top_k: Number of top jobs to generate reports for.

    Returns:
        list[dict], one per job:
            job_title (str), job_url (str), rank_score (float),
            ats_score (int 0-100), ats_grade (str A-F), ats_breakdown (dict),
            critiques (list[dict]), suggestions (list[dict])

    Raises:
        FileNotFoundError: If the resume PDF doesn't exist.
        ValueError: If no text can be extracted from the resume.
    """
    resume_path = Path(resume_pdf_path)
    if not resume_path.exists():
        raise FileNotFoundError(f"Resume not found: {resume_path}")

    logger.info(f"Parsing resume: {resume_path.name}")
    parsed = parse_resume(str(resume_path))
    resume_text = parsed.get("full_text", "").strip()

    if not resume_text:
        raise ValueError(f"No text extracted from resume: {resume_path}")

    reports = []
    for i, match in enumerate(matched_jobs[:top_k], 1):
        job = match.get("job", {})
        jd_text = job.get("description", "")
        job_title = match.get("title") or job.get("title", "Unknown")
        job_url = match.get("url") or job.get("url", "")
        rank_score = match.get("rank_score", match.get("score", 0.0))

        logger.info(f"[{i}/{min(top_k, len(matched_jobs))}] Processing: {job_title}")

        if not jd_text:
            logger.warning(f"No description for '{job_title}' — skipping")
            continue

        ats_result = score_resume(resume_text, jd_text)
        critiques = critique_resume(resume_text, jd_text)
        suggestions = generate_suggestions(resume_text, jd_text, critiques)

        reports.append({
            "job_title": job_title,
            "job_url": job_url,
            "rank_score": rank_score,
            "ats_score": ats_result["overall_score"],
            "ats_grade": ats_result["grade"],
            "ats_breakdown": {
                "keyword":          ats_result["keyword_score"],
                "sections":         ats_result["section_score"],
                "formatting":       ats_result["formatting_score"],
                "keyword_detail":   ats_result["keyword_detail"],
                "section_detail":   ats_result["section_detail"],
                "formatting_detail": ats_result["formatting_detail"],
            },
            "critiques": critiques,
            "suggestions": suggestions,
        })

    logger.info(f"Generated {len(reports)} tailoring report(s)")
    return reports


def print_report(report: dict) -> None:
    """Pretty-print a single tailoring report."""
    w = 62
    print(f"\n{'='*w}")
    print(f"  {report['job_title']}")
    if report["job_url"]:
        print(f"  {report['job_url']}")
    ats = report["ats_score"]
    grade = report["ats_grade"]
    rank = report["rank_score"]
    print(f"  Rank Score: {rank:.4f}  |  ATS Score: {ats}/100 (Grade {grade})")
    print(f"{'='*w}")

    bd = report["ats_breakdown"]
    print(f"\n  ATS Breakdown")
    print(f"    Keyword density:       {bd['keyword']:.1f} / 40")
    print(f"    Section completeness:  {bd['sections']:.1f} / 30")
    print(f"    Formatting signals:    {bd['formatting']:.1f} / 30")
    missing = bd["keyword_detail"].get("top_missing", [])[:5]
    if missing:
        print(f"    Top missing keywords:  {missing}")

    print(f"\n  Critiques  ({len(report['critiques'])})")
    for j, c in enumerate(report["critiques"], 1):
        print(f"    [{j}] {c['section'].upper()} — {c['severity'].upper()}")
        print(f"        {c['issue']}")
        if c.get("current_text"):
            print(f"        → \"{c['current_text'][:80]}\"")

    print(f"\n  Suggestions  ({len(report['suggestions'])})")
    for j, s in enumerate(report["suggestions"], 1):
        print(f"    [{j}] {s['section'].upper()} — {s['priority'].upper()} priority")
        print(f"        {s['suggestion']}")
        if s.get("example_phrasing"):
            print(f"        Example: \"{s['example_phrasing']}\"")

    print(f"\n{'-'*w}")


def print_all_reports(reports: list[dict]) -> None:
    """Pretty-print all tailoring reports."""
    print(f"\n{'='*62}")
    print(f"  RESUME TAILOR AGENT — {len(reports)} Report(s)")
    print(f"{'='*62}")
    for report in reports:
        print_report(report)
    print()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    resume_path = (
        sys.argv[1]
        if len(sys.argv) > 1
        else "resume_matching_agent/test_data/resumes/Resume_AI_Fall_26.pdf"
    )

    from resume_matching_agent.pipeline import match_resume_to_jobs

    logger.info("Step 1 — Resume Matching Agent")
    matches = match_resume_to_jobs(
        resume_pdf_path=resume_path,
        job_source=None,
        top_k=5,
        candidate_extras={"years_experience": 2, "preferred_locations": ["Remote", "Los Angeles"]},
    )

    logger.info(f"\nStep 2 — Resume Tailor Agent ({min(3, len(matches))} reports)")
    reports = tailor_resume(resume_pdf_path=resume_path, matched_jobs=matches, top_k=3)
    print_all_reports(reports)
