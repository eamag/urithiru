"""Original exact/Ward/model deduplication and shared embedding-based context selection."""

from pathlib import Path

import numpy as np
from scipy.cluster.hierarchy import linkage

from urithiru.runtime.checkpoints import read_json, write_json


def canonicalize(claim: str) -> str:
    value = " ".join(claim.split())
    if not value:
        raise ValueError("Hypothesis cannot be empty")
    return value


class DisjointSet:
    """Merged claims keep the lowest index, which is the original engine's representative."""

    def __init__(self, size: int):
        self.parents = list(range(size))

    def root(self, index: int) -> int:
        while self.parents[index] != index:
            index = self.parents[index]
        return index

    def union(self, left: int, right: int) -> int:
        keep, drop = min(left, right), max(left, right)
        self.parents[drop] = keep
        return keep


class CandidateSelector:
    def __init__(self, model, directory: Path, top_k: int):
        self.model, self.directory, self.top_k = model, directory / "artifacts", top_k
        self.directory.mkdir(parents=True, exist_ok=True)
        self.embeddings = self.load_cache("embeddings.json")
        self.merges = self.load_cache("dedupe_llm_decisions.json")

    def load_cache(self, name: str) -> dict:
        path = self.directory / name
        return read_json(path) if path.exists() else {}

    def embed(self, texts: list[str]) -> np.ndarray:
        missing = list(dict.fromkeys(text for text in texts if text not in self.embeddings))
        if missing:
            self.embeddings.update(zip(missing, self.model.embed(missing), strict=True))
            write_json(self.directory / "embeddings.json", self.embeddings)
        # The original stores JSON floats but converts them to float32 before clustering/retrieval.
        return np.array([self.embeddings[text] for text in texts], dtype=np.float32)

    def same(self, left: str, right: str) -> bool:
        forward, backward = f"{left} ||| {right}", f"{right} ||| {left}"
        if forward in self.merges:
            return self.merges[forward]
        if backward in self.merges:
            return self.merges[backward]
        result = self.model.same_claim(left, right)
        self.merges[forward] = result
        write_json(self.directory / "dedupe_llm_decisions.json", self.merges)
        return result

    def deduplicate(self, candidates: list[str], verified: list[str]) -> tuple[list[int], dict, dict]:
        verified = list(dict.fromkeys(canonicalize(claim) for claim in verified))
        seen, live, exact = set(verified), [], {}
        for index, claim in enumerate(candidates):
            claim = canonicalize(claim)
            if claim in seen:
                exact[index] = claim
            else:
                seen.add(claim)
                live.append((index, claim))
        pool = verified + [claim for _, claim in live]
        representatives = self.cluster(pool) if len(pool) >= 2 else list(range(len(pool)))
        survivors, semantic = [], {}
        for index, (original, _) in enumerate(live, start=len(verified)):
            if representatives[index] == index:
                survivors.append(original)
            else:
                semantic[original] = pool[representatives[index]]
        return survivors, exact, semantic

    def cluster(self, pool: list[str]) -> list[int]:
        """Walk scipy's merge order; a scipy cluster id is `len(pool) + merge number`."""
        groups = DisjointSet(len(pool))
        cluster_representative = dict(enumerate(range(len(pool))))
        for number, (left_id, right_id, _distance, _size) in enumerate(linkage(self.embed(pool), "ward")):
            left = groups.root(cluster_representative[int(left_id)])
            right = groups.root(cluster_representative[int(right_id)])
            merged = groups.union(left, right) if self.same(pool[left], pool[right]) else min(left, right)
            cluster_representative[len(pool) + number] = merged
        return [groups.root(index) for index in range(len(pool))]

    def diversity(self, candidates: list[str], verified: list[str]) -> list[float]:
        vectors = self.embed(verified + candidates).astype(np.float64)
        vectors /= np.linalg.norm(vectors, axis=1, keepdims=True)
        similarity = vectors[len(verified) :] @ vectors[: len(verified)].T
        return np.sort(similarity, axis=1)[:, -self.top_k :].mean(axis=1).tolist()

    def retrieve(self, claim: str, nodes: list) -> list:
        if not claim:
            return nodes[-self.top_k :]
        if not nodes:
            return []
        vectors = self.embed([claim, *(node.claim for node in nodes)])
        target, candidates = vectors[0], vectors[1:]
        similarity = candidates @ target / (np.linalg.norm(candidates, axis=1) * np.linalg.norm(target))
        return [nodes[int(index)] for index in np.argsort(-similarity)[: self.top_k]]
