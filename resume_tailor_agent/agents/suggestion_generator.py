"""LLM-powered suggestion generator for resume improvement.

Takes critique output from critique_engine and generates targeted, actionable
suggestions. Does NOT rewrite resume content — provides specific guidance on
what to change and a short example of improved phrasing only.

Uses Groq Llama 3.3 70B.
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
_MAX_CHARS = 2000

_SYSTEM_PROMPT = (
    "You are a career coach helping a candidate improve their resume. "
    "Provide targeted, actionable suggestions — tell the candidate what to change and why. "
    "Do NOT rewrite resume content. Keep example_phrasing under 20 words."
)

_USER_TEMPLATE = """\
RESUME (excerpt):
{resume}

JOB DESCRIPTION (excerpt):
{jd}

IDENTIFIED WEAKNESSES:
{critiques}

For each weakness, provide a specific improvement suggestion.

Return ONLY a JSON array, no other text. Schema:
[
  {{
    "section": "<same section as the critique>",
    "suggestion": "<1-2 sentences: what to change and why>",
    "example_phrasing": "<one improved sentence, ≤ 20 words>",
    "priority": "<high|medium|low — match the critique severity>"
  }}
]"""


def generate_suggestions(
    resume_text: str,
    jd_text: str,
    critiques: list[dict],
) -> list[dict]:
    """Generate targeted improvement suggestions for each critique.

    Args:
        resume_text: Full text of the candidate's resume.
        jd_text: Full text of the job description.
        critiques: list[dict] from critique_engine.critique_resume().

    Returns:
        list[dict] each with keys: section, suggestion, example_phrasing, priority.
        Returns empty list if critiques is empty or LLM fails.
    """
    if not critiques:
        return []

    critiques_text = "\n".join(
        f"{i+1}. [{c.get('section','other').upper()}] "
        f"({c.get('severity','medium')} severity) {c.get('issue','')}"
        for i, c in enumerate(critiques)
    )

    prompt = _USER_TEMPLATE.format(
        resume=resume_text[:_MAX_CHARS].strip(),
        jd=jd_text[:_MAX_CHARS].strip(),
        critiques=critiques_text,
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
            temperature=0.4,
        )
        raw = response.choices[0].message.content.strip()
    except Exception as e:
        print(f"[suggestion_generator] LLM call failed: {e}")
        return []

    match = re.search(r"\[.*\]", raw, re.DOTALL)
    if not match:
        print(f"[suggestion_generator] No JSON array in response: {raw[:200]}")
        return []

    try:
        items = json.loads(match.group(0))
        return [
            {
                "section": item.get("section", "other"),
                "suggestion": str(item["suggestion"]),
                "example_phrasing": item.get("example_phrasing", ""),
                "priority": item.get("priority", "medium").lower(),
            }
            for item in items
            if "suggestion" in item
        ]
    except json.JSONDecodeError as e:
        print(f"[suggestion_generator] JSON parse error: {e}")
        return []


if __name__ == "__main__":
    sample_resume = "Led team to build recommendation system. Worked on ML models."
    sample_jd = "Senior ML Engineer. 3+ years PyTorch. Production systems experience required."
    sample_critiques = [
        {
            "section": "experience",
            "issue": "No quantification — no metrics or scale mentioned.",
            "severity": "high",
            "current_text": "Led team to build recommendation system.",
        },
        {
            "section": "skills",
            "issue": "PyTorch not listed despite being a core requirement.",
            "severity": "high",
            "current_text": "Python, machine learning, some SQL",
        },
    ]
    suggestions = generate_suggestions(sample_resume, sample_jd, sample_critiques)
    for i, s in enumerate(suggestions, 1):
        print(f"\n[{i}] {s['section'].upper()} — {s['priority'].upper()} priority")
        print(f"  Suggestion: {s['suggestion']}")
        print(f"  Example:    {s['example_phrasing']}")
