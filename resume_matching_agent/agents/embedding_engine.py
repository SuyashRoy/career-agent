'''Load BGE-large-en-v1.5 from HuggingFace via sentence-transformers'''

import numpy as np
from sentence_transformers import SentenceTransformer

MODEL_NAME = 'BAAI/bge-large-en-v1.5'
QUERY_PREFIX = 'Represent this sentence: '
_model = None

# model = SentenceTransformer('BAAI/bge-large-en-v1.5')
### Lazy loading of the model to avoid loading it multiple times
def _get_model():
    global _model
    if _model is None:
        _model = SentenceTransformer(MODEL_NAME)
    return _model

def embed_texts(texts: list[str], is_query: bool = False) -> np.ndarray:
    '''Embed a list of texts using the BGE-large-en-v1.5 model. 
    If is_query is True, add the QUERY_PREFIX before to each text before embedding.
    is_query = True for Resume and False for Job Description.'''
    model = _get_model()
    if is_query:
        texts = [QUERY_PREFIX + text for text in texts]
    return model.encode(texts, normalize_embeddings=True) ### Normalize embeddings to unit length for cosine similarity calculations and faster FAISS indexing.
