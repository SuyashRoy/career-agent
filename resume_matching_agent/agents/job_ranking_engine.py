"""Multi-signal ranking engine for job matches.

Re-ranks semantic similarity matches using additional signals:
    - Semantic similarity (from FAISS cosine search)
    - Experience fit (years + seniority alignment)
    - Location match (candidate preference vs job location)
    - Preference match (skills, industry, role-type alignment)

Weights are configurable. Signals that can't be computed (missing data)
gracefully default to neutral scores (0.5) rather than crashing.
"""

import re
import logging

logger = logging.getLogger(__name__)


class RankingEngine:
    """Composite ranking engine combining semantic and heuristic signals."""

    DEFAULT_WEIGHTS = {
        "semantic": 0.50,
        "experience_fit": 0.20,
        "location_match": 0.15,
        "preference_match": 0.15,
    }

    NEUTRAL_SCORE = 0.5  # Default when a signal can't be computed

    def __init__(self, weights: dict = None):
        """Initialize with optional custom weights.

        Args:
            weights: dict mapping signal names to float weights.
                     Must sum to 1.0. Defaults to DEFAULT_WEIGHTS.
        """
        self.weights = weights or self.DEFAULT_WEIGHTS.copy()

    def rank(self, matches: list[dict], candidate_profile: dict) -> list[dict]:
        """Re-rank matches using composite scoring.

        Args:
            matches: list of dicts from matcher.py, each with at minimum
                     'score' (semantic similarity) and optionally 'job' (full JD dict).
            candidate_profile: dict with candidate info. Expected keys:
                     'full_text', 'sections' (from resume_parser), and optionally
                     'preferred_locations', 'years_experience'.

        Returns:
            list[dict] sorted by composite rank_score descending.
            Each dict gets additional keys: rank_score, signal_breakdown.
        """
        ranked = []

        for match in matches:
            sem = match.get("score", 0.0)
            job = match.get("job", {})

            exp = self._experience_fit(job, candidate_profile)
            loc = self._location_match(job, candidate_profile)
            pref = self._preference_match(job, candidate_profile)

            composite = (
                self.weights["semantic"] * sem
                + self.weights["experience_fit"] * exp
                + self.weights["location_match"] * loc
                + self.weights["preference_match"] * pref
            )

            ranked.append({
                **match,
                "rank_score": round(composite, 4),
                "signal_breakdown": {
                    "semantic": round(sem, 4),
                    "experience_fit": round(exp, 4),
                    "location_match": round(loc, 4),
                    "preference_match": round(pref, 4),
                },
            })

        return sorted(ranked, key=lambda x: x["rank_score"], reverse=True)

    def _experience_fit(self, job: dict, candidate: dict) -> float:
        """Score how well candidate experience matches job requirements.

        Heuristic: extracts years-of-experience mentions from JD text
        and compares against candidate's stated experience.
        Returns NEUTRAL_SCORE if either side lacks data.
        """
        jd_text = job.get("description", "")
        candidate_years = candidate.get("years_experience")

        if not jd_text or candidate_years is None:
            return self.NEUTRAL_SCORE

        # Extract "X+ years" or "X years" patterns from JD
        year_patterns = re.findall(r"(\d+)\+?\s*years?", jd_text.lower())

        if not year_patterns:
            return self.NEUTRAL_SCORE

        required_years = max(int(y) for y in year_patterns)

        if candidate_years >= required_years:
            return 1.0
        elif candidate_years >= required_years * 0.7:
            return 0.7  # Close enough — still worth applying
        else:
            return 0.3  # Significant experience gap

    def _location_match(self, job: dict, candidate: dict) -> float:
        """Score location compatibility.

        Checks if job location matches candidate's preferred locations.
        Treats 'remote' as a universal match.
        Returns NEUTRAL_SCORE if location data is missing.
        """
        job_location = job.get("location", "").lower().strip()
        preferred = candidate.get("preferred_locations", [])

        if not job_location or not preferred:
            return self.NEUTRAL_SCORE

        # Remote is always a match
        if "remote" in job_location:
            return 1.0

        preferred_lower = [loc.lower().strip() for loc in preferred]

        # Check for exact or partial match
        for pref in preferred_lower:
            if pref in job_location or job_location in pref:
                return 1.0

        return 0.2  # No location match

    def _preference_match(self, job: dict, candidate: dict) -> float:
        """Score alignment between candidate skills and JD requirements.

        Uses simple keyword overlap between candidate's skills section
        and the job description text. More sophisticated NLP matching
        is handled by the semantic score — this catches explicit keyword hits.
        Returns NEUTRAL_SCORE if skill data is missing.
        """
        jd_text = job.get("description", "").lower()
        sections = candidate.get("sections", {})
        skills_text = sections.get("skills", "").lower()

        if not jd_text or not skills_text:
            return self.NEUTRAL_SCORE

        # Extract individual skill keywords
        # Split on common delimiters: commas, pipes, newlines, bullets
        skill_tokens = re.split(r"[,|\n•·\-]+", skills_text)
        skill_tokens = [s.strip() for s in skill_tokens if len(s.strip()) > 2]

        if not skill_tokens:
            return self.NEUTRAL_SCORE

        # Count how many candidate skills appear in the JD
        hits = sum(1 for skill in skill_tokens if skill in jd_text)
        match_ratio = hits / len(skill_tokens)

        # Scale: 60%+ skill match = perfect score
        if match_ratio >= 0.6:
            return 1.0
        elif match_ratio >= 0.3:
            return 0.7
        elif match_ratio > 0:
            return 0.4
        else:
            return 0.1


if __name__ == "__main__":
    print("RankingEngine — Smoke Test")
    print("=" * 40)

    engine = RankingEngine()

    # Simulated matches from matcher.py
    matches = [
        {
            "job_id": 0,
            "score": 0.85,
            "title": "ML Engineer",
            "job": {
                "title": "ML Engineer",
                "description": "3+ years experience with PyTorch and transformers. Remote position.",
                "location": "Remote",
            },
        },
        {
            "job_id": 1,
            "score": 0.72,
            "title": "Marketing Manager",
            "job": {
                "title": "Marketing Manager",
                "description": "Lead marketing campaigns. 5 years experience required. NYC office.",
                "location": "New York, NY",
            },
        },
    ]

    candidate = {
        "full_text": "ML engineer with 4 years experience...",
        "sections": {"skills": "Python, PyTorch, transformers, FAISS, LangGraph"},
        "years_experience": 4,
        "preferred_locations": ["Remote", "Los Angeles"],
    }

    ranked = engine.rank(matches, candidate)

    for r in ranked:
        print(f"\n  {r['title']}")
        print(f"    Rank score: {r['rank_score']}")
        print(f"    Breakdown:  {r['signal_breakdown']}")

    # Verify ML Engineer ranks above Marketing Manager
    assert ranked[0]["title"] == "ML Engineer", "ML Engineer should rank first"
    print("\n✅ Ranking engine test passed")