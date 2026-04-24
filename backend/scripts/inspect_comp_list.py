import csv
import re
from pathlib import Path


ISIN_RE = re.compile(r"^[A-Z]{2}[A-Z0-9]{10}$")


def main() -> None:
    csv_path = Path(__file__).resolve().parents[2] / "Comp_List.csv"
    with csv_path.open("r", encoding="utf-8-sig", errors="ignore", newline="") as f:
        rows = list(csv.reader(f, delimiter=";"))

    print(f"rows={len(rows)}")

    header_row_idx = None
    for idx, row in enumerate(rows):
        if any("Burggraben Depot" in cell for cell in row):
            header_row_idx = idx
            break

    print(f"header_row_idx={header_row_idx}")
    if header_row_idx is not None:
        row = rows[header_row_idx]
        print(f"header_len={len(row)}")
        for i, cell in enumerate(row):
            c = cell.strip()
            if c:
                if any(
                    key in c
                    for key in [
                        "ISIN",
                        "Aktie",
                        "Burggraben Depot",
                        "Invest  Depot",
                        "Summe Anzahl Tranchen",
                        "Meinung",
                        "Sektor",
                    ]
                ):
                    print(i, repr(c))

    for row in rows:
        isins = [cell.strip().upper() for cell in row if ISIN_RE.match(cell.strip().upper())]
        if isins:
            print("first_data_len=", len(row))
            for i, cell in enumerate(row):
                c = cell.strip()
                if c:
                    print(i, repr(c[:120]))
            break


if __name__ == "__main__":
    main()
