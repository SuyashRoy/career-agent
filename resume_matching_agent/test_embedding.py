"""Smoke test: verify resume and JD embeddings have matching dimensions."""

from agents.embedding_engine import embed_texts
from agents.resume_parser import parse_resume

def test_embedding_dimensions():
    # Embed a resume
    result = parse_resume("test_data/resumes/Resume_AI_Fall_26.pdf")
    resume_embedding = embed_texts([result["full_text"]], is_query=True)

    # Embed a job description
    sample_jd = (
        "We are looking for an ML Engineer with experience in PyTorch, "
        "transformer architectures, and deploying models at scale. "
        "Experience with vector databases and RAG pipelines preferred."
    )
    jd_embedding = embed_texts([sample_jd], is_query=False)

    print(f"Resume embedding shape: {resume_embedding.shape}")
    print(f"JD embedding shape:     {jd_embedding.shape}")
    print(f"Dimensions match:       {resume_embedding.shape[1] == jd_embedding.shape[1]}")
    assert resume_embedding.shape[1] == 1024, f"Expected 1024, got {resume_embedding.shape[1]}"
    assert jd_embedding.shape[1] == 1024, f"Expected 1024, got {jd_embedding.shape[1]}"
    print("\n✅ All dimension checks passed")

if __name__ == "__main__":
    test_embedding_dimensions()