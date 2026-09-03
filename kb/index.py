"""Local knowledge base: hybrid retrieval over the organisation's documents.

Two searches run in parallel and their ranks are fused:
  - vector search finds things that MEAN the same
  - BM25 keyword search finds exact identifiers (tag numbers, clause refs)

Vector search alone reliably fails on 'P-101B'. In engineering documents
that is not an edge case, it is most of the queries.
"""
import json, pickle
from pathlib import Path
import numpy as np
from rank_bm25 import BM25Okapi
from core import llm, trace, registry
from . import chunk as chunker

STORE = Path("kb_store.pkl")


def build(doc_paths, out=STORE):
    chunks = []
    for p in doc_paths:
        p = Path(p)
        chunks.extend(chunker.chunk_text(p.read_text(errors="ignore"), p.name))

    vectors = np.array(llm.embed([c["text"] for c in chunks]), dtype=np.float32)
    vectors /= np.linalg.norm(vectors, axis=1, keepdims=True) + 1e-9

    store = {
        "chunks": chunks,
        "vectors": vectors,
        "embed_model": registry.embeddings_cfg()["model_name"],
    }
    with open(out, "wb") as f:
        pickle.dump(store, f)
    trace.emit("kb_build", chunks=len(chunks), docs=len(doc_paths))
    return store


def load(path=STORE):
    with open(path, "rb") as f:
        store = pickle.load(f)
    current = registry.embeddings_cfg()["model_name"]
    if store["embed_model"] != current:
        raise RuntimeError(
            f"Index was built with '{store['embed_model']}' but config now says "
            f"'{current}'. Results would be meaningless. Rebuild the index."
        )
    store["bm25"] = BM25Okapi([c["text"].lower().split() for c in store["chunks"]])
    return store


def search(store, query, k=5):
    qv = np.array(llm.embed([query])[0], dtype=np.float32)
    qv /= np.linalg.norm(qv) + 1e-9
    dense = store["vectors"] @ qv

    sparse = store["bm25"].get_scores(query.lower().split())

    dense_rank = {i: r for r, i in enumerate(np.argsort(-dense))}
    sparse_rank = {i: r for r, i in enumerate(np.argsort(-np.array(sparse)))}

    # Reciprocal rank fusion. Robust, needs no score normalisation.
    fused = {
        i: 1 / (60 + dense_rank[i]) + 1 / (60 + sparse_rank[i])
        for i in range(len(store["chunks"]))
    }
    top = sorted(fused, key=fused.get, reverse=True)[:k]

    hits = [{
        "text": store["chunks"][i]["text"],
        "source": store["chunks"][i]["source"],
        "section": store["chunks"][i]["section"],
        "cosine": round(float(dense[i]), 3),
        "bm25": round(float(sparse[i]), 2),
    } for i in top]

    trace.emit("retrieve", query=query,
               hits=[{"source": h["source"], "section": h["section"],
                      "cosine": h["cosine"], "bm25": h["bm25"]} for h in hits])
    return hits
