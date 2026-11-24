"""Embedding backends. Default: deterministic hashing embeddings (no download needed).
Set DOCQA_EMBEDDING_BACKEND=st for sentence-transformers (pip install sentence-transformers)."""
import hashlib, re
import numpy as np
from .config import EMBEDDING_BACKEND, ST_MODEL

DIM = 1024
STOP = set("""a an the and or but if then of to in on at by for with about as is are was were be been being it its this that
these those from into over under up down out not no do does did have has had will would can could should may might what which
who whom whose when where why how i you he she we they them his her their our your my me us than so such also very just more
most other some any each few all both between during before after above below again further once here there only own same too""".split())
_TOK = re.compile(r"[a-z0-9]+")


def tokenize(text: str):
    return [t for t in _TOK.findall(text.lower()) if t not in STOP and len(t) > 1]


def _stem(t: str) -> str:
    for suf in ("ingly", "edly", "ing", "ies", "ed", "es", "s", "ly"):
        if t.endswith(suf) and len(t) - len(suf) >= 3:
            return t[: -len(suf)] + ("y" if suf == "ies" else "")
    return t


def _h(s: str) -> int:
    return int.from_bytes(hashlib.md5(s.encode()).digest()[:4], "little")


class HashEmbedder:
    name = "hash-1024"
    dim = DIM

    def embed_one(self, text: str) -> np.ndarray:
        toks = [_stem(t) for t in tokenize(text)]
        v = np.zeros(DIM, dtype=np.float32)
        feats = toks + [f"{a}_{b}" for a, b in zip(toks, toks[1:])]
        for f in feats:
            h = _h(f)
            sign = 1.0 if (h >> 31) & 1 else -1.0
            w = 1.0 if "_" not in f else 0.6
            v[h % DIM] += sign * w
            # 5-char prefix links morphological variants (employs / employees)
            if "_" not in f and len(f) >= 6:
                h3 = _h("p:" + f[:5])
                v[h3 % DIM] += (1.0 if (h3 >> 31) & 1 else -1.0) * 0.5
            # character trigrams of unigrams give robustness to typos/morphology
            if "_" not in f and len(f) > 4:
                for i in range(len(f) - 2):
                    h2 = _h("c:" + f[i:i + 3])
                    v[h2 % DIM] += (1.0 if (h2 >> 31) & 1 else -1.0) * 0.15
        v = np.sign(v) * np.log1p(np.abs(v))        # sublinear tf
        n = np.linalg.norm(v)
        return v / n if n else v

    def embed(self, texts):
        return np.vstack([self.embed_one(t) for t in texts]) if texts else np.zeros((0, DIM), np.float32)


class STEmbedder:
    def __init__(self):
        from sentence_transformers import SentenceTransformer
        self.model = SentenceTransformer(ST_MODEL)
        self.name = f"st-{ST_MODEL}"
        self.dim = self.model.get_sentence_embedding_dimension()

    def embed(self, texts):
        return np.asarray(self.model.encode(list(texts), normalize_embeddings=True), dtype=np.float32)


_embedder = None


def get_embedder():
    global _embedder
    if _embedder is None:
        if EMBEDDING_BACKEND == "st":
            try:
                _embedder = STEmbedder()
            except Exception as e:
                print(f"[embeddings] sentence-transformers unavailable ({e}); using hash embedder")
                _embedder = HashEmbedder()
        else:
            _embedder = HashEmbedder()
    return _embedder


def embed_texts(texts) -> np.ndarray:
    return get_embedder().embed(list(texts))
