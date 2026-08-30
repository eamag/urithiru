"""Freeze the NHANES August 2021 - August 2023 public release into the demo bundle.

Raw downloads and prepared data belong under `.work/`, which is ignored by Git. The
output keeps eight tables linked by SEQN and writes the official codebooks as a single
UTF-8 dictionary. It does not join the tables, apply survey weights, or turn
cross-sectional associations into causes.
"""

import argparse
import csv
import hashlib
import json
import re
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
from bs4 import BeautifulSoup

CYCLE = "August 2021 - August 2023"
BASE = "https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2021/DataFiles"
DATASET_PAGE = "https://wwwn.cdc.gov/nchs/nhanes/continuousnhanes/default.aspx?Cycle=2021-2023"
SPINE = "demographics.csv"
TABLES = {
    SPINE: ("DEMO_L", "Demographics, interview and examination sample weights, survey design"),
    "body_measures.csv": ("BMX_L", "Body measures: weight, height, BMI, waist and arm circumference"),
    "blood_pressure.csv": ("BPXO_L", "Oscillometric blood pressure, three readings per participant"),
    "glycohemoglobin.csv": ("GHB_L", "Glycohemoglobin (HbA1c), laboratory"),
    "hdl_cholesterol.csv": ("HDL_L", "Direct HDL cholesterol, laboratory"),
    "sleep.csv": ("SLQ_L", "Sleep disorders questionnaire: usual sleep and wake times, trouble sleeping"),
    "physical_activity.csv": ("PAQ_L", "Physical activity questionnaire, global physical activity items"),
    "depression_phq9.csv": ("DPQ_L", "Patient Health Questionnaire depression screener, nine items"),
}
DICTIONARY = "data_dictionary.csv"
KEY = "SEQN"
USER_AGENT = "urithiru-nhanes-demo/1"


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def fetch(url: str, target: Path) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=180) as response, target.open("wb") as stream:
        while chunk := response.read(1024 * 1024):
            stream.write(chunk)


def download(raw: Path) -> None:
    raw.mkdir(parents=True, exist_ok=True)
    for component, _ in TABLES.values():
        for suffix in (".xpt", ".htm"):
            target = raw / f"{component}{suffix}"
            if not target.is_file():
                fetch(f"{BASE}/{component}{suffix}", target)


def read_transport(path: Path) -> pd.DataFrame:
    """SAS transport carries numerics as floats and character fields as bytes."""
    frame = pd.read_sas(path, format="xport")
    for column in frame.columns:
        if frame[column].dtype == object:
            frame[column] = frame[column].str.decode("utf-8", errors="replace").str.strip()
    frame[KEY] = frame[KEY].astype("int64")
    return frame


def write_table(frame: pd.DataFrame, target: Path) -> None:
    """Integral floats are written without a trailing `.0`; SAS has no integer type."""
    output = frame.copy()
    for column in output.columns:
        values = output[column]
        if pd.api.types.is_float_dtype(values) and values.dropna().mod(1).eq(0).all():
            output[column] = values.astype("Int64")
    output.to_csv(target, index=False, lineterminator="\n")


def parse_codebook(path: Path, table: str) -> list[dict[str, str]]:
    """One row per documented code, or a single row for a variable with no code table."""
    soup = BeautifulSoup(path.read_text(encoding="utf-8", errors="replace"), "html.parser")
    rows: list[dict[str, str]] = []
    for block in soup.select("div.pagebreak"):
        title = block.select_one("h3.vartitle")
        if title is None:
            continue
        definitions = {
            term.get_text(strip=True).rstrip(":"): value.get_text(" ", strip=True)
            for term, value in zip(block.select("dl dt"), block.select("dl dd"), strict=False)
        }
        common = {
            "table": table,
            "variable": title.get("id") or definitions.get("Variable Name", ""),
            "label": definitions.get("SAS Label", ""),
            "english_text": re.sub(r"\s+", " ", definitions.get("English Text", "")),
            "target": re.sub(r"\s+", " ", definitions.get("Target", "")),
        }
        values = block.select_one("table.values")
        cells = values.select("tbody tr") if values else []
        if not cells:
            rows.append({**common, "code": "", "code_description": ""})
            continue
        for row in cells:
            columns = [cell.get_text(" ", strip=True) for cell in row.select("td")]
            if len(columns) >= 2:
                rows.append({**common, "code": columns[0], "code_description": columns[1]})
    return rows


def prepare(raw: Path, output: Path) -> dict:
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite existing snapshot: {output}")
    missing = [
        raw / f"{component}{suffix}"
        for component, _ in TABLES.values()
        for suffix in (".xpt", ".htm")
        if not (raw / f"{component}{suffix}").is_file()
    ]
    if missing:
        raise FileNotFoundError(f"Missing raw resources: {', '.join(map(str, missing))}")
    output.mkdir(parents=True)

    spine_component = TABLES[SPINE][0]
    spine = read_transport(raw / f"{spine_component}.xpt")
    participants = set(spine[KEY])

    records: dict[str, dict] = {}
    dictionary: list[dict[str, str]] = []
    for name, (component, description) in TABLES.items():
        source = raw / f"{component}.xpt"
        frame = spine if name == SPINE else read_transport(source)
        frame = frame[frame[KEY].isin(participants)]
        target = output / name
        write_table(frame, target)
        dictionary.extend(parse_codebook(raw / f"{component}.htm", name))
        records[name] = {
            "component": component,
            "description": description,
            "rows": int(len(frame)),
            "columns": int(frame.shape[1]),
            "participants": int(frame[KEY].nunique()),
            "raw_bytes": source.stat().st_size,
            "raw_sha256": digest(source),
            "prepared_bytes": target.stat().st_size,
            "prepared_sha256": digest(target),
            "source": f"{BASE}/{component}.xpt",
            "codebook": f"{BASE}/{component}.htm",
        }

    dictionary_target = output / DICTIONARY
    with dictionary_target.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=["table", "variable", "label", "english_text", "target", "code", "code_description"],
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(dictionary)
    records[DICTIONARY] = {
        "component": "codebooks",
        "description": "Official NHANES codebooks for the eight tables, one row per documented code",
        "rows": len(dictionary),
        "columns": 7,
        "participants": 0,
        "prepared_bytes": dictionary_target.stat().st_size,
        "prepared_sha256": digest(dictionary_target),
        "source": DATASET_PAGE,
    }

    write_metadata(output, records, len(participants))
    manifest = {
        "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "cycle": CYCLE,
        "source_dataset": DATASET_PAGE,
        "license": "Public domain (U.S. Government work, 17 U.S.C. 105)",
        "external_data_included": False,
        "participants": len(participants),
        "key": KEY,
        "files": records,
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def write_metadata(output: Path, records: dict, participants: int) -> None:
    """Only what the files and the shipped codebook cannot tell an agent themselves.

    Table grain, missing-value codes, weight variables and the cross-sectional caveat are
    all documented per variable in the official codebook that ships beside the data, so
    restating them here would be handing the agent an analysis plan rather than a dataset.
    """
    text = f"""# NHANES {CYCLE}

The U.S. National Health and Nutrition Examination Survey public release for the
{CYCLE} cycle. Centers for Disease Control and Prevention, National Center for Health
Statistics: {DATASET_PAGE}. Public domain (U.S. Government work, 17 U.S.C. 105).

`{DICTIONARY}` is the official NHANES codebook for the other tables: one row per
documented code, carrying each variable's SAS label, the question text read to the
participant, the eligible target population, and the meaning of every coded value.

Prepared from the official SAS transport releases with no recoding, filtering or
imputation, except that each table is restricted to the {participants:,} participants
present in `demographics.csv`.

Any external check must be independent of this release: not another NHANES cycle, not a
mirror or derivative of these files, and not the same collection campaign published
elsewhere.
"""
    (output / "metadata.md").write_text(text, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", type=Path, default=Path(".work/nhanes/raw"))
    parser.add_argument("--output", type=Path, default=Path(".work/nhanes/nhanes_2021_2023"))
    parser.add_argument("--skip-download", action="store_true")
    arguments = parser.parse_args()

    if not arguments.skip_download:
        download(arguments.raw)
    manifest = prepare(arguments.raw, arguments.output)
    for name, record in manifest["files"].items():
        print(f"{name:<24} {record['rows']:>7,} rows  {record['columns']:>3} columns")
    print(f"\n{manifest['participants']:,} participants -> {arguments.output}")


if __name__ == "__main__":
    main()
