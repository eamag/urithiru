"""The urithiru command line.

`app()` is the entry point. Each command below is one function whose signature *is*
the argument list and its defaults; the work itself lives in `runtime.runs`.
"""

import json
import sys
from pathlib import Path
from typing import Annotated

import typer

from urithiru.runtime.config import Config
from urithiru.runtime.files import DATA_SUFFIXES
from urithiru.runtime.runs import CloudRun, open_run, start, unpublish

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    pretty_exceptions_enable=False,
    help="Autonomous scientific discovery: agents propose hypotheses from your data, test them "
    "with code, seek independent evidence, and rank what survived.",
)

RUN = Annotated[
    str,
    typer.Argument(
        metavar="RUN",
        help="A local run directory, or the gs://bucket/prefix/run-id printed when the run started.",
    ),
]
DESTINATION = Annotated[Path, typer.Option("--output", help="A new, empty destination directory.")]


def show(result: dict) -> None:
    print(json.dumps(result, ensure_ascii=False, indent=2))


def stage_minutes(proposal: int | None, search: int | None, code: int | None, external: int | None) -> dict:
    """The stage limits the operator actually named; the profile supplies the rest."""
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
    ] = Path("configs/docker.toml"),
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
    """Start a new discovery run over one or more data files."""
    minutes = stage_minutes(proposal_minutes, search_minutes, code_minutes, external_minutes)
    show(start(Config.read(config, minutes), data, metadata or [], steps, seed, output))


@app.command()
def status(run: RUN) -> None:
    """Print a run's status, progress and last update time."""
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
    """Continue an interrupted or finished run, reusing every completed evaluation."""
    minutes = stage_minutes(proposal_minutes, search_minutes, code_minutes, external_minutes)
    show(open_run(run).resume(steps, minutes))


@app.command()
def cancel(run: RUN) -> None:
    """Ask a run to stop. The checkpoint and every completed evaluation are preserved."""
    show(open_run(run).cancel())


@app.command()
def logs(
    run: RUN,
    follow: Annotated[
        bool, typer.Option("--follow", "-f", help="Keep printing until the run reports finishing.")
    ] = False,
) -> None:
    """Print the run's event log: the same lines the orchestrator wrote, in order."""
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
    """Copy a run's checkpoint and event log where the web page can read them."""
    show(open_run(run).publish(output.resolve(), watch))


@app.command(name="unpublish")
def remove(
    run: RUN,
    output: Annotated[Path, typer.Option("--output", help="Where the web page looks for runs.")] = Path(
        "web/public/runs"
    ),
) -> None:
    """Remove a run's published copy. The run itself, and its bucket, are untouched."""
    show(unpublish(output.resolve(), run))


@app.command()
def export(run: RUN, output: DESTINATION) -> None:
    """Copy a run to a new directory and write the ranked report.json and report.md."""
    show(open_run(run).export(output.resolve()))


@app.command(hidden=True)
def orchestrate(run: Annotated[str, typer.Option("--run")]) -> None:
    """Cloud Run entry point: drive the discovery loop for a run in a bucket."""
    show(CloudRun(run).orchestrate())


def main() -> int:
    """A failure is one line on stderr, not a traceback; `urithiru` exits nonzero."""
    try:
        app()
    except KeyboardInterrupt:
        return 130
    except Exception as error:
        print(f"{type(error).__name__}: {error}", file=sys.stderr)
        return 1
    return 0
