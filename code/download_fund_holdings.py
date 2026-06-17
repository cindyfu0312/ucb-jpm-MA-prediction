"""Download merger-arb fund / ETF holdings from SEC N-PORT filings (free, no key).

Registered funds file portfolio holdings monthly as NPORT-P on EDGAR. This pulls the
dedicated merger-arbitrage funds' holdings -- including long/short hedge legs -- the raw
material for the merger-arb fund-scoring track.

Discovery is CIK-anchored: each fund query is filtered to the fund's own registrant CIK so
funds-of-funds that merely *hold* a merger-arb ETF are excluded. Filings are sorted by EDGAR
filing date (most recent first), and that filing date is captured as `available_date` --
distinct from `report_date` (portfolio period-end). N-PORT-P is public ~60 days AFTER the
period-end, so any point-in-time panel join must use available_date, not report_date.

  data/raw/funds/fund_holdings.csv  # one row per (fund, period, holding)
  data/raw/funds/fund_manifest.csv  # one row per N-PORT filing
"""
from __future__ import annotations

import argparse
import json
import os
import re
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urlencode

import pandas as pd

from _sec_http import http_get


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "raw" / "funds"
EFTS_URL = "https://efts.sec.gov/LATEST/search-index"
ARCHIVE = "https://www.sec.gov/Archives/edgar/data"

# Dedicated merger-arb / event-driven funds: (full-text phrase, registrant CIK).
# The CIK anchors the search to the fund's OWN filings (drops funds-of-funds holding the ETF).
# cik=None keeps all CIKs and relies on the series-name filter (for multi-registrant families).
DEFAULT_FUNDS = [
    ("IQ Merger Arbitrage", "0001415995"),         # MNA  (IndexIQ ETF Trust)
    ("ProShares Merger", "0001174610"),            # MRGR (ProShares Trust)
    ("AltShares Merger Arbitrage", "0001779306"),  # ARB  (AltShares Trust)
    ("AltShares Event-Driven", "0001779306"),
    ("Merger Fund", None),                          # MERFX (Westchester / Virtus -- multiple CIKs)
    ("Gabelli Merger Arbitrage", None),
]
HOLDING_FIELDS = ("name", "title", "cusip", "balance", "units", "curCd",
                  "valUSD", "pctVal", "payoffProfile", "assetCat", "issuerCat")


def _ln(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def efts_search(query: str, cik: str | None, max_filings: int, sleep: float) -> list[tuple]:
    """Return [(cik, accession, name, file_date)] of a fund's NPORT-P filings, most-recent first.

    EDGAR full-text search ranks by relevance, not date, so we collect hits and sort by the
    file_date carried in each hit before taking the most recent `max_filings`.
    """
    hits: list[tuple] = []
    frm = 0
    while True:
        params = urlencode({"q": f'"{query}"', "forms": "NPORT-P", "from": frm})
        data = json.loads(http_get(f"{EFTS_URL}?{params}").decode("utf-8", "replace"))
        page = data.get("hits", {}).get("hits", [])
        if not page:
            break
        for h in page:
            src = h.get("_source", {})
            ciks = src.get("ciks", [])
            if cik and cik not in ciks:
                continue
            names = src.get("display_names", [])
            hits.append((ciks[0] if ciks else "", h["_id"].split(":")[0],
                         names[0] if names else "", src.get("file_date")))
        frm += len(page)
        if frm >= data["hits"]["total"]["value"] or frm >= 200:
            break
        time.sleep(sleep)
    hits.sort(key=lambda r: r[3] or "", reverse=True)
    return hits[:max_filings]


def parse_nport(xml_bytes: bytes) -> tuple[dict, list[dict]]:
    root = ET.fromstring(xml_bytes)
    header: dict = {}
    for el in root.iter():
        ln = _ln(el.tag)
        if ln in ("seriesName", "repPdDate", "totAssets") and el.text and ln not in header:
            header[ln] = el.text.strip()
    holdings: list[dict] = []
    for sec in root.iter():
        if _ln(sec.tag) != "invstOrSec":
            continue
        row: dict = {}
        for child in sec:
            ln = _ln(child.tag)
            if ln in HOLDING_FIELDS:
                row[ln] = (child.text or "").strip()
            elif ln == "identifiers":
                for idel in child:
                    if _ln(idel.tag) in ("isin", "ticker"):
                        row[_ln(idel.tag)] = idel.get("value", "")
        holdings.append(row)
    return header, holdings


def build(args) -> tuple[pd.DataFrame, pd.DataFrame]:
    series_re = re.compile(args.series_filter, re.I) if args.series_filter else None
    filings: dict[tuple[str, str], tuple] = {}
    for query, cik in DEFAULT_FUNDS:
        hits = efts_search(query, cik, args.max_filings, args.sleep)
        print(f"  {query!r} (cik={cik or 'any'}): {len(hits)} NPORT-P filings"
              + ("   <- WARNING: none found" if not hits else ""))
        for c, accn, name, fdate in hits:
            filings.setdefault((c, accn), (name, fdate))
        time.sleep(args.sleep)
    print(f"Fetching {len(filings)} unique N-PORT filings...")

    rows: list[dict] = []
    manifest: list[dict] = []
    skipped = 0
    for i, ((cik, accn), (name, file_date)) in enumerate(filings.items(), start=1):
        url = f"{ARCHIVE}/{int(cik)}/{accn.replace('-', '')}/primary_doc.xml"
        try:
            header, holdings = parse_nport(http_get(url))
        except Exception as exc:  # noqa: BLE001
            if args.verbose:
                print(f"  ! {name} {accn}: {exc}")
            continue
        fund = header.get("seriesName") or name
        if series_re and not series_re.search(fund or ""):
            skipped += 1
            continue
        manifest.append({"cik": cik, "accession": accn, "fund": fund,
                         "report_date": header.get("repPdDate"), "available_date": file_date,
                         "total_assets": header.get("totAssets"), "n_holdings": len(holdings)})
        for h in holdings:
            rows.append({"cik": cik, "fund": fund, "report_date": header.get("repPdDate"),
                         "available_date": file_date, **h})
        if i % 10 == 0 or i == len(filings):
            print(f"  {i}/{len(filings)} filings parsed ({len(rows):,} holdings, {skipped} off-target)")
        time.sleep(args.sleep)

    return pd.DataFrame(rows), pd.DataFrame(manifest)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Download merger-arb fund holdings from SEC N-PORT.")
    p.add_argument("--max-filings", type=int, default=8, help="Max NPORT-P filings per fund (most recent).")
    p.add_argument("--series-filter", default=r"merger|arbitrage|event.?driven",
                   help="Keep only filings whose fund/series name matches this regex (set '' to keep all).")
    p.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    p.add_argument("--sleep", type=float, default=0.2, help="Seconds between SEC requests.")
    p.add_argument("--verbose", action="store_true")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    holdings, manifest = build(args)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    hp = args.output_dir / "fund_holdings.csv"
    mp = args.output_dir / "fund_manifest.csv"
    holdings.to_csv(hp, index=False)
    manifest.to_csv(mp, index=False)

    print(f"\nWrote {len(holdings):,} holdings across {len(manifest)} filings")
    if not manifest.empty:
        print("  funds:", ", ".join(sorted(manifest["fund"].dropna().unique())[:8]))
    if not holdings.empty and "payoffProfile" in holdings.columns:
        print("  long/short:", holdings["payoffProfile"].value_counts().to_dict())
    print(f"  -> {os.path.relpath(hp, PROJECT_ROOT)}")
    print(f"  -> {os.path.relpath(mp, PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
