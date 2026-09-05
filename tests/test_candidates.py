import numpy as np
import pytest

from urithiru.core.candidates import CandidateSelector, canonicalize
from urithiru.core.tree import Node


class StubModel:
    def __init__(self, same_claim_decisions=None):
        self.same_decisions = same_claim_decisions or {}
        self.embed_calls = []
        self.same_calls = []

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.embed_calls.append(list(texts))
        vectors = []
        for text in texts:
            vec = np.zeros(8, dtype=np.float64)
            for char in text.lower():
                vec[ord(char) % 8] += 1.0
            norm = np.linalg.norm(vec)
            if norm > 0:
                vec = vec / norm
            vectors.append(vec.tolist())
        return vectors

    def same_claim(self, left: str, right: str) -> bool:
        self.same_calls.append((left, right))
        pair = (left, right)
        rev = (right, left)
        if pair in self.same_decisions:
            return self.same_decisions[pair]
        if rev in self.same_decisions:
            return self.same_decisions[rev]
        return False


def test_canonicalize():
    assert canonicalize("  Hypothesis   about  blood pressure.  ") == "Hypothesis about blood pressure."
    with pytest.raises(ValueError, match="Hypothesis cannot be empty"):
        canonicalize("   \n\t  ")


def test_candidate_selector_caching(tmp_path):
    model = StubModel()
    selector = CandidateSelector(model, tmp_path, top_k=2)

    vecs1 = selector.embed(["Claim A", "Claim B"])
    assert len(model.embed_calls) == 1
    assert (tmp_path / "artifacts" / "embeddings.json").exists()

    vecs2 = selector.embed(["Claim A", "Claim B"])
    assert len(model.embed_calls) == 1
    assert np.allclose(vecs1, vecs2)

    selector.embed(["Claim A", "Claim C"])
    assert len(model.embed_calls) == 2
    assert model.embed_calls[1] == ["Claim C"]


def test_candidate_selector_deduplicate_exact_and_semantic(tmp_path):
    model = StubModel(
        same_claim_decisions={
            ("Claim X", "Claim X."): True,
            ("Existing Claim", "Existing Claim Copy"): True,
        }
    )
    selector = CandidateSelector(model, tmp_path, top_k=2)

    verified = ["Existing Claim", "Different Claim"]
    candidates = [
        "  Existing Claim  ",
        "Existing Claim Copy",
        "New Unique Claim",
        "New Unique Claim",
        "Claim X",
        "Claim X.",
    ]

    duplicates = selector.deduplicate(candidates, verified)

    assert 0 in duplicates
    assert duplicates[0] == ("Existing Claim", "exact_duplicate")

    assert 3 in duplicates
    assert duplicates[3] == ("New Unique Claim", "exact_duplicate")


def test_candidate_selector_diversity(tmp_path):
    model = StubModel()
    selector = CandidateSelector(model, tmp_path, top_k=2)

    verified = ["Blood pressure increases with age.", "Dietary sodium affects hypertension."]
    candidates = [
        "Age correlates with systolic pressure.",
        "Quantum mechanics describes electron spin.",
    ]

    diversity_scores = selector.diversity(candidates, verified)
    assert len(diversity_scores) == 2
    assert diversity_scores[0] > diversity_scores[1]


def test_candidate_selector_retrieve(tmp_path):
    model = StubModel()
    selector = CandidateSelector(model, tmp_path, top_k=2)

    n1 = Node("n1", None, "Blood pressure in adults")
    n2 = Node("n2", None, "Sodium intake study")
    n3 = Node("n3", None, "Quantum computing algorithms")

    retrieved = selector.retrieve("Hypertension and blood pressure", [n1, n2, n3])
    assert len(retrieved) == 2
    assert n1 in retrieved
