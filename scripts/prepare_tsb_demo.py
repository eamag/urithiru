"""Freeze the live Canadian TSB aviation tables to the 2005-2024 demo window.

Raw downloads and prepared data belong under `.work/`, which is ignored by Git. The
output keeps the five tables linked by OccID and writes the official dictionary as
UTF-8 metadata. It does not join the tables or turn observational signals into causes.
"""

import argparse
import csv
import hashlib
import json
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

DATASET_PAGE = "https://open.canada.ca/data/en/dataset/a376864b-18f2-49d8-9b98-1b7268ffb3c0"
NTSB_PAGE = "https://www.ntsb.gov/safety/data/pages/Data_Stats.aspx"
NTSB_DOWNLOAD = "https://data.ntsb.gov/avdata/FileDirectory/DownloadFile?fileID=C%3A%5Cavdata%5Cavall.zip"
RESOURCES = {
    "occurrence.csv": "https://www.bst.gc.ca/sites/default/files/stats/ASISdb_MDOTW_VW_OCCURRENCE_PUBLIC.csv",
    "aircraft.csv": "https://www.bst.gc.ca/sites/default/files/stats/ASISdb_MDOTW_VW_AIRCRAFT_PUBLIC.csv",
    "events_and_phases.csv": "https://www.bst.gc.ca/sites/default/files/stats/ASISdb_MDOTW_VW_EVENTS_AND_PHASES_PUBLIC.csv",
    "injuries.csv": "https://www.bst.gc.ca/sites/default/files/stats/ASISdb_MDOTW_VW_INJURIES_PUBLIC.csv",
    "survivability.csv": "https://www.bst.gc.ca/sites/default/files/stats/ASISdb_MDOTW_VW_SURVIVABILITY_PUBLIC.csv",
    "data_dictionary.csv": "https://www.bst.gc.ca/sites/default/files/2025-10/MDOTW-ASIS-Master-dataset-inventory-and-dictionary-ENG.csv",
}
CHILD_KEYS = {
    "aircraft.csv": "occid",
    "events_and_phases.csv": "OccID",
    "injuries.csv": "occID",
    "survivability.csv": "OccID",
}
START_YEAR = 2005
END_YEAR = 2024


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def clean_header(header: list[str]) -> list[str]:
    """Remove the duplicated Base64/BOM prefix currently shipped on the first field."""
    return [name.removeprefix("77u/").removeprefix("\ufeff") for name in header]


def download(raw: Path) -> None:
    raw.mkdir(parents=True, exist_ok=True)
    for name, url in RESOURCES.items():
        target = raw / name
        request = urllib.request.Request(url, headers={"User-Agent": "urithiru-tsb-demo/1"})
        with urllib.request.urlopen(request, timeout=120) as response, target.open("wb") as stream:
            while chunk := response.read(1024 * 1024):
                stream.write(chunk)


def copy_occurrences(source: Path, target: Path) -> tuple[set[str], int, int]:
    identifiers: set[str] = set()
    rows = 0
    with (
        source.open(encoding="utf-8", newline="") as incoming,
        target.open("w", encoding="utf-8", newline="") as outgoing,
    ):
        reader = csv.reader(incoming)
        header = clean_header(next(reader))
        writer = csv.writer(outgoing, lineterminator="\n")
        writer.writerow(header)
        id_index, date_index = header.index("OccID"), header.index("OccDate")
        for row in reader:
            year = int(row[date_index][:4])
            if START_YEAR <= year <= END_YEAR:
                writer.writerow(row)
                identifiers.add(row[id_index])
                rows += 1
    return identifiers, rows, len(header)


def copy_children(source: Path, target: Path, key: str, identifiers: set[str]) -> tuple[int, int, int]:
    rows, linked = 0, set()
    with (
        source.open(encoding="utf-8", newline="") as incoming,
        target.open("w", encoding="utf-8", newline="") as outgoing,
    ):
        reader = csv.reader(incoming)
        header = clean_header(next(reader))
        writer = csv.writer(outgoing, lineterminator="\n")
        writer.writerow(header)
        key_index = header.index(key)
        for row in reader:
            if row[key_index] in identifiers:
                writer.writerow(row)
                linked.add(row[key_index])
                rows += 1
    return rows, len(linked), len(header)


def copy_dictionary(source: Path, target: Path) -> tuple[int, int]:
    rows = 0
    with (
        source.open(encoding="cp1252", newline="") as incoming,
        target.open("w", encoding="utf-8", newline="") as outgoing,
    ):
        reader = csv.reader(incoming)
        header = clean_header(next(reader))
        writer = csv.writer(outgoing, lineterminator="\n")
        writer.writerow(header)
        for row in reader:
            writer.writerow(row)
            rows += 1
    return rows, len(header)


def file_record(raw: Path, prepared: Path, rows: int, columns: int, occurrences: int) -> dict:
    return {
        "rows": rows,
        "columns": columns,
        "unique_occurrences": occurrences,
        "raw_bytes": raw.stat().st_size,
        "raw_sha256": digest(raw),
        "prepared_bytes": prepared.stat().st_size,
        "prepared_sha256": digest(prepared),
        "source": RESOURCES[raw.name],
    }


def write_metadata(output: Path, records: dict, unique_occurrences: int) -> None:
    occurrence_rows = records["occurrence.csv"]["rows"]
    text = f"""# Canadian aviation safety occurrence demo

This is a fixed 2005-2024 slice of the Transportation Safety Board of Canada's live
Aviation Safety Information System public dataset: {unique_occurrences:,} unique
occurrences represented by {occurrence_rows:,} occurrence-category rows, linked to
aircraft, event/phase, injury and survivability tables through `OccID` (and `AcID`
where applicable). The occurrence table is not one row per occurrence: one occurrence
can carry multiple ICAO categories. Joining without respecting table grain will
multiply records.

Treat outputs as observational **safety signals**, never causal estimates. Reporting,
investigation depth, field completeness, operating exposure and coding practice vary
over time and across occurrence types. A blank means not applicable or not populated.
Do not use post-occurrence fields as predictors of earlier risk, infer rates without an
exposure denominator, or interpret missingness as absence.

Source: Transportation Safety Board of Canada, "Air occurrence data from January 1995
to present," {DATASET_PAGE}. Open Government Licence - Canada. The live files were
filtered by `OccDate` from 2005-01-01 through 2024-12-31; values and table grain were
otherwise preserved. `data_dictionary.csv` contains the official field definitions.

For an external check, use the separate U.S. National Transportation Safety Board
aviation corpus at {NTSB_PAGE}. Match constructs and inclusion rules explicitly before
comparing countries. Its official bulk download is {NTSB_DOWNLOAD}; the ZIP contains
`avall.mdb`, and the analysis image provides `mdb-tables` and `mdb-export`. Never treat
a Canadian subset, mirror or derivative as independent.
"""
    (output / "metadata.md").write_text(text, encoding="utf-8")


def prepare(raw: Path, output: Path) -> dict:
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite existing snapshot: {output}")
    missing = [raw / name for name in RESOURCES if not (raw / name).is_file()]
    if missing:
        raise FileNotFoundError(f"Missing raw resources: {', '.join(map(str, missing))}")
    output.mkdir(parents=True)

    occurrence_target = output / "occurrence.csv"
    identifiers, rows, columns = copy_occurrences(raw / "occurrence.csv", occurrence_target)
    records = {
        "occurrence.csv": file_record(
            raw / "occurrence.csv", occurrence_target, rows, columns, len(identifiers)
        )
    }
    for name, key in CHILD_KEYS.items():
        target = output / name
        child_rows, linked, child_columns = copy_children(raw / name, target, key, identifiers)
        records[name] = file_record(raw / name, target, child_rows, child_columns, linked)

    dictionary_target = output / "data_dictionary.csv"
    dictionary_rows, dictionary_columns = copy_dictionary(raw / "data_dictionary.csv", dictionary_target)
    records["data_dictionary.csv"] = file_record(
        raw / "data_dictionary.csv",
        dictionary_target,
        dictionary_rows,
        dictionary_columns,
        0,
    )
    write_metadata(output, records, len(identifiers))

    manifest = {
        "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "window": {"start": f"{START_YEAR}-01-01", "end": f"{END_YEAR}-12-31"},
        "source_dataset": DATASET_PAGE,
        "license": "Open Government Licence - Canada",
        "external_holdout": NTSB_PAGE,
        "external_holdout_download": NTSB_DOWNLOAD,
        "external_data_included": False,
        "unique_occurrences": len(identifiers),
        "files": records,
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", type=Path, default=Path(".work/tsb/raw"))
    parser.add_argument("--output", type=Path, default=Path(".work/tsb/tsb_aviation_2005_2024"))
    parser.add_argument("--download", action="store_true", help="Refresh the six official files first")
    arguments = parser.parse_args()
    if arguments.download:
        download(arguments.raw)
    print(json.dumps(prepare(arguments.raw, arguments.output), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
