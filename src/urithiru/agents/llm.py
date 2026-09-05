import json
import os
from importlib.resources import files
from string import Template

from google import genai
from google.genai import types

from urithiru.core.models import CATEGORIES, Belief
from urithiru.runtime.config import Config, GoogleConfig

EMBEDDING_DIMENSIONS = 768
EMBEDDING_BATCH = 128
REQUEST_TIMEOUT_MS = 120_000
REQUEST_ATTEMPTS = 3


def belief_schema() -> dict:
    counts = {
        "type": "object",
        "properties": {name: {"type": "integer"} for name in CATEGORIES},
        "required": list(CATEGORIES),
    }
    return {
        "type": "object",
        "properties": {"category_counts": counts, "rationale": {"type": "string"}},
        "required": ["category_counts", "rationale"],
    }


def prompt(name: str, values: dict) -> str:
    template = files("urithiru.agents").joinpath("prompts", f"{name}.txt").read_text(encoding="utf-8")
    return Template(template).substitute(values)


class LLM:
    def __init__(self, config: Config, seed: int):
        self.config, self.models, self.seed = config, config.models, seed
        self.model_names = {"prior": self.models.prior, "merge": self.models.deduplication}
        self.schemas = {
            "prior": belief_schema(),
            "merge": {
                "type": "object",
                "properties": {"is_same": {"type": "boolean"}},
                "required": ["is_same"],
            },
        }
        self.generation = self.client("global")
        credentialed = isinstance(config.options, GoogleConfig)
        self.embedding = self.client("us-central1") if credentialed else self.generation

    def client(self, location: str) -> genai.Client:
        http = types.HttpOptions(
            timeout=REQUEST_TIMEOUT_MS, retry_options=types.HttpRetryOptions(attempts=REQUEST_ATTEMPTS)
        )
        if isinstance(self.config.options, GoogleConfig):
            return genai.Client(
                enterprise=True,
                project=self.config.options.project,
                location=location,
                http_options=http,
            )
        return genai.Client(enterprise=True, api_key=os.environ["VERTEX_API_KEY"], http_options=http)

    def close(self) -> None:
        self.generation.close()
        if self.embedding is not self.generation:
            self.embedding.close()

    def prior(self, claim: str) -> Belief:
        text = prompt("prior", {"hypothesis": claim, "contract": json.dumps(self.schemas["prior"])})
        data = self.generate(text, "prior")
        return Belief(data["category_counts"], data["rationale"])

    def same_claim(self, left: str, right: str) -> bool:
        text = prompt("merge", {"left": left, "right": right, "contract": json.dumps(self.schemas["merge"])})
        value = self.generate(text, "merge")["is_same"]
        if type(value) is not bool:
            raise ValueError("Merge decision must be Boolean")
        return value

    def generate(self, text: str, role: str) -> dict:
        response = self.generation.models.generate_content(
            model=self.model_names[role],
            contents=text,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_json_schema=self.schemas[role],
                max_output_tokens=self.config.budget.max_output_tokens,
                temperature=self.models.temperature,
                seed=self.seed,
            ),
        )
        if response.text is None:
            raise RuntimeError(f"The {role} model returned no text")
        return json.loads(response.text)

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors = []
        for offset in range(0, len(texts), EMBEDDING_BATCH):
            response = self.embedding.models.embed_content(
                model=self.models.embedding,
                contents=texts[offset : offset + EMBEDDING_BATCH],
                config=types.EmbedContentConfig(output_dimensionality=EMBEDDING_DIMENSIONS),
            )
            if response.embeddings is None:
                raise RuntimeError("Missing embeddings")
            for item in response.embeddings:
                if item.values is None:
                    raise RuntimeError("Missing embeddings")
                vectors.append(list(item.values))
        return vectors
