"""Resume Matching Agent — semantic matching between resumes and job descriptions."""

from .agents.resume_parser import parse_resume
from .agents.embedding_engine import embed_texts
from .agents.job_description_loader import load_job_descriptions


def embed_resume(pdf_path: str):
    """Parse a resume PDF and return its embedding vector."""
    result = parse_resume(pdf_path)
    return embed_texts([result["full_text"]], is_query=True)


def embed_jd(description):
    """Load and embed a job description from any supported format."""
    jds = load_job_descriptions(description)
    texts = [jd["description"] for jd in jds]
    return embed_texts(texts, is_query=False)