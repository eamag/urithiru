"""Render configuration only. This script never creates or executes cloud resources."""

import argparse
import os
import re
from pathlib import Path
from string import Template


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    values = {name: os.environ[name] for name in ("IMAGE_URI", "SERVICE_ACCOUNT")}
    if any(re.fullmatch(r"[A-Za-z0-9@._:/-]+", value) is None for value in values.values()):
        raise ValueError("Image and service-account identifiers contain invalid characters")
    arguments.output.mkdir(parents=True, exist_ok=True)
    for name in ("job",):
        template = Path(__file__).parent / f"{name}.yaml.template"
        with (arguments.output / f"{name}.yaml").open("x") as stream:
            stream.write(Template(template.read_text()).substitute(values))


if __name__ == "__main__":
    main()
