"""Turn the 2025 road age-grading standards into the small JSON file the app reads.

    pip install openpyxl
    python scripts/build_age_standards.py MaleRoadStd2025.xlsx FemaleRoadStd2025.xlsx

The spreadsheets are the 2025 road running age standards by Alan Jones and Tom Bernhard,
approved by USATF Masters Long Distance Running (January 2025) and released into the
public domain (CC0): https://github.com/AlanLyttonJones/Age-Grade-Tables ("2025 Files").
Each standard is the best time expected at that age; age grade = standard / your time.
"""

import json
import sys
from pathlib import Path

import openpyxl

OUT = Path(__file__).resolve().parent.parent / "app" / "data" / "age_standards_2025.json"
# Column headings in the standards-in-seconds sheet -> the distance in metres the app uses.
DISTANCES = {"5 km": 5000, "10 km": 10000, "15 km": 15000, "H. Mar": 21097.5, "Marathon": 42195}


def read(path: str) -> dict[str, dict[str, int]]:
    book = openpyxl.load_workbook(path, read_only=True, data_only=True)
    # The seconds sheet is "AgeStdSec" in the men's file and "AgeStanSec" in the women's.
    sheet = next(
        ws for ws in book.worksheets if ws.title.startswith("AgeSt") and ws.title.endswith("Sec")
    )
    rows = list(sheet.values)
    headings = rows[1]
    columns = {name: headings.index(name) for name in DISTANCES}
    out: dict[str, dict[str, int]] = {name: {} for name in DISTANCES}
    for row in rows[4:]:
        if not isinstance(row[0], int):
            continue
        for name, col in columns.items():
            out[name][str(row[0])] = round(float(row[col]))
    return {str(DISTANCES[name]): ages for name, ages in out.items()}


def main() -> None:
    male, female = sys.argv[1:3]
    data = {
        "source": "2025 road age standards, Alan Jones and Tom Bernhard (USATF MLDR, CC0): "
        "https://github.com/AlanLyttonJones/Age-Grade-Tables",
        "male": read(male),
        "female": read(female),
    }
    OUT.write_text(json.dumps(data, separators=(",", ":")) + "\n")
    print(f"Wrote {OUT} ({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
