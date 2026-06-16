from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.request import Request, urlopen

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers_exchange.json"
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "raw" / "index" / "us_listed_companies_sec.csv"
DEFAULT_USER_AGENT = "UCB JPM M&A research cindyfu@example.com"
LISTED_EXCHANGES = {"NYSE", "Nasdaq", "NYSE American"}


def download_sec_company_tickers(url: str, user_agent: str) -> pd.DataFrame:
    request = Request(url, headers={"User-Agent": user_agent})
    with urlopen(request, timeout=60) as response:
        payload = json.loads(response.read().decode("utf-8"))

    frame = pd.DataFrame(payload["data"], columns=payload["fields"])
    frame["sec_rank"] = range(1, len(frame) + 1)
    frame["ticker"] = frame["ticker"].astype(str).str.strip().str.upper().str.replace("-", ".", regex=False)
    frame["company_name"] = frame["name"].astype(str).str.strip()
    frame["exchange"] = frame["exchange"].astype(str).str.strip()
    frame["cik"] = frame["cik"].astype(str).str.zfill(10)
    frame = frame.loc[frame["exchange"].isin(LISTED_EXCHANGES)].copy()
    frame["source"] = "SEC company_tickers_exchange.json"
    frame["source_url"] = url
    return frame[["ticker", "company_name", "exchange", "cik", "sec_rank", "source", "source_url"]].sort_values("ticker")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download a US-listed company ticker master from SEC.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--url", default=SEC_TICKERS_URL)
    parser.add_argument("--user-agent", default=DEFAULT_USER_AGENT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    listed = download_sec_company_tickers(args.url, args.user_agent)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    listed.to_csv(args.output, index=False)
    print(f"Wrote {len(listed):,} US-listed companies to {args.output.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
