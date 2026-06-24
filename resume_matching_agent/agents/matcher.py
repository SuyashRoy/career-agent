"""FAISS-based semantic matching between resume and job description embeddings.

Uses cosine similarity via inner product on L2-normalized vectors.
Embeddings are expected to be pre-normalized (from embed_texts with
normalize_embeddings=True), but normalization is applied defensively.
"""

import numpy as np
import faiss


def build_index(jd_embeddings: np.ndarray) -> faiss.IndexFlatIP:
    """Build a FAISS inner-product index from job description embeddings.

    Args:
        jd_embeddings: Array of shape (n_jobs, embedding_dim), pre-normalized.

    Returns:
        FAISS IndexFlatIP ready for search.
    """
    jd_embeddings = np.ascontiguousarray(jd_embeddings, dtype=np.float32)
    # Defensive normalization (no-op if already unit vectors)
    faiss.normalize_L2(jd_embeddings)

    dimension = jd_embeddings.shape[1]
    index = faiss.IndexFlatIP(dimension)
    index.add(jd_embeddings)
    return index


def match_resume(
    resume_embedding: np.ndarray,
    jd_embeddings: np.ndarray,
    job_metadata: list[dict] = None,
    top_k: int = 5,
) -> list[dict]:
    """Match a resume embedding against job description embeddings.

    Args:
        resume_embedding: Array of shape (1, embedding_dim).
        jd_embeddings: Array of shape (n_jobs, embedding_dim).
        job_metadata: Optional list of dicts with JD info (title, url, etc.).
                      Must be same length as jd_embeddings if provided.
        top_k: Number of top matches to return.

    Returns:
        list[dict] with keys: job_id, score, and any metadata fields.
        Sorted by score descending.
    """
    n_jobs = jd_embeddings.shape[0]
    top_k = min(top_k, n_jobs)  # Guard against top_k > available jobs

    if top_k == 0:
        return []

    # Build index and search
    index = build_index(jd_embeddings)

    resume_query = np.ascontiguousarray(resume_embedding, dtype=np.float32)
    faiss.normalize_L2(resume_query)

    distances, indices = index.search(resume_query, top_k)

    # Build results with optional metadata enrichment
    results = []
    for i in range(top_k):
        idx = int(indices[0][i])
        if idx == -1:
            continue  # FAISS returns -1 for unfilled slots

        result = {
            "job_id": idx,
            "score": round(float(distances[0][i]), 4),
        }

        # Attach JD metadata if provided
        if job_metadata and idx < len(job_metadata):
            result["title"] = job_metadata[idx].get("title", "Unknown")
            result["url"] = job_metadata[idx].get("url", "")
            result["company"] = job_metadata[idx].get("company", "")
            result["job"] = job_metadata[idx]  # Full JD dict for ranking engine

        results.append(result)

    return results


if __name__ == "__main__":
    print("matcher.py — Smoke Test")
    print("=" * 40)

    # Simulate embeddings (1024-dim for BGE-large)
    np.random.seed(42)
    fake_resume = np.random.randn(1, 1024).astype(np.float32)
    fake_jds = np.random.randn(5, 1024).astype(np.float32)

    metadata = [
        {"title": "ML Engineer", "url": "https://example.com/1"},
        {"title": "Data Scientist", "url": "https://example.com/2"},
        {"title": "Frontend Dev", "url": "https://example.com/3"},
        {"title": "AI Researcher", "url": "https://example.com/4"},
        {"title": "Marketing Manager", "url": "https://example.com/5"},
    ]

    results = match_resume(fake_resume, fake_jds, job_metadata=metadata, top_k=3)

    for r in results:
        print(f"  #{r['job_id']} {r['title']}: {r['score']}")

    # Edge case: top_k > n_jobs
    results = match_resume(fake_resume, fake_jds, top_k=10)
    assert len(results) == 5, f"Expected 5, got {len(results)}"

    print("\n✅ All matcher tests passed")