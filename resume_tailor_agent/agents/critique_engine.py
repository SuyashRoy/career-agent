"""LLM-powered resume critique engine.

Uses Groq Llama 3.3 70B to identify the 3-5 most critical weaknesses in a
resume for a specific job description. Returns structured critique objects
that the suggestion_generator uses as input.
"""

import json
import re
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).parent.parent.parent  # career-agent/
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from groq import Groq
from shared.config import get_groq_api_key

_MODEL = "llama-3.3-70b-versatile"
_MAX_CHARS = 3000

_SYSTEM_PROMPT = (
    "You are a professional resume reviewer. Identify specific, actionable weaknesses "
    "in a resume relative to a job description. Be honest and precise — focus only on "
    "the 3-5 most impactful issues."
)

_USER_TEMPLATE = """\
RESUME:
{resume}

JOB DESCRIPTION:
{jd}

Identify exactly 3-5 weaknesses in this resume for this specific role.

Return ONLY a JSON array, no other text. Schema:
[
  {{
    "section": "<summary|experience|skills|education|projects|other>",
    "issue": "<1-2 sentences describing the weakness>",
    "severity": "<high|medium|low>",
    "current_text": "<the actual weak phrase from the resume, or empty string>"
  }}
]

Focus on: missing keywords, missing metrics, weak action verbs, experience gaps, \
missing sections, or mismatched skills — relative to this specific job."""


def critique_resume(resume_text: str, jd_text: str) -> list[dict]:
    """Analyze a resume against a JD and return structured weaknesses.

    Args:
        resume_text: Full text of the candidate's resume.
        jd_text: Full text of the job description.

    Returns:
        list[dict] each with keys: section, issue, severity, current_text.
        Returns empty list on LLM failure.
    """
    prompt = _USER_TEMPLATE.format(
        resume=resume_text[:_MAX_CHARS].strip(),
        jd=jd_text[:_MAX_CHARS].strip(),
    )
    try:
        client = Groq(api_key=get_groq_api_key())
        response = client.chat.completions.create(
            model=_MODEL,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            max_tokens=800,
            temperature=0.3,
        )
        raw = response.choices[0].message.content.strip()
    except Exception as e:
        print(f"[critique_engine] LLM call failed: {e}")
        return []

    match = re.search(r"\[.*\]", raw, re.DOTALL)
    if not match:
        print(f"[critique_engine] No JSON array in response: {raw[:200]}")
        return []

    try:
        items = json.loads(match.group(0))
        return [
            {
                "section": item.get("section", "other"),
                "issue": str(item["issue"]),
                "severity": item.get("severity", "medium").lower(),
                "current_text": item.get("current_text", ""),
            }
            for item in items
            if "issue" in item
        ]
    except json.JSONDecodeError as e:
        print(f"[critique_engine] JSON parse error: {e}")
        return []


if __name__ == "__main__":
    sample_resume = """
    EXPERIENCE
    Led team to build recommendation system. Worked on ML models. Deployed to cloud.

    TECHNICAL SKILLS
    Python, machine learning, some SQL

    EDUCATION
    BS Computer Science
    """
    sample_jd = (
        "Senior ML Engineer. 3+ years PyTorch. Must have production experience "
        "handling 1M+ requests/day. FAISS or Pinecone required. AWS or GCP preferred."
    )
    critiques = critique_resume(sample_resume, sample_jd)
    for i, c in enumerate(critiques, 1):
        print(f"\n[{i}] {c['section'].upper()} — {c['severity'].upper()}")
        print(f"  Issue: {c['issue']}")
        if c["current_text"]:
            print(f"  Text:  {c['current_text']}")
