import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.stock_service import extract_seed_rows_from_csv  # noqa: E402


def main() -> None:
    csv_path = ROOT / "Comp_List.csv"
    out_path = ROOT / "backend" / "app" / "seed" / "stocks.seed.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    rows = extract_seed_rows_from_csv(csv_path.read_bytes())
    out_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Generated {len(rows)} seed rows at {out_path}")


if __name__ == "__main__":
    main()
