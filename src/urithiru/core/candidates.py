from pathlib import Path

import numpy as np

from urithiru.runtime.files import read_json, write_json

SIMILARITY_THRESHOLD = 0.8


def canonicalize(claim: str) -> str:
    value = " ".join(claim.split())
    if not value:
        raise ValueError("Hypothesis cannot be empty")
    return value


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
        vectors = np.array([self.embeddings[text] for text in texts], dtype=np.float64)
        return vectors / np.linalg.norm(vectors, axis=1, keepdims=True)

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

    def deduplicate(self, candidates: list[str], verified: list[str]) -> dict[int, tuple[str, str]]:
        settled = list(dict.fromkeys(canonicalize(claim) for claim in verified))
        seen, fresh, duplicates = set(settled), [], {}
        for index, raw in enumerate(candidates):
            claim = canonicalize(raw)
            if claim in seen:
                duplicates[index] = (claim, "exact_duplicate")
                continue
            seen.add(claim)
            fresh.append((index, claim))
        if not fresh:
            return duplicates
        pool = settled + [claim for _, claim in fresh]
        vectors = dict(zip(pool, self.embed(pool), strict=True))
        for index, claim in fresh:
            match = self.nearest_duplicate(claim, vectors, settled)
            if match is None:
                settled.append(claim)
            else:
                duplicates[index] = (match, "semantic_duplicate")
        return duplicates

    def nearest_duplicate(self, claim: str, vectors: dict, others: list[str]) -> str | None:
        if not others:
            return None
        similarity = np.array([vectors[other] for other in others]) @ vectors[claim]
        for position in np.argsort(-similarity):
            if similarity[position] < SIMILARITY_THRESHOLD:
                return None
            if self.same(others[position], claim):
                return others[position]
        return None

    def diversity(self, candidates: list[str], verified: list[str]) -> list[float]:
        vectors = self.embed(verified + candidates)
        verified_vectors = vectors[: len(verified)]
        candidate_vectors = vectors[len(verified) :]
        similarity = candidate_vectors @ verified_vectors.T
        return np.sort(similarity, axis=1)[:, -self.top_k :].mean(axis=1).tolist()

    def retrieve(self, claim: str, nodes: list) -> list:
        if not claim:
            return nodes[-self.top_k :]
        if not nodes:
            return []
        vectors = self.embed([claim, *(node.claim for node in nodes)])
        claim_vector = vectors[0]
        node_vectors = vectors[1:]
        similarity = node_vectors @ claim_vector
        return [nodes[int(index)] for index in np.argsort(-similarity)[: self.top_k]]
