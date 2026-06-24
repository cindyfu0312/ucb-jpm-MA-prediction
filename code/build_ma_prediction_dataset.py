from __future__ import annotations

import argparse
import os
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_UNIVERSE = PROJECT_ROOT / "data" / "raw" / "index" / "us_listed_companies_sec.csv"
DEFAULT_PRICES = PROJECT_ROOT / "data" / "raw" / "market" / "daily_prices.csv"
DEFAULT_EVENTS = PROJECT_ROOT / "data" / "raw" / "events" / "ma_events.csv"
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "interim" / "ma_prediction_panel.csv"
DEFAULT_COVERAGE = PROJECT_ROOT / "reports" / "week1" / "ma_prediction_data_coverage.csv"


def standardize_ticker(series: pd.Series) -> pd.Series:
    out = series.astype("string").str.strip().str.upper()
    out = out.mask(out.isin(["", "NAN", "NONE", "<NA>"]))
    return out


def load_universe(path: Path) -> pd.DataFrame:
    universe = pd.read_csv(path)
    universe["ticker"] = standardize_ticker(universe["ticker"])
    keep_cols = [col for col in ["ticker", "company_name", "exchange", "sector", "cik"] if col in universe.columns]
    return universe[keep_cols].dropna(subset=["ticker"]).drop_duplicates("ticker")


def load_prices(path: Path) -> pd.DataFrame:
    prices = pd.read_csv(path, parse_dates=["date"])
    prices["ticker"] = standardize_ticker(prices["ticker"])
    for col in ["open", "high", "low", "close", "volume", "ret"]:
        if col in prices.columns:
            prices[col] = pd.to_numeric(prices[col], errors="coerce")

    prices = prices.dropna(subset=["date", "ticker", "close"]).sort_values(["ticker", "date"])
    if "ret" not in prices.columns or prices["ret"].isna().all():
        prices["ret"] = prices.groupby("ticker")["close"].pct_change()
    prices["dollar_volume"] = prices["close"].abs() * prices["volume"]
    return prices


def load_events(path: Path) -> pd.DataFrame:
    events = pd.read_csv(path, parse_dates=["announcement_date", "close_date"])
    events["target_ticker"] = standardize_ticker(events["target_ticker"])
    events["acquirer_ticker"] = standardize_ticker(events["acquirer_ticker"])
    events["deal_value_usd"] = pd.to_numeric(events["deal_value_usd"], errors="coerce")
    return events.dropna(subset=["announcement_date", "target_ticker"])


def add_market_features(prices: pd.DataFrame) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for _, group in prices.groupby("ticker", sort=False):
        group = group.sort_values("date").copy()
        group["ret_5d"] = group["close"].pct_change(5)
        group["ret_20d"] = group["close"].pct_change(20)
        group["ret_60d"] = group["close"].pct_change(60)
        group["vol_20d"] = group["ret"].rolling(20, min_periods=10).std()
        group["vol_60d"] = group["ret"].rolling(60, min_periods=20).std()
        group["avg_dollar_volume_20d"] = group["dollar_volume"].rolling(20, min_periods=10).mean()
        volume_mean_20d = group["volume"].rolling(20, min_periods=10).mean()
        volume_std_20d = group["volume"].rolling(20, min_periods=10).std()
        group["volume_zscore_20d"] = (group["volume"] - volume_mean_20d) / volume_std_20d
        rolling_high_60d = group["close"].rolling(60, min_periods=20).max()
        group["drawdown_60d"] = group["close"] / rolling_high_60d - 1
        frames.append(group)
    return pd.concat(frames, ignore_index=True)


def select_as_of_rows(features: pd.DataFrame, frequency: str) -> pd.DataFrame:
    if frequency == "daily":
        return features.rename(columns={"date": "as_of_date"})
    if frequency != "month_end":
        raise ValueError("frequency must be 'daily' or 'month_end'")

    out = features.copy()
    out["as_of_month"] = out["date"].dt.to_period("M")
    out = out.sort_values(["ticker", "date"]).groupby(["ticker", "as_of_month"], as_index=False).tail(1)
    out = out.drop(columns=["as_of_month"]).rename(columns={"date": "as_of_date"})
    return out


def event_table(events: pd.DataFrame, role_col: str) -> dict[str, list[pd.Timestamp]]:
    role_events = events.dropna(subset=[role_col, "announcement_date"])
    role_events = role_events[[role_col, "announcement_date"]].rename(columns={role_col: "ticker"})
    grouped = role_events.sort_values("announcement_date").groupby("ticker")["announcement_date"]
    return {ticker: dates.tolist() for ticker, dates in grouped}


def add_role_labels(panel: pd.DataFrame, events: pd.DataFrame, role: str, horizon_months: int) -> pd.DataFrame:
    role_col = f"{role}_ticker"
    event_dates_by_ticker = event_table(events, role_col)

    next_dates: list[pd.Timestamp | pd.NaT] = []
    labels: list[int] = []
    prior_counts: list[int] = []
    days_since_prior: list[float] = []

    for ticker, as_of_date in zip(panel["ticker"], panel["as_of_date"], strict=False):
        dates = event_dates_by_ticker.get(ticker, [])
        future_limit = as_of_date + pd.DateOffset(months=horizon_months)
        prior = [date for date in dates if date <= as_of_date]
        future = [date for date in dates if as_of_date < date <= future_limit]

        prior_counts.append(len(prior))
        if prior:
            days_since_prior.append((as_of_date - prior[-1]).days)
        else:
            days_since_prior.append(pd.NA)

        if future:
            labels.append(1)
            next_dates.append(future[0])
        else:
            labels.append(0)
            next_dates.append(pd.NaT)

    panel[f"prior_{role}_event_count"] = prior_counts
    panel[f"days_since_prior_{role}_event"] = days_since_prior
    panel[f"next_{role}_announcement_date"] = next_dates
    panel[f"label_{role}_within_{horizon_months}m"] = labels
    return panel


def build_panel(
    universe: pd.DataFrame,
    prices: pd.DataFrame,
    events: pd.DataFrame,
    frequency: str,
    horizon_months: int,
) -> pd.DataFrame:
    features = add_market_features(prices)
    panel = select_as_of_rows(features, frequency)
    panel = panel.merge(universe, how="left", on="ticker")

    panel = add_role_labels(panel, events, "target", horizon_months)
    panel = add_role_labels(panel, events, "acquirer", horizon_months)

    ordered_cols = [
        "ticker",
        "company_name",
        "exchange",
        "sector",
        "cik",
        "as_of_date",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "ret",
        "dollar_volume",
        "ret_5d",
        "ret_20d",
        "ret_60d",
        "vol_20d",
        "vol_60d",
        "avg_dollar_volume_20d",
        "volume_zscore_20d",
        "drawdown_60d",
        "prior_target_event_count",
        "days_since_prior_target_event",
        "next_target_announcement_date",
        f"label_target_within_{horizon_months}m",
        "prior_acquirer_event_count",
        "days_since_prior_acquirer_event",
        "next_acquirer_announcement_date",
        f"label_acquirer_within_{horizon_months}m",
    ]
    ordered_cols = [col for col in ordered_cols if col in panel.columns]
    return panel[ordered_cols].sort_values(["as_of_date", "ticker"]).reset_index(drop=True)


def build_coverage_report(universe: pd.DataFrame, prices: pd.DataFrame, events: pd.DataFrame, panel: pd.DataFrame) -> pd.DataFrame:
    price_tickers = set(prices["ticker"].dropna())
    event_targets = set(events["target_ticker"].dropna())
    event_acquirers = set(events["acquirer_ticker"].dropna())
    universe_tickers = set(universe["ticker"].dropna())

    rows = [
        {"metric": "universe_tickers", "value": len(universe_tickers)},
        {"metric": "price_tickers", "value": len(price_tickers)},
        {"metric": "event_rows", "value": len(events)},
        {"metric": "event_target_tickers", "value": len(event_targets)},
        {"metric": "event_acquirer_tickers", "value": len(event_acquirers)},
        {"metric": "event_targets_with_price", "value": len(event_targets & price_tickers)},
        {"metric": "event_acquirers_with_price", "value": len(event_acquirers & price_tickers)},
        {"metric": "panel_rows", "value": len(panel)},
        {"metric": "panel_tickers", "value": panel["ticker"].nunique()},
        {"metric": "panel_positive_target_rows", "value": int(panel.filter(like="label_target_within_").sum().sum())},
        {"metric": "panel_positive_acquirer_rows", "value": int(panel.filter(like="label_acquirer_within_").sum().sum())},
    ]
    return pd.DataFrame(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build an OHLCV + M&A-label prediction panel.")
    parser.add_argument("--universe", type=Path, default=DEFAULT_UNIVERSE)
    parser.add_argument("--prices", type=Path, default=DEFAULT_PRICES)
    parser.add_argument("--events", type=Path, default=DEFAULT_EVENTS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--coverage-output", type=Path, default=DEFAULT_COVERAGE)
    parser.add_argument("--frequency", choices=["daily", "month_end"], default="month_end")
    parser.add_argument("--horizon-months", type=int, default=6)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    universe = load_universe(args.universe)
    prices = load_prices(args.prices)
    events = load_events(args.events)
    panel = build_panel(universe, prices, events, args.frequency, args.horizon_months)
    coverage = build_coverage_report(universe, prices, events, panel)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.coverage_output.parent.mkdir(parents=True, exist_ok=True)
    panel.to_csv(args.output, index=False)
    coverage.to_csv(args.coverage_output, index=False)

    print(f"Wrote {len(panel):,} panel rows to {os.path.relpath(args.output, PROJECT_ROOT)}")
    print(f"Wrote coverage report to {os.path.relpath(args.coverage_output, PROJECT_ROOT)}")
    print(coverage.to_string(index=False))


if __name__ == "__main__":
    main()
