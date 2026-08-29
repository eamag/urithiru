"""The research settings, the run's explicit time and size limits, and the runtime choice."""

import math
import tomllib
from dataclasses import dataclass, fields
from pathlib import Path

from urithiru.core.models import STAGES

PLACEHOLDERS = (
    "your-google-cloud-project-id",
    "your-private-bucket",
    "YOUR_PROJECT_ID",
    "YOUR_PRIVATE_BUCKET",
    "CHANGE_ME",
    "",
)
MEGABYTE = 1024 * 1024
EFFORTS = ("low", "medium", "high")
JOB_SECONDS_LIMIT = 604800


@dataclass(frozen=True)
class Budget:
    """Every wall-clock and size limit for a run, stated in minutes and MiB."""

    proposal_minutes: int
    verification_minutes: int
    external_minutes: int
    grace_minutes: int
    max_output_tokens: int
    input_mib: int
    stage_attempts: int

    def minutes(self, stage: str) -> int:
        return {
            "proposal": self.proposal_minutes,
            "verification": self.verification_minutes,
            "external": self.external_minutes,
        }[stage]

    def seconds(self, stage: str) -> int:
        return self.minutes(stage) * 60

    @property
    def grace_seconds(self) -> int:
        return self.grace_minutes * 60

    @property
    def input_bytes(self) -> int:
        return self.input_mib * MEGABYTE

    def step_seconds(self) -> int:
        """One MCTS step is a proposal, a verification and an external check, plus grace."""
        return sum(self.seconds(stage) + self.grace_seconds for stage in STAGES)

    def orchestrator_seconds(self, steps: int) -> int:
        return min(JOB_SECONDS_LIMIT, steps * self.step_seconds() * self.stage_attempts)

    def validate(self) -> None:
        nonpositive = [field.name for field in fields(self) if getattr(self, field.name) <= 0]
        if nonpositive:
            raise ValueError(f"Budget values must be positive: {', '.join(nonpositive)}")
        if self.step_seconds() > JOB_SECONDS_LIMIT:
            raise ValueError("One step exceeds the seven-day job limit")


@dataclass(frozen=True)
class SearchConfig:
    parallelism: int
    branching_factor: int
    top_k: int
    uct_c: float
    surprisal_threshold: float
    external_minimum_surprise: float
    external_opportunity_weight: float
    external_cost_weight: float


@dataclass(frozen=True)
class ModelConfig:
    agent: str
    prior: str
    deduplication: str
    embedding: str
    temperature: float
    effort: str


@dataclass(frozen=True)
class DockerConfig:
    image: str
    credential_volume: str
    agent_env: list[str]


@dataclass(frozen=True)
class GoogleConfig:
    project: str
    region: str
    bucket: str
    prefix: str
    orchestrator_job: str


OPTIONS = {"docker": DockerConfig, "google": GoogleConfig}


@dataclass(frozen=True)
class Config:
    runtime: str
    budget: Budget
    search: SearchConfig
    models: ModelConfig
    options: DockerConfig | GoogleConfig

    @classmethod
    def from_dict(cls, data: dict, minutes: dict[str, int] | None = None) -> "Config":
        runtime = data["runtime"]
        config = cls(
            runtime,
            Budget(**(data["budget"] | (minutes or {}))),
            SearchConfig(**data["search"]),
            ModelConfig(**data["models"]),
            OPTIONS[runtime](**data["options"]),
        )
        config.validate()
        return config

    @classmethod
    def read(cls, path: Path, minutes: dict[str, int] | None = None) -> "Config":
        if not path.is_file():
            raise FileNotFoundError(f"No configuration profile at {path}")
        return cls.from_dict(tomllib.loads(path.read_text(encoding="utf-8")), minutes)

    def validate(self) -> None:
        self.budget.validate()
        search = self.search
        if not 1 <= search.parallelism <= 16 or not 1 <= search.branching_factor <= 50:
            raise ValueError("Parallelism must be 1-16 and branching factor 1-50")
        if not 1 <= search.top_k <= 200:
            raise ValueError("Retrieved-context count must be between 1 and 200")
        if any(not math.isfinite(value) or value < 0 for value in vars(search).values()):
            raise ValueError("Search parameters must be finite and nonnegative")
        if not 0 <= search.surprisal_threshold <= 1 or not 0 <= search.external_minimum_surprise <= 1:
            raise ValueError("Surprise thresholds must be between zero and one")
        if not 0 <= self.models.temperature <= 2:
            raise ValueError("Model temperature must be between zero and two")
        if self.models.effort not in EFFORTS:
            raise ValueError(f"Model effort must be one of {', '.join(EFFORTS)}")
        blank = [
            field.name
            for field in fields(self.models)
            if isinstance(getattr(self.models, field.name), str)
            and not getattr(self.models, field.name).strip()
        ]
        if blank:
            raise ValueError(f"Model names must not be empty: {', '.join(blank)}")
        unset = [
            f"options.{field.name}"
            for field in fields(self.options)
            if isinstance(getattr(self.options, field.name), str)
            and getattr(self.options, field.name).strip() in PLACEHOLDERS
        ]
        if unset:
            raise ValueError(f"Replace the placeholder configuration values: {', '.join(unset)}")
