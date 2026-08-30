# Canadian aviation safety occurrence demo

This is a fixed 2005-2024 slice of the Transportation Safety Board of Canada's live
Aviation Safety Information System public dataset. It contains 20,301 unique
occurrences represented by 21,586 occurrence-category rows, linked to 24,560 aircraft
rows, 58,879 event/phase rows, 30,644 injury rows and 2,372 survivability rows through
`OccID` and, where applicable, `AcID`.

The occurrence table is not one row per occurrence: one occurrence can carry multiple
ICAO categories. Respect each table's grain before joining so records are not multiplied.

Treat every output as an observational **safety signal**, never a causal estimate.
Reporting, investigation depth, field completeness, operating exposure and coding
practice vary over time and across occurrence types. A blank means not applicable or
not populated. Do not infer rates without an exposure denominator, use post-occurrence
fields as predictors of earlier risk, or interpret missingness as absence.

Source: Transportation Safety Board of Canada, "Air occurrence data from January 1995
to present," https://open.canada.ca/data/en/dataset/a376864b-18f2-49d8-9b98-1b7268ffb3c0,
Open Government Licence - Canada. The live files were filtered by `OccDate` from
2005-01-01 through 2024-12-31; values and source table grain were otherwise preserved.

For independent verification, use the separate U.S. National Transportation Safety
Board aviation census at https://www.ntsb.gov/safety/data/pages/Data_Stats.aspx. Its
official bulk download is
https://data.ntsb.gov/avdata/FileDirectory/DownloadFile?fileID=C%3A%5Cavdata%5Cavall.zip;
`avall.zip` contains `avall.mdb`, and the analysis image provides `mdb-tables` and
`mdb-export`. Match constructs, population and inclusion rules explicitly before
comparing countries. Never treat a Canadian subset, mirror or derivative as independent.
