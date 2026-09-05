from pathlib import Path

import pytest

from urithiru.cli import DEFAULT_DOCKER_PROFILE, DEFAULT_GOOGLE_PROFILE
from urithiru.runtime.config import (
    PLACEHOLDERS,
    Budget,
    Config,
    DockerConfig,
)


def test_bundled_profiles_match_repository_templates():
    assert DEFAULT_DOCKER_PROFILE.read_bytes() == Path("configs/docker.toml").read_bytes()
    assert DEFAULT_GOOGLE_PROFILE.read_bytes() == Path("configs/google.toml").read_bytes()
    assert isinstance(Config.read(DEFAULT_DOCKER_PROFILE).options, DockerConfig)


def valid_budget_dict():
    return {
        "proposal_minutes": 5,
        "search_minutes": 8,
        "code_minutes": 10,
        "external_minutes": 10,
        "grace_minutes": 4,
        "max_output_tokens": 4096,
        "input_mib": 50,
        "stage_attempts": 2,
    }


def valid_search_dict():
    return {
        "parallelism": 2,
        "branching_factor": 5,
        "top_k": 10,
        "uct_c": 1.414,
        "external_minimum_surprise": 0.3,
        "external_opportunity_weight": 1.0,
        "external_cost_weight": 0.1,
    }


def valid_models_dict():
    return {
        "agent": "gemini-3.7-flash",
        "prior": "gemini-3.7-flash",
        "deduplication": "gemini-3.5-flash-lite",
        "embedding": "text-embedding-005",
        "temperature": 0.7,
        "effort": "medium",
    }


def valid_docker_options():
    return {
        "image": "urithiru-sandbox:latest",
        "credential_volume": "agy_credentials",
    }


def valid_google_options():
    return {
        "project": "my-real-project",
        "region": "us-central1",
        "bucket": "my-real-bucket",
        "prefix": "runs",
        "orchestrator_job": "urithiru-job",
    }


def test_budget_positive_validation():
    bad_budget = Budget(
        proposal_minutes=0,
        search_minutes=8,
        code_minutes=10,
        external_minutes=10,
        grace_minutes=4,
        max_output_tokens=4096,
        input_mib=50,
        stage_attempts=2,
    )
    with pytest.raises(ValueError, match="Budget values must be positive"):
        bad_budget.validate()

    bad_budget2 = Budget(
        proposal_minutes=5,
        search_minutes=8,
        code_minutes=-2,
        external_minutes=10,
        grace_minutes=4,
        max_output_tokens=4096,
        input_mib=50,
        stage_attempts=2,
    )
    with pytest.raises(ValueError, match="Budget values must be positive"):
        bad_budget2.validate()


def test_budget_step_and_orchestrator_seconds():
    b = Budget(**valid_budget_dict())
    assert b.step_seconds() == (5 * 60 + 10 * 60 + 10 * 60) + (3 * 4 * 60)
    assert b.orchestrator_seconds(steps=3) == 3 * b.step_seconds() * 2


def test_budget_exceeds_job_limit():
    b = Budget(
        proposal_minutes=50000,
        search_minutes=8,
        code_minutes=10,
        external_minutes=10,
        grace_minutes=4,
        max_output_tokens=4096,
        input_mib=50,
        stage_attempts=2,
    )
    with pytest.raises(ValueError, match="One step exceeds the seven-day job limit"):
        b.validate()


def test_config_search_parameters_validation():
    with pytest.raises(ValueError, match="Parallelism must be 1-16"):
        Config.from_dict(
            {
                "runtime": "docker",
                "budget": valid_budget_dict(),
                "search": valid_search_dict() | {"parallelism": 0},
                "models": valid_models_dict(),
                "options": valid_docker_options(),
            }
        )

    with pytest.raises(ValueError, match="Retrieved-context count"):
        Config.from_dict(
            {
                "runtime": "docker",
                "budget": valid_budget_dict(),
                "search": valid_search_dict() | {"top_k": 500},
                "models": valid_models_dict(),
                "options": valid_docker_options(),
            }
        )

    with pytest.raises(ValueError, match="external-verification threshold"):
        Config.from_dict(
            {
                "runtime": "docker",
                "budget": valid_budget_dict(),
                "search": valid_search_dict() | {"external_minimum_surprise": 1.5},
                "models": valid_models_dict(),
                "options": valid_docker_options(),
            }
        )


def test_config_models_validation():
    with pytest.raises(ValueError, match="Model temperature must be between zero and two"):
        Config.from_dict(
            {
                "runtime": "docker",
                "budget": valid_budget_dict(),
                "search": valid_search_dict(),
                "models": valid_models_dict() | {"temperature": 3.0},
                "options": valid_docker_options(),
            }
        )

    with pytest.raises(ValueError, match="Model effort must be one of"):
        Config.from_dict(
            {
                "runtime": "docker",
                "budget": valid_budget_dict(),
                "search": valid_search_dict(),
                "models": valid_models_dict() | {"effort": "extreme"},
                "options": valid_docker_options(),
            }
        )

    with pytest.raises(ValueError, match="Model names must not be empty"):
        Config.from_dict(
            {
                "runtime": "docker",
                "budget": valid_budget_dict(),
                "search": valid_search_dict(),
                "models": valid_models_dict() | {"agent": ""},
                "options": valid_docker_options(),
            }
        )


def test_config_placeholder_rejection():
    for placeholder in PLACEHOLDERS:
        with pytest.raises(ValueError, match="Replace the placeholder configuration values"):
            Config.from_dict(
                {
                    "runtime": "google",
                    "budget": valid_budget_dict(),
                    "search": valid_search_dict(),
                    "models": valid_models_dict(),
                    "options": valid_google_options() | {"project": placeholder},
                }
            )

    with pytest.raises(ValueError, match="Replace the placeholder configuration values"):
        Config.from_dict(
            {
                "runtime": "google",
                "budget": valid_budget_dict(),
                "search": valid_search_dict(),
                "models": valid_models_dict(),
                "options": valid_google_options() | {"bucket": "your-private-bucket"},
            }
        )


def test_config_read_from_toml_and_minute_override(tmp_path):
    toml_content = """
runtime = "docker"

[budget]
proposal_minutes = 5
search_minutes = 8
code_minutes = 10
external_minutes = 10
grace_minutes = 4
max_output_tokens = 4096
input_mib = 50
stage_attempts = 2

[search]
parallelism = 2
branching_factor = 5
top_k = 10
uct_c = 1.414
external_minimum_surprise = 0.3
external_opportunity_weight = 1.0
external_cost_weight = 0.1

[models]
agent = "gemini-3.7-flash"
prior = "gemini-3.7-flash"
deduplication = "gemini-3.5-flash-lite"
embedding = "text-embedding-005"
temperature = 0.7
effort = "medium"

[options]
image = "urithiru-sandbox:latest"
credential_volume = "agy_credentials"
"""
    config_file = tmp_path / "config.toml"
    config_file.write_text(toml_content)

    cfg = Config.read(config_file, minutes={"code_minutes": 20, "external_minutes": 25})
    assert cfg.budget.code_minutes == 20
    assert cfg.budget.external_minutes == 25
    assert cfg.budget.proposal_minutes == 5
    assert cfg.runtime == "docker"
    assert isinstance(cfg.options, DockerConfig)
