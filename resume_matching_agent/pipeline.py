"""End-to-end resume matching pipeline.

Public API for the Resume Matching Agent. Takes a resume PDF path
and job descriptions from any supported source, returns ranked matches.

Usage:
    from resume_matching_agent.pipeline import match_resume_to_jobs

    results = match_resume_to_jobs(
        resume_pdf_path="path/to/resume.pdf",
        job_source="path/to/jds/",          # or URL, dict, list, etc.
        top_k=5,
    )
"""

import logging
from pathlib import Path
from typing import Union

import numpy as np

from .agents.resume_parser import parse_resume
from .agents.embedding_engine import embed_texts
from .agents.job_description_loader import load_job_descriptions
from .agents.matcher import match_resume
from .agents.job_ranking_engine import RankingEngine

logger = logging.getLogger(__name__)


def match_resume_to_jobs(
    resume_pdf_path: str,
    job_source: Union[str, dict, list, Path] = None,
    top_k: int = 5,
    candidate_extras: dict = None,
) -> list[dict]:
    """Match a resume against job descriptions and return ranked results.

    Args:
        resume_pdf_path: Path to the candidate's resume PDF.
        job_source: Job descriptions in any format accepted by
                    load_job_descriptions(). None loads from
                    test_data/job_descriptions/.
        top_k: Number of top matches to return.
        candidate_extras: Optional dict with additional candidate info
                          for ranking signals (years_experience,
                          preferred_locations). Merged with parsed resume data.

    Returns:
        list[dict] sorted by composite rank_score, each containing:
            - job_id, title, score (semantic), rank_score (composite)
            - signal_breakdown (per-signal scores)
            - job (full JD dict)

    Raises:
        FileNotFoundError: If resume PDF doesn't exist.
        ValueError: If no job descriptions could be loaded.
    """
    # ── Step 1: Parse resume ──────────────────────────────────────────
    resume_path = Path(resume_pdf_path)
    if not resume_path.exists():
        raise FileNotFoundError(f"Resume not found: {resume_path}")

    logger.info(f"Parsing resume: {resume_path}")
    resume_result = parse_resume(str(resume_path))

    if not resume_result.get("full_text", "").strip():
        raise ValueError(f"No text extracted from resume: {resume_path}")

    # ── Step 2: Load job descriptions ─────────────────────────────────
    logger.info("Loading job descriptions...")
    job_descriptions = load_job_descriptions(job_source)

    if not job_descriptions:
        raise ValueError("No job descriptions loaded. Check your source.")

    logger.info(f"Loaded {len(job_descriptions)} job description(s)")

    # ── Step 3: Generate embeddings ───────────────────────────────────
    logger.info("Generating embeddings...")
    resume_embedding = embed_texts([resume_result["full_text"]], is_query=True)

    jd_texts = [jd["description"] for jd in job_descriptions]
    jd_embeddings = embed_texts(jd_texts, is_query=False)

    # ── Step 4: FAISS semantic matching ───────────────────────────────
    logger.info(f"Running FAISS search (top_k={top_k})...")
    matches = match_resume(
        resume_embedding=resume_embedding,
        jd_embeddings=jd_embeddings,
        job_metadata=job_descriptions,
        top_k=top_k,
    )

    # ── Step 5: Composite ranking ─────────────────────────────────────
    logger.info("Applying composite ranking...")

    # Build candidate profile by merging parsed resume + any extras
    candidate_profile = {
        "full_text": resume_result["full_text"],
        "sections": resume_result.get("sections", {}),
    }
    if candidate_extras:
        candidate_profile.update(candidate_extras)

    ranking_engine = RankingEngine()
    ranked = ranking_engine.rank(matches, candidate_profile)

    logger.info(f"Returning {len(ranked)} ranked match(es)")
    return ranked


def print_results(results: list[dict]) -> None:
    """Pretty-print ranked match results to console."""
    print(f"\n{'='*60}")
    print(f"  RESUME MATCHING RESULTS — {len(results)} match(es)")
    print(f"{'='*60}")

    for i, r in enumerate(results, 1):
        title = r.get("title", "Unknown")
        rank_score = r.get("rank_score", 0)
        semantic = r.get("signal_breakdown", {}).get("semantic", 0)
        exp = r.get("signal_breakdown", {}).get("experience_fit", 0)
        loc = r.get("signal_breakdown", {}).get("location_match", 0)
        pref = r.get("signal_breakdown", {}).get("preference_match", 0)

        print(f"\n  #{i}  {title}")
        print(f"       Composite Score:  {rank_score:.4f}")
        print(f"       ├── Semantic:     {semantic:.4f}")
        print(f"       ├── Experience:   {exp:.4f}")
        print(f"       ├── Location:     {loc:.4f}")
        print(f"       └── Preference:   {pref:.4f}")
        if r.get("url"):
            print(f"       URL: {r['url']}")

    print(f"\n{'='*60}\n")


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    # Default paths — adjust as needed
    resume_path = sys.argv[1] if len(sys.argv) > 1 else "test_data/resumes/Resume_AI_Fall_26.pdf"
    jd_dir = sys.argv[2] if len(sys.argv) > 2 else None  # None = load from default dir

    results = match_resume_to_jobs(
        resume_pdf_path=resume_path,
        job_source=jd_dir,
        top_k=5,
        candidate_extras={
            "years_experience": 2,
            "preferred_locations": ["Remote", "Los Angeles", "San Francisco"],
        },
    )

    print_results(results)