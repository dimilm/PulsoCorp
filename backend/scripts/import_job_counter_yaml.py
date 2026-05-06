"""One-shot conversion of the legacy ``11_JobCounter`` YAML configs.

Reads every ``config/sectors/*.yaml`` file in the standalone JobCounter project,
maps the free-form ``id`` to an ISIN where possible, and writes the result to
``backend/app/seed/job_sources.seed.json``. Both httpx- and Playwright-based
adapter types are emitted; the seed runs through the regular schema validator
on import, so a backend without the Playwright extra still loads the rows but
will refuse to scrape them until the extra is installed.

The seed file is read on first boot by ``seed_service.load_job_sources_seed_json``
exactly like ``stocks.seed.json``.

Usage::

    conda activate companytracker
    python scripts/import_job_counter_yaml.py \
        --source ../11_JobCounter/01_JobCounter/config \
        --target app/seed/job_sources.seed.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml

SUPPORTED_ADAPTERS = {
    "static_html",
    "json_get_path_int",
    "json_get_array_count",
    "json_post_path_int",
    "json_post_facet_sum",
    "playwright_api_fetch",
    "playwright_css_count",
    "playwright_text_regex",
}

# Mapping company-id -> ISIN. Curated by hand for the seed entries — extend
# this table as new YAML companies are added.
ISIN_MAPPING: dict[str, str] = {
    "ferrari": "NL0011585146",
    "mercedes": "DE0007100000",
    "volkswagen": "DE0007664039",
    "paypal": "US70450Y1038",
    "deutsche_bank": "DE0005140008",
    "philips": "NL0000009538",
    "kontron": "AT0000A0E9W5",
    "intel": "US4581401001",
    "amd": "US0079031078",
    "eventim": "DE0005470306",
    "nike": "US6541061031",
    "tui": "DE000TUAG505",
    "pfizer": "US7170811035",
    "kraftheinz": "US5007541064",
    "telekom": "DE0005557508",
    # Playwright-only entries from the legacy YAML.
    "boeing": "US0970231058",
    "carnival": "PA1436583006",
    "unitedhealth": "US91324P1021",
}


def _convert_company(company: dict[str, Any]) -> dict[str, Any] | None:
    """Project a YAML company onto the seed-file shape, or skip it.

    Returns ``None`` for unsupported adapters so the caller can keep counting
    skipped rows for the operator-facing summary.
    """
    adapter_type = company.get("adapter_type")
    if adapter_type not in SUPPORTED_ADAPTERS:
        return None

    company_id = company.get("id", "")
    return {
        "name": company.get("name", company_id),
        "portal_url": company.get("portal_url", ""),
        "adapter_type": adapter_type,
        "adapter_settings": company.get("settings", {}) or {},
        "is_active": bool(company.get("is_active", True)),
        "isin": ISIN_MAPPING.get(company_id),
    }


def _iter_yaml_companies(config_dir: Path):
    sectors_dir = config_dir / "sectors"
    if not sectors_dir.exists():
        raise FileNotFoundError(f"Sectors directory not found: {sectors_dir}")
    for yaml_file in sorted(sectors_dir.glob("*.yaml")):
        payload = yaml.safe_load(yaml_file.read_text(encoding="utf-8")) or {}
        for company in payload.get("companies", []) or []:
            yield yaml_file.stem, company


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        type=Path,
        required=True,
        help="Path to 11_JobCounter/01_JobCounter/config",
    )
    parser.add_argument(
        "--target",
        type=Path,
        default=Path("app/seed/job_sources.seed.json"),
        help="Output JSON file (default: app/seed/job_sources.seed.json)",
    )
    args = parser.parse_args()

    rows: list[dict[str, Any]] = []
    skipped: list[str] = []
    unmapped: list[str] = []

    for sector, company in _iter_yaml_companies(args.source):
        converted = _convert_company(company)
        company_id = company.get("id", "?")
        if converted is None:
            skipped.append(f"{sector}/{company_id} ({company.get('adapter_type')})")
            continue
        if converted["isin"] is None:
            unmapped.append(f"{sector}/{company_id}")
        rows.append(converted)

    args.target.parent.mkdir(parents=True, exist_ok=True)
    args.target.write_text(
        json.dumps(rows, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print(f"Wrote {len(rows)} job sources to {args.target}")
    if skipped:
        print(f"Skipped {len(skipped)} entries (unsupported adapter):")
        for entry in skipped:
            print(f"  - {entry}")
    if unmapped:
        print(f"WARNING: {len(unmapped)} entries without ISIN mapping:")
        for entry in unmapped:
            print(f"  - {entry}")


if __name__ == "__main__":
    main()
