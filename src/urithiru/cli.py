import json
import sys
from importlib.resources import files
from pathlib import Path
from typing import Annotated

import typer

from urithiru.cloud.catalog import artifact, catalog, set_label
from urithiru.runtime.config import Config, GoogleConfig
from urithiru.runtime.files import DATA_SUFFIXES
from urithiru.runtime.runs import CloudRun, open_run, start, unpublish


def bundled_profile(name: str) -> Path:
    return Path(str(files("urithiru").joinpath("configs", name)))


DEFAULT_DOCKER_PROFILE = bundled_profile("docker.toml")
DEFAULT_GOOGLE_PROFILE = bundled_profile("google.toml")

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    pretty_exceptions_enable=False,
    help="Autonomous scientific exploration: agents propose hypotheses from your data, test them "
    "with code, seek external evidence, and rank the resulting leads.",
)

RUN = Annotated[
    str,
    typer.Argument(
        metavar="RUN",
        help="A local run directory, or the gs://bucket/prefix/run-id printed when the run started.",
    ),
]
DESTINATION = Annotated[Path, typer.Option("--output", help="A new, empty destination directory.")]
PROFILE = Annotated[
    Path,
    typer.Option("--config", help="The TOML profile naming the bucket these runs live in."),
]
RUN_ID = Annotated[
    str,
    typer.Option("--run", help="A catalog run id. Never a gs:// reference."),
]


def google(config: Path) -> GoogleConfig:
    options = Config.read(config).options
    if not isinstance(options, GoogleConfig):
        raise typer.BadParameter(f"{config} is not a Google Cloud profile")
    return options


def show(result: dict) -> None:
    print(json.dumps(result, ensure_ascii=False, indent=2))


def stage_minutes(proposal: int | None, search: int | None, code: int | None, external: int | None) -> dict:
    named = {
        "proposal_minutes": proposal,
        "search_minutes": search,
        "code_minutes": code,
        "external_minutes": external,
    }
    return {name: value for name, value in named.items() if value is not None}


@app.command()
def run(
    data: Annotated[
        list[Path],
        typer.Option("--data", help=f"Data files ({', '.join(sorted(DATA_SUFFIXES))}). Repeatable."),
    ],
    config: Annotated[
        Path, typer.Option(help="TOML profile choosing the runtime, models, budget and search settings.")
    ] = DEFAULT_DOCKER_PROFILE,
    steps: Annotated[int, typer.Option(help="How many hypotheses to evaluate.")] = 3,
    seed: Annotated[int, typer.Option(help="Seeds candidate selection and every model call.")] = 42,
    metadata: Annotated[
        list[Path] | None,
        typer.Option("--metadata", help="UTF-8 notes describing the data, passed to agents verbatim."),
    ] = None,
    output: Annotated[Path, typer.Option(help="Where local run directories are created.")] = Path("runs"),
    proposal_minutes: Annotated[int | None, typer.Option(help="Override the profile's stage limit.")] = None,
    search_minutes: Annotated[int | None, typer.Option(help="Override the literature stage's limit.")] = None,
    code_minutes: Annotated[int | None, typer.Option(help="Override the experiment stage's limit.")] = None,
    external_minutes: Annotated[int | None, typer.Option(help="Override the profile's limit.")] = None,
) -> None:
    minutes = stage_minutes(proposal_minutes, search_minutes, code_minutes, external_minutes)
    show(start(Config.read(config, minutes), data, metadata or [], steps, seed, output))


@app.command()
def status(run: RUN) -> None:
    show(open_run(run).status())


@app.command()
def resume(
    run: RUN,
    steps: Annotated[
        int | None,
        typer.Option(help="Raise the run's budget to this many hypotheses before continuing."),
    ] = None,
    proposal_minutes: Annotated[int | None, typer.Option(help="Raise the stage limit too.")] = None,
    search_minutes: Annotated[int | None, typer.Option(help="Raise the stage limit too.")] = None,
    code_minutes: Annotated[int | None, typer.Option(help="Raise the stage limit too.")] = None,
    external_minutes: Annotated[int | None, typer.Option(help="Raise the stage limit too.")] = None,
) -> None:
    minutes = stage_minutes(proposal_minutes, search_minutes, code_minutes, external_minutes)
    show(open_run(run).resume(steps, minutes))


@app.command()
def cancel(run: RUN) -> None:
    show(open_run(run).cancel())


@app.command()
def logs(
    run: RUN,
    follow: Annotated[
        bool, typer.Option("--follow", "-f", help="Keep printing until the run reports finishing.")
    ] = False,
) -> None:
    for line in open_run(run).logs(follow):
        print(line, flush=True)


@app.command()
def publish(
    run: RUN,
    output: Annotated[Path, typer.Option("--output", help="Where the web page looks for runs.")] = Path(
        "web/public/runs"
    ),
    watch: Annotated[
        bool, typer.Option("--watch", help="Keep publishing every few seconds until the run finishes.")
    ] = False,
) -> None:
    show(open_run(run).publish(output.resolve(), watch))


@app.command(name="unpublish")
def remove(
    run: RUN,
    output: Annotated[Path, typer.Option("--output", help="Where the web page looks for runs.")] = Path(
        "web/public/runs"
    ),
) -> None:
    show(unpublish(output.resolve(), run))


@app.command(name="catalog")
def list_runs(config: PROFILE = DEFAULT_GOOGLE_PROFILE) -> None:
    print(json.dumps(catalog(google(config)), ensure_ascii=False, indent=2))


@app.command(name="artifact")
def read_artifact(
    run: RUN_ID,
    name: Annotated[str, typer.Option("--name", help="run.json, mcts_state.json or events.jsonl.")],
    config: PROFILE = DEFAULT_GOOGLE_PROFILE,
) -> None:
    sys.stdout.write(artifact(google(config), run, name))


@app.command()
def label(
    run: RUN_ID,
    title: Annotated[str, typer.Option("--title", help="The operator's name for the run; empty clears it.")],
    config: PROFILE = DEFAULT_GOOGLE_PROFILE,
) -> None:
    show(set_label(google(config), run, title))


@app.command()
def export(run: RUN, output: DESTINATION) -> None:
    show(open_run(run).export(output.resolve()))


@app.command(hidden=True)
def orchestrate(run: Annotated[str, typer.Option("--run")]) -> None:
    show(CloudRun(run).orchestrate())


def main() -> int:
    try:
        app()
    except KeyboardInterrupt:
        return 130
    except Exception as error:
        print(f"{type(error).__name__}: {error}", file=sys.stderr)
        return 1
    return 0
