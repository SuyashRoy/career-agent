"""Heuristic ATS scoring for a resume against a job description.

Returns an overall score 0-100 and a per-signal breakdown across three dimensions:
    1. Keyword density      — JD keywords present in the resume (40 pts)
    2. Section completeness — required resume sections detected  (30 pts)
    3. Formatting signals   — bullets, action verbs, quantities  (30 pts)

No LLM calls — fully deterministic so results are fast and reproducible.
"""

import re

_SECTION_KEYWORDS = {
    "summary":    ["summary", "objective", "professional summary", "about"],
    "experience": ["experience", "work experience", "professional experience", "employment"],
    "skills":     ["skills", "technical skills", "core competencies", "technologies"],
    "education":  ["education", "academic background", "education & certifications"],
}

_SECTION_WEIGHTS = {"experience": 10, "skills": 10, "education": 8, "summary": 7}

_ACTION_VERBS = {
    "achieved", "architected", "automated", "built", "created", "delivered",
    "deployed", "designed", "developed", "drove", "engineered", "established",
    "executed", "generated", "implemented", "improved", "increased", "launched",
    "led", "managed", "optimized", "produced", "reduced", "refactored", "shipped",
    "scaled", "spearheaded", "streamlined", "trained", "transformed",
}

_STOPWORDS = {
    "the", "and", "for", "with", "you", "are", "have", "will", "this",
    "that", "from", "our", "your", "we", "be", "to", "of", "a", "an",
    "in", "on", "at", "is", "it", "as", "by", "or", "not", "can",
    "all", "but", "its", "was", "has", "had", "been", "more", "also",
    "about", "into", "than", "they", "them", "their", "who", "what",
    "when", "where", "how", "which", "would", "could", "should",
    "must", "may", "any", "some", "such", "both", "each", "most",
    "very", "just", "over", "up", "out", "do", "did", "does", "new",
    "well", "per", "via", "role", "work", "team", "strong", "good",
    "working", "looking", "including", "across", "within", "between",
    "please", "apply", "position", "candidate", "opportunity",
}


def _extract_keywords(text: str) -> set[str]:
    tokens = re.findall(r"\b[a-zA-Z][a-zA-Z0-9+#.\-]{3,}\b", text.lower())
    return {t for t in tokens if t not in _STOPWORDS}


def _score_keyword_density(resume_text: str, jd_text: str) -> tuple[float, dict]:
    jd_keywords = _extract_keywords(jd_text)
    if not jd_keywords:
        return 20.0, {"jd_keywords": 0, "matched": 0, "ratio": 0.0, "top_missing": []}

    resume_lower = resume_text.lower()
    matched = {kw for kw in jd_keywords if kw in resume_lower}
    ratio = len(matched) / len(jd_keywords)
    score = min(40.0, ratio * 40.0)

    return score, {
        "jd_keywords": len(jd_keywords),
        "matched": len(matched),
        "ratio": round(ratio, 3),
        "top_missing": sorted(jd_keywords - matched)[:10],
    }


def _score_section_completeness(resume_text: str) -> tuple[float, dict]:
    resume_lower = resume_text.lower()
    found = {s: any(kw in resume_lower for kw in kws) for s, kws in _SECTION_KEYWORDS.items()}
    raw = sum(w for s, w in _SECTION_WEIGHTS.items() if found.get(s))
    score = (raw / sum(_SECTION_WEIGHTS.values())) * 30.0
    return score, found


def _score_formatting(resume_text: str) -> tuple[float, dict]:
    has_bullets = bool(re.search(r"^[\s]*[•\-\*·▪▸►◆]", resume_text, re.MULTILINE))
    bullet_score = 10.0 if has_bullets else 0.0

    resume_lower = resume_text.lower()
    found_verbs = _ACTION_VERBS & set(re.findall(r"\b\w+\b", resume_lower))
    # 5+ distinct action verbs = full score; scales linearly below that
    verb_score = min(10.0, len(found_verbs) * 2.0)

    quant_patterns = [
        r"\b\d+\s*%",
        r"\b\d+[kKmMbB]\+?\b",
        r"\$\s*\d+",
        r"\b\d{2,}\s*(users|customers|engineers|people|requests|ms|seconds|points)",
    ]
    quant_hits = sum(1 for p in quant_patterns if re.search(p, resume_text, re.IGNORECASE))
    quant_score = min(10.0, quant_hits * 5.0)

    return bullet_score + verb_score + quant_score, {
        "has_bullets": has_bullets,
        "action_verb_count": len(found_verbs),
        "found_action_verbs": sorted(found_verbs)[:8],
        "quantified_result_patterns": quant_hits,
    }


def score_resume(resume_text: str, jd_text: str) -> dict:
    """Score a resume against a job description using ATS heuristics.

    Args:
        resume_text: Full text of the candidate's resume.
        jd_text: Full text of the job description.

    Returns:
        dict with overall_score (0-100), grade (A-F), and per-signal scores + details.
    """
    kw_score, kw_detail = _score_keyword_density(resume_text, jd_text)
    sec_score, sec_detail = _score_section_completeness(resume_text)
    fmt_score, fmt_detail = _score_formatting(resume_text)
    total = kw_score + sec_score + fmt_score

    if total >= 85:
        grade = "A"
    elif total >= 70:
        grade = "B"
    elif total >= 55:
        grade = "C"
    elif total >= 40:
        grade = "D"
    else:
        grade = "F"

    return {
        "overall_score": round(total),
        "grade": grade,
        "keyword_score": round(kw_score, 1),
        "section_score": round(sec_score, 1),
        "formatting_score": round(fmt_score, 1),
        "keyword_detail": kw_detail,
        "section_detail": sec_detail,
        "formatting_detail": fmt_detail,
    }


if __name__ == "__main__":
    sample_resume = """
    SUMMARY
    ML engineer with 3 years of experience building production inference systems.

    EXPERIENCE
    • Built real-time recommendation system serving 500K users, reducing latency by 40%
    • Led team of 4 engineers to deploy transformer-based NLP pipeline on AWS
    • Achieved 25% reduction in infrastructure costs through model optimization

    TECHNICAL SKILLS
    Python, PyTorch, TensorFlow, FAISS, LangGraph, Docker, Kubernetes, AWS, PostgreSQL

    EDUCATION
    B.S. Computer Science, University of Southern California
    """
    sample_jd = """
    ML Engineer — Recommendations Team
    3+ years experience with PyTorch and transformer architectures. AWS required.
    FAISS or Pinecone experience strongly preferred. Strong Python skills.
    """
    result = score_resume(sample_resume, sample_jd)
    print(f"Score: {result['overall_score']}/100 (Grade {result['grade']})")
    print(f"  Keyword:    {result['keyword_score']}/40")
    print(f"  Sections:   {result['section_score']}/30")
    print(f"  Formatting: {result['formatting_score']}/30")
    print(f"  Missing keywords: {result['keyword_detail']['top_missing']}")
