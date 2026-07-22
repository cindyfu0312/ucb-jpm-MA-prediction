"""Score cached M&A event-window news with an LLM (OpenAI structured outputs), resumably.

For every (transaction_id, window) pair in the local news cache built by
`download_news_ma_events.py`, this sends ONE chat-completions call containing that window's
(noise-filtered, deduplicated) GDELT headlines plus a one-line summary of the window's SEC
filings, and receives a strict-JSON vector of M&A-precursor signals (rumor intensity,
strategic-alternatives language, activist pressure, management instability, ...). Those
fields become "feature set B" in `week7_llm_ma_prediction.ipynb`, compared against the
week-4 classic-NLP stack ("feature set A") computed on the exact same corpus.

Three tasks share the same cache/resume machinery (`--task`):
  - `extract`  score the `pre` / `baseline` windows from the main news cache (the default)
  - `day0`     score the [announcement-7d, announcement] windows from the blackout
               diagnostic cache -- for the week-4 §8 detection comparison only
  - `probe`    memorization test: NO headlines are sent; the model is asked, from memory
               alone, whether the company was announced as an acquisition target after a
               given as-of date. Quantifies training-data look-ahead. Output goes to a
               separate cache that must NEVER be merged into modeling features.

Leakage rules baked into the prompts:
  - the announcement date is never sent; windows are described only by their end month
    and per-headline day-offsets within the window ([d07] = day 7 of the period);
  - the model is never told whether a window is `pre` or `baseline`;
  - `--mask-names` additionally blanks the company's own name tokens from every headline
    (same masking as week4 §3c) -- the unmasked-vs-masked score gap estimates how much the
    model leans on recognizing the specific company rather than reading the text.

Like the news scrapers, the cache is a persistent, append-only local file
(`data/raw/llm/ma_event_llm_scores.csv`, gitignored): re-running skips every
(transaction_id, window, task, model, prompt_version, variant, run_tag) already scored
successfully, so runs can be stopped, resumed, and topped up without re-paying for calls.
Failed/refused/unparseable calls are retried on the next run. Every response's token usage
is metered against `--max-cost` (per-run USD cap): when the cap is hit, in-flight calls
finish, everything is flushed, and the run exits cleanly.

Requires OPENAI_API_KEY in the environment or in `<repo>/.env` (gitignored).

Typical sequence (each line resumable, costs are rough at gpt-5-mini pricing):
    python code/extract_llm_features.py --limit 3 --workers 1          # smoke test, ~$0.01
    python code/extract_llm_features.py                                # main extract, ~$2
    python code/extract_llm_features.py --mask-names                   # masked A/B, ~$2
    python code/extract_llm_features.py --repeat-tag r2 --limit-events 30   # consistency
    python code/extract_llm_features.py --task probe                   # memorization probe
    python code/extract_llm_features.py --model gpt-5 --limit-events 100    # sensitivity
    python code/extract_llm_features.py --task day0                    # detection windows
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import lru_cache
from pathlib import Path

import pandas as pd

from download_news_ma_events import clean_name, get_window_dates

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EVENTS = PROJECT_ROOT / "data" / "raw" / "events" / "ma_events.csv"
DEFAULT_NEWS_CACHE = PROJECT_ROOT / "data" / "raw" / "news" / "ma_event_news.csv"
DEFAULT_BLACKOUT_CACHE = PROJECT_ROOT / "data" / "raw" / "news" / "ma_event_news_blackout.csv"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "raw" / "llm"

# Window geometry -- must match the scraping run in download_news_ma_events.py.
LOOKBACK_DAYS = 90
BLACKOUT_DAYS = 7
NEGATIVE_SHIFT = 180

PROMPT_VERSION = "v1"

# Published per-1M-token prices (input, output). Verify against current provider pricing;
# override with --price-in/--price-out for any model not listed here. OpenRouter model IDs
# are namespaced (provider/model) and priced at the underlying provider's rate.
PRICES = {
    "gpt-5": (1.25, 10.00),
    "gpt-5-mini": (0.25, 2.00),
    "gpt-5-nano": (0.05, 0.40),
    # OpenRouter (base-url https://openrouter.ai/api/v1); see openrouter.ai/models.
    "openai/gpt-4o-mini": (0.15, 0.60),
    "openai/gpt-4o": (2.50, 10.00),
    "google/gemini-2.5-flash-lite": (0.10, 0.40),
}

# Approximate published knowledge cutoffs, used by the notebook to split events into
# pre-cutoff (memorizable) vs post-cutoff (memorization-free holdout).
MODEL_KNOWLEDGE_CUTOFF = {
    "gpt-5": "2024-10-01",
    "gpt-5-mini": "2024-06-01",
    "gpt-5-nano": "2024-06-01",
    "openai/gpt-4o-mini": "2023-10-01",
    "openai/gpt-4o": "2023-10-01",
    "google/gemini-2.5-flash-lite": "2025-01-01",
}

# ── Institutional/analyst-bot noise filter ─────────────────────────────────────
# Lifted verbatim from week4 cell 13 so the LLM reads the SAME corpus the classic-NLP
# feature stack scores (single source of truth going forward: the notebook imports these).
# Content-based, applied identically to both windows -- never conditioned on the label.
NOISE_RE = re.compile(
    r"("
    r"\bShares\b.{0,40}\b(Sold|Bought|Acquired|Cut|Lowered|Raised|Boosted|Purchased)\b|"
    r"\b(Sells|Buys|Acquires|Cuts|Lowers|Raises|Boosts|Purchases)\b.{0,40}\bShares\b|"
    r"\bHoldings (in|of)\b|\bPosition (in|of)\b|\bStake (in|of)\b|"
    r"\bPosition (Lowered|Raised|Boosted|Cut)\b|"
    r"\bPrice Target\b|\bPT from\b|\bAverage (Price )?Target\b|"
    r"\bRating (Upgraded|Downgraded|Reiterated|Lowered|Raised)\b|"
    r"\bShort Interest\b|\bInstitutional Investor\b|\bHedge Fund\b|"
    r"\bAverage Recommendation\b|\bModerate Buy\b|\b13F\b|"
    r"\bQ[1-4]\s?20\d\d Earnings\b|\bEarnings (Call )?Transcript\b|\bEarnings Snapshot\b|"
    r"\bMarket (Report|Size|Share|Growth|Trends|Forecast|Challenges|Outlook)\b|"
    r"\bGlobal Market\b|\bIndustry Forecast\b|\bTop Players\b|\bMarket 20\d\d\b|"
    r"\bMakes New Investment\b|\bTakes .{0,20}Position\b"
    r")",
    re.IGNORECASE,
)
JUNK_DOMAINS = {
    "dailypolitical.com", "wkrb13.com", "themarketsdaily.com", "tickerreport.com",
    "theenterpriseleader.com", "modernreaders.com", "openpr.com", "insidermonkey.com",
}

FTYPE_RE = re.compile(r"^\[([^\]]+)\]")

# ── Structured-output schemas ──────────────────────────────────────────────────
# All properties required + additionalProperties:false (strict-mode requirements).
# Strict mode does not enforce numeric ranges -> parse_and_clamp() does.

SIGNAL_FIELDS_0_10 = {
    "ma_rumor_intensity": "Explicit deal reports about THIS company: 'in talks', 'exploring a sale', 'takeover bid', 'sources say', named suitors.",
    "strategic_alternatives_review": "Strategic review / 'exploring strategic alternatives' / bankers or advisers hired / unit-sale exploration language.",
    "activist_pressure": "Activist investors, stake-building campaigns, board fights, proxy contests, demands to sell or break up.",
    "management_instability": "CEO/CFO departures, board shakeups, leadership uncertainty or succession questions.",
    "financial_distress": "Losses, heavy debt, downgrades, layoffs, guidance cuts, restructuring, going-concern language.",
    "undervaluation_narrative": "Coverage framing the company as cheap, lagging peers, trading below value, 'a bargain'.",
    "sector_consolidation_wave": "M&A activity among the company's PEERS or sector mentioned around this company.",
    "regulatory_antitrust_attention": "Antitrust or regulator scrutiny touching the company or deals in its sector.",
    "divestiture_restructuring": "Spin-offs, asset or unit sales, portfolio pruning, carve-outs by the company.",
    "growth_expansion_tone": "Ordinary-course growth news: products, partnerships, expansion, hiring (control dimension).",
}

EXTRACT_SCHEMA = {
    "type": "object",
    "properties": {
        **{
            k: {"type": "integer", "description": f"0-10. {v} 0 = no evidence in the text, 10 = overwhelming."}
            for k, v in SIGNAL_FIELDS_0_10.items()
        },
        "acquisition_likelihood": {
            "type": "integer",
            "description": "0-100. Holistic judgment: likelihood this company is acquired within ~6 months, based ONLY on these headlines.",
        },
        "headline_information_quality": {
            "type": "integer",
            "description": "0-10. How substantive and on-topic the supplied headlines are (0 = all noise/irrelevant).",
        },
        "dominant_theme": {
            "type": "string",
            "enum": ["ma_speculation", "earnings", "product", "legal_regulatory",
                     "leadership", "distress", "macro_sector", "other"],
            "description": "The single theme that best characterizes this window's coverage.",
        },
        "recognized_company": {
            "type": "boolean",
            "description": "True if you believe you can identify which specific real-world company this is.",
        },
        "recognized_deal": {
            "type": "boolean",
            "description": "True if you recall a specific real-world M&A deal involving this company from your training knowledge (NOT from these headlines).",
        },
        "evidence_quotes": {
            "type": "array", "items": {"type": "string"},
            "description": "Up to 3 verbatim headline fragments supporting your highest scores. Empty if nothing substantive.",
        },
        "rationale": {"type": "string", "description": "One sentence (<= 40 words) justifying the overall read."},
    },
    "required": list(SIGNAL_FIELDS_0_10) + [
        "acquisition_likelihood", "headline_information_quality", "dominant_theme",
        "recognized_company", "recognized_deal", "evidence_quotes", "rationale",
    ],
    "additionalProperties": False,
}

PROBE_SCHEMA = {
    "type": "object",
    "properties": {
        "was_announced_target": {
            "type": "boolean",
            "description": "True if, within the stated horizon after the as-of date, this company was publicly announced as the target of a >= $1B acquisition.",
        },
        "confidence_0_100": {"type": "integer", "description": "0-100 confidence in your answer."},
        "recalls_specific_deal": {
            "type": "boolean",
            "description": "True if you are recalling a specific real deal (dates, acquirer) rather than guessing from base rates.",
        },
        "acquirer_name_guess": {
            "type": "string",
            "description": "If you recall a specific deal, the acquirer's name; otherwise an empty string.",
        },
        "brief_reason": {"type": "string", "description": "One short sentence explaining your answer."},
    },
    "required": ["was_announced_target", "confidence_0_100", "recalls_specific_deal",
                 "acquirer_name_guess", "brief_reason"],
    "additionalProperties": False,
}

SCORE_FIELDS = list(SIGNAL_FIELDS_0_10) + ["acquisition_likelihood", "headline_information_quality"]

CACHE_COLUMNS = [
    "transaction_id", "window", "label", "task", "variant", "run_tag", "model",
    "prompt_version", "company_name", "n_headlines_total", "n_headlines_sent",
    "n_edgar_filings", "window_end_month", "latency_s", "input_tokens", "output_tokens",
    "cost_usd", "finish_reason", "refusal", "parse_ok", "error",
] + [f"llm_{f}" for f in SCORE_FIELDS] + [
    "llm_dominant_theme", "llm_recognized_company", "llm_recognized_deal",
    "llm_evidence_quotes", "llm_rationale", "json_raw",
]

PROBE_COLUMNS = [
    "transaction_id", "window", "label", "task", "variant", "run_tag", "model",
    "prompt_version", "company_name", "asof_date", "horizon_days", "latency_s",
    "input_tokens", "output_tokens", "cost_usd", "finish_reason", "refusal",
    "parse_ok", "error",
    "probe_was_announced_target", "probe_confidence_0_100", "probe_recalls_specific_deal",
    "probe_acquirer_name_guess", "probe_brief_reason", "json_raw",
]

EXTRACT_SYSTEM_PROMPT = (
    "You are a financial-news analyst scoring M&A-precursor signals for ONE US public "
    "company from a single ~{period_days}-day period of its news coverage. Judge ONLY "
    "from the text provided. Do not use any memory of real-world outcomes for this "
    "specific company. Score each dimension 0-10 where 0 = no evidence in the text and "
    "10 = overwhelming evidence. Be conservative: for most companies in most periods, "
    "most dimensions score 0-2. Quote only text that actually appears in the headlines."
)

PROBE_SYSTEM_PROMPT = (
    "You are being tested on your factual recall of corporate M&A history. Answer from "
    "your general knowledge/memory only. If you do not recall this specific company's "
    "history, say so via low confidence rather than guessing confidently."
)


@lru_cache(maxsize=None)
def _company_mask_pattern(company_name: str):
    """Same masking as week4 §3c: blank the company's own name tokens from its headlines."""
    words = [w for w in clean_name(company_name).split() if len(w) >= 3]
    if not words:
        return None
    return re.compile(r"\b(" + "|".join(re.escape(w) for w in words) + r")\b", re.IGNORECASE)


def mask_text(text: str, company_name: str) -> str:
    pat = _company_mask_pattern(company_name)
    return pat.sub("[COMPANY]", str(text)) if pat else str(text)


def pack_headlines(articles: list[dict], max_headlines: int, mask_company: str | None) -> tuple[list[str], int]:
    """Dedupe (case-normalized), sort by date, cap to an evenly-spaced-by-date subset so
    the temporal spread survives the cap (the LLM can still judge late-building intensity)."""
    seen: set[str] = set()
    deduped = []
    for a in sorted(articles, key=lambda a: a.get("date") or ""):
        key = re.sub(r"\s+", " ", str(a["title"]).strip().lower())
        if key and key not in seen:
            seen.add(key)
            deduped.append(a)
    n_total = len(deduped)
    if n_total > max_headlines:
        idx = [round(i * (n_total - 1) / (max_headlines - 1)) for i in range(max_headlines)]
        deduped = [deduped[i] for i in sorted(set(idx))]
    lines = []
    for a in deduped:
        title = mask_text(a["title"], mask_company) if mask_company else str(a["title"])
        day = a.get("day_offset")
        tag = f"[d{int(day):02d}]" if day is not None and not pd.isna(day) else "[d??]"
        dom = f" ({a['domain']})" if a.get("domain") else ""
        lines.append(f"{tag} {title}{dom}")
    return lines, n_total


def build_messages_extract(company: str, window_end_month: str, period_days: int,
                           headline_lines: list[str], n_total: int, edgar_summary: str,
                           masked: bool) -> list[dict]:
    shown_name = "[COMPANY]" if masked else clean_name(company) or company
    if headline_lines:
        head_block = (
            f"Headlines ({len(headline_lines)} of {n_total} kept after spam filtering, "
            f"chronological; [dNN] = day within the period, higher = later):\n"
            + "\n".join(headline_lines)
        )
    else:
        head_block = "Headlines: none available for this period."
    user = (
        f"Company: {shown_name}\n"
        f"Period: ~{period_days} days ending {window_end_month}\n"
        f"SEC filings during the period: {edgar_summary}\n\n"
        f"{head_block}\n\n"
        "Score the signals defined in the response schema, based ONLY on the text above."
    )
    return [
        {"role": "system", "content": EXTRACT_SYSTEM_PROMPT.format(period_days=period_days)},
        {"role": "user", "content": user},
    ]


def build_messages_probe(company: str, ticker: str, industry: str, asof_date: str,
                         horizon_days: int) -> list[dict]:
    ident = company
    if ticker and not pd.isna(ticker):
        ident += f" (ticker: {ticker})"
    if industry and not pd.isna(industry):
        ident += f", {industry} industry"
    user = (
        f"As of {asof_date}: within the following {horizon_days} days, was {ident} "
        f"publicly announced as the acquisition target in a deal valued at $1 billion "
        f"or more? Answer from memory only -- no news text is provided."
    )
    return [
        {"role": "system", "content": PROBE_SYSTEM_PROMPT},
        {"role": "user", "content": user},
    ]


class CostMeter:
    """Thread-safe running cost total with a hard per-run USD cap."""

    def __init__(self, price_in_per_m: float, price_out_per_m: float, max_cost: float):
        self.price_in = price_in_per_m
        self.price_out = price_out_per_m
        self.max_cost = max_cost
        self.input_tokens = 0
        self.output_tokens = 0
        self.calls = 0
        self._lock = threading.Lock()
        self.stop_event = threading.Event()

    def add(self, usage) -> float:
        cost = (usage.prompt_tokens * self.price_in + usage.completion_tokens * self.price_out) / 1e6
        with self._lock:
            self.input_tokens += usage.prompt_tokens
            self.output_tokens += usage.completion_tokens
            self.calls += 1
            total = self.total_usd
        if total >= self.max_cost:
            self.stop_event.set()
        return cost

    @property
    def total_usd(self) -> float:
        return (self.input_tokens * self.price_in + self.output_tokens * self.price_out) / 1e6


def call_llm(client, messages: list[dict], schema: dict, schema_name: str, model: str,
             reasoning_effort: str, max_output_tokens: int, retries: int = 6):
    """One structured-output call with manual backoff. Returns (parsed|None, meta dict).

    gpt-5-family reasoning models reject temperature/top_p, so none are sent; if a model
    rejects reasoning_effort itself, the call is retried once without it."""
    import openai

    response_format = {
        "type": "json_schema",
        "json_schema": {"name": schema_name, "strict": True, "schema": schema},
    }
    kwargs = dict(model=model, messages=messages, response_format=response_format,
                  max_completion_tokens=max_output_tokens)
    if reasoning_effort:
        kwargs["reasoning_effort"] = reasoning_effort

    meta = {"latency_s": 0.0, "finish_reason": "", "refusal": "0", "parse_ok": "0",
            "error": "", "usage": None}
    for attempt in range(retries):
        t0 = time.monotonic()
        try:
            resp = client.chat.completions.create(**kwargs)
        except openai.BadRequestError as exc:
            if "reasoning_effort" in str(exc) and "reasoning_effort" in kwargs:
                kwargs.pop("reasoning_effort")
                continue
            meta["error"] = f"BadRequestError:{str(exc)[:180]}"
            return None, meta
        except (openai.RateLimitError, openai.APIConnectionError, openai.APITimeoutError) as exc:
            if attempt == retries - 1:
                meta["error"] = type(exc).__name__
                return None, meta
            retry_after = getattr(getattr(exc, "response", None), "headers", {}) or {}
            wait = float(retry_after.get("retry-after", 0) or 0) or min(60.0, 2.0 ** attempt + 0.5)
            time.sleep(wait)
            continue
        except openai.APIStatusError as exc:
            if exc.status_code >= 500 and attempt < retries - 1:
                time.sleep(min(60.0, 2.0 ** attempt + 0.5))
                continue
            meta["error"] = f"APIStatusError:{exc.status_code}"
            return None, meta

        meta["latency_s"] = round(time.monotonic() - t0, 2)
        meta["usage"] = resp.usage
        choice = resp.choices[0]
        meta["finish_reason"] = choice.finish_reason or ""
        if getattr(choice.message, "refusal", None):
            meta["refusal"] = "1"
            meta["error"] = f"refusal:{choice.message.refusal[:120]}"
            return None, meta
        if choice.finish_reason == "length" and attempt < retries - 1:
            kwargs["max_completion_tokens"] = kwargs["max_completion_tokens"] * 2
            continue
        try:
            parsed = json.loads(choice.message.content or "")
            meta["parse_ok"] = "1"
            return parsed, meta
        except (json.JSONDecodeError, TypeError):
            meta["error"] = "json_parse_failed"
            return None, meta
    meta["error"] = meta["error"] or "retries_exhausted"
    return None, meta


def parse_and_clamp(raw: dict) -> dict:
    """Coerce/clamp extract-task fields (strict mode does not enforce numeric ranges)."""
    out = {}
    for f in SIGNAL_FIELDS_0_10:
        out[f"llm_{f}"] = int(min(10, max(0, int(raw.get(f, 0) or 0))))
    out["llm_acquisition_likelihood"] = int(min(100, max(0, int(raw.get("acquisition_likelihood", 0) or 0))))
    out["llm_headline_information_quality"] = int(min(10, max(0, int(raw.get("headline_information_quality", 0) or 0))))
    theme = str(raw.get("dominant_theme", "other"))
    out["llm_dominant_theme"] = theme if theme in EXTRACT_SCHEMA["properties"]["dominant_theme"]["enum"] else "other"
    out["llm_recognized_company"] = "1" if raw.get("recognized_company") else "0"
    out["llm_recognized_deal"] = "1" if raw.get("recognized_deal") else "0"
    quotes = raw.get("evidence_quotes") or []
    out["llm_evidence_quotes"] = json.dumps([str(q)[:200] for q in quotes[:3]])
    out["llm_rationale"] = str(raw.get("rationale", ""))[:400]
    return out


def load_llm_cache(path: Path, columns: list[str]) -> pd.DataFrame:
    if path.exists():
        return pd.read_csv(path, dtype=str).fillna("")
    return pd.DataFrame(columns=columns)


class RowWriter:
    """Lock-guarded append-only CSV writer, flushed per row (crash-safe: a killed run
    loses at most the in-flight call, never completed paid calls)."""

    def __init__(self, path: Path, columns: list[str]):
        path.parent.mkdir(parents=True, exist_ok=True)
        new = not path.exists() or path.stat().st_size == 0
        self._fh = open(path, "a", newline="", encoding="utf-8")
        self._writer = csv.DictWriter(self._fh, fieldnames=columns, extrasaction="ignore")
        self._lock = threading.Lock()
        if new:
            self._writer.writeheader()
            self._fh.flush()

    def write(self, row: dict) -> None:
        with self._lock:
            self._writer.writerow(row)
            self._fh.flush()

    def close(self) -> None:
        self._fh.close()


def build_window_corpus(news_df: pd.DataFrame, events: pd.DataFrame,
                        blackout_df: pd.DataFrame | None = None) -> dict:
    """Group cached articles by (transaction_id, window) with per-article day offsets and
    per-window EDGAR filing-type counts. Blackout rows (if given) become window='day0'."""
    ev = events.set_index("transaction_id")

    def _window_bounds(txn_id: str, window: str):
        ann = ev.loc[txn_id, "announcement_date"]
        if window == "day0":
            end = pd.Timestamp(ann)
            start = end - pd.Timedelta(days=BLACKOUT_DAYS)
            return start, end
        s, e = get_window_dates(ann, window, LOOKBACK_DAYS, BLACKOUT_DAYS, NEGATIVE_SHIFT)
        return pd.Timestamp(s), pd.Timestamp(e)

    corpus: dict[tuple[str, str], dict] = {}

    def _ingest(df: pd.DataFrame, window_override: str | None, label_override: str | None):
        for _, r in df.iterrows():
            txn = str(r["transaction_id"])
            if txn not in ev.index:
                continue
            window = window_override or str(r["window"])
            key = (txn, window)
            if key not in corpus:
                start, end = _window_bounds(txn, window)
                corpus[key] = {
                    "transaction_id": txn,
                    "window": window,
                    "label": label_override if label_override is not None else str(r.get("label", "")),
                    "company_name": str(r["company_name"]),
                    "window_end_month": end.strftime("%Y-%m"),
                    "period_days": max((end - start).days, 1),
                    "_start": start,
                    "gdelt": [],
                    "edgar_types": {},
                    "n_noise_dropped": 0,
                }
            c = corpus[key]
            title = str(r.get("title", "") or "").strip()
            if not title:
                continue
            src = str(r.get("source", ""))
            if src == "edgar":
                m = FTYPE_RE.match(title)
                ftype = m.group(1) if m else "UNK"
                c["edgar_types"][ftype] = c["edgar_types"].get(ftype, 0) + 1
                continue
            if src != "gdelt":
                continue
            if NOISE_RE.search(title) or str(r.get("domain", "")) in JUNK_DOMAINS:
                c["n_noise_dropped"] += 1
                continue
            date_str = str(r.get("date", "") or "")[:8]
            day_offset = None
            art_date = pd.to_datetime(date_str, format="%Y%m%d", errors="coerce")
            if not pd.isna(art_date):
                day_offset = int(max((art_date - c["_start"]).days, 0))
            c["gdelt"].append({"title": title, "date": date_str,
                               "domain": str(r.get("domain", "")), "day_offset": day_offset})

    _ingest(news_df, None, None)
    if blackout_df is not None:
        _ingest(blackout_df, "day0", "1")
    return corpus


def edgar_summary_line(edgar_types: dict) -> str:
    if not edgar_types:
        return "none observed"
    return ", ".join(f"{k} x{v}" for k, v in sorted(edgar_types.items()))


def select_transaction_ids(all_ids: list[str], limit_events: int, seed: int) -> set[str]:
    """Deterministic shuffled prefix so smaller subsets nest inside larger ones
    (gpt-5's 100 events are a subset of gpt-5-mini's full set)."""
    order = pd.Series(sorted(all_ids)).sample(frac=1.0, random_state=seed).tolist()
    if limit_events and limit_events < len(order):
        order = order[:limit_events]
    return set(order)


def run(args) -> None:
    events = pd.read_csv(args.events, parse_dates=["announcement_date"])
    is_probe = args.task == "probe"
    if is_probe and args.mask_names:
        raise SystemExit("--task probe is a memory test of the REAL company name; --mask-names makes no sense here.")

    variant = "masked" if args.mask_names else "unmasked"
    out_path = args.output_dir / ("ma_event_llm_probe.csv" if is_probe else "ma_event_llm_scores.csv")
    columns = PROBE_COLUMNS if is_probe else CACHE_COLUMNS

    # ── Build the to-do list ───────────────────────────────────────────────────
    if is_probe:
        news = pd.read_csv(args.news_cache, dtype=str).fillna("")
        pool_ids = sorted(set(news["transaction_id"]))
        keep = select_transaction_ids(pool_ids, args.limit_events, args.seed)
        ev = events[events["transaction_id"].astype(str).isin(keep)]
        items = []
        for _, e in ev.iterrows():
            ann = pd.Timestamp(e["announcement_date"])
            for window, label, asof in [
                ("asof_ann_minus_7d", "1", ann - pd.Timedelta(days=7)),
                ("asof_base_end", "0", ann - pd.Timedelta(days=BLACKOUT_DAYS + NEGATIVE_SHIFT)),
            ]:
                items.append({
                    "transaction_id": str(e["transaction_id"]), "window": window, "label": label,
                    "company_name": str(e["target_name"]), "ticker": e.get("target_ticker", ""),
                    "industry": e.get("primary_industry", ""),
                    "asof_date": asof.strftime("%Y-%m-%d"), "horizon_days": args.probe_horizon_days,
                })
    else:
        news = pd.read_csv(args.news_cache, dtype=str).fillna("")
        blackout = None
        if args.task == "day0":
            if not args.blackout_cache.exists():
                raise SystemExit(f"--task day0 needs {args.blackout_cache}; run diagnose_blackout_signal.py first.")
            blackout = pd.read_csv(args.blackout_cache, dtype=str).fillna("")
            corpus = build_window_corpus(news.iloc[0:0], events, blackout)
        else:
            corpus = build_window_corpus(news, events)
        keep = select_transaction_ids(sorted({t for t, _ in corpus}), args.limit_events, args.seed)
        items = []
        for (txn, window), c in sorted(corpus.items()):
            if txn not in keep:
                continue
            if not c["gdelt"] and not c["edgar_types"]:
                continue  # nothing to read; downstream treats absent rows as zero-coverage
            items.append(c)

    # ── Resume: skip keys already scored successfully ──────────────────────────
    cache = load_llm_cache(out_path, columns)
    done: set[tuple] = set()
    if not cache.empty:
        ok = cache[cache["parse_ok"] == "1"]
        done = set(zip(ok["transaction_id"], ok["window"], ok["task"], ok["model"],
                       ok["prompt_version"], ok["variant"], ok["run_tag"]))
    todo = [it for it in items
            if (it["transaction_id"], it["window"], args.task, args.model,
                PROMPT_VERSION, variant, args.repeat_tag) not in done]
    n_already = len(items) - len(todo)
    if args.limit:
        todo = todo[:args.limit]

    price_in, price_out = PRICES.get(args.model, (None, None))
    if args.price_in is not None:
        price_in = args.price_in
    if args.price_out is not None:
        price_out = args.price_out
    if price_in is None:
        raise SystemExit(f"No built-in pricing for {args.model!r}; pass --price-in/--price-out (per 1M tokens).")

    print(f"Task={args.task} model={args.model} variant={variant} run_tag={args.repeat_tag} "
          f"prompt={PROMPT_VERSION}")
    print(f"  candidate items: {len(items):,} | already scored: {n_already:,} | "
          f"to call this run: {len(todo):,}")
    print(f"  pricing assumed: ${price_in}/M in, ${price_out}/M out (verify vs current OpenAI pricing)"
          f" | per-run cap: ${args.max_cost:.2f}")

    # ── Build messages ─────────────────────────────────────────────────────────
    def messages_for(item) -> tuple[list[dict], dict]:
        if is_probe:
            msgs = build_messages_probe(item["company_name"], item["ticker"], item["industry"],
                                        item["asof_date"], item["horizon_days"])
            extra = {"asof_date": item["asof_date"], "horizon_days": item["horizon_days"]}
            return msgs, extra
        lines, n_total = pack_headlines(item["gdelt"], args.max_headlines,
                                        item["company_name"] if args.mask_names else None)
        msgs = build_messages_extract(item["company_name"], item["window_end_month"],
                                      item["period_days"], lines, n_total,
                                      edgar_summary_line(item["edgar_types"]), args.mask_names)
        extra = {"n_headlines_total": n_total, "n_headlines_sent": len(lines),
                 "n_edgar_filings": sum(item["edgar_types"].values()),
                 "window_end_month": item["window_end_month"]}
        return msgs, extra

    if args.dry_run:
        est_in = est_out = 0
        for i, item in enumerate(todo):
            msgs, _ = messages_for(item)
            n_in = sum(len(m["content"]) for m in msgs) // 4 + 350  # +schema overhead
            est_in += n_in
            est_out += 450 if not is_probe else 120
            if i < args.dry_run_show:
                print(f"\n--- DRY RUN prompt {i + 1} "
                      f"({item['transaction_id']}, {item['window']}) ---")
                for m in msgs:
                    print(f"[{m['role']}]\n{m['content']}")
        print(f"\nDry run: {len(todo):,} calls | est. {est_in:,} input + {est_out:,} output tokens "
              f"| est. cost ${(est_in * price_in + est_out * price_out) / 1e6:.2f}")
        return

    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env")
    import openai  # noqa: F401  (exception types used in call_llm)
    from openai import OpenAI
    api_key = os.environ.get(args.api_key_env)
    if not api_key:
        raise SystemExit(f"No API key found in ${args.api_key_env} (checked environment + .env).")
    client_kwargs = dict(api_key=api_key, timeout=90.0, max_retries=0)
    if args.base_url:
        client_kwargs["base_url"] = args.base_url
    client = OpenAI(**client_kwargs)
    print(f"  endpoint: {args.base_url or 'https://api.openai.com/v1 (default)'} "
          f"| key from ${args.api_key_env}")

    meter = CostMeter(price_in, price_out, args.max_cost)
    writer = RowWriter(out_path, columns)
    schema = PROBE_SCHEMA if is_probe else EXTRACT_SCHEMA
    schema_name = "ma_probe_v1" if is_probe else "ma_window_signals_v1"

    base_row = {"task": args.task, "variant": variant, "run_tag": args.repeat_tag,
                "model": args.model, "prompt_version": PROMPT_VERSION}

    def work(item) -> dict:
        msgs, extra = messages_for(item)
        row = {c: "" for c in columns}
        row.update(base_row)
        row.update({k: item.get(k, "") for k in ("transaction_id", "window", "label", "company_name")})
        row.update({k: str(v) for k, v in extra.items()})
        if meter.stop_event.is_set():
            row.update(error="skipped_max_cost", parse_ok="0")
            return row
        parsed, meta = call_llm(client, msgs, schema, schema_name, args.model,
                                args.reasoning_effort, args.max_output_tokens)
        usage = meta.pop("usage", None)
        if usage is not None:
            cost = meter.add(usage)
            row.update(input_tokens=str(usage.prompt_tokens),
                       output_tokens=str(usage.completion_tokens), cost_usd=f"{cost:.6f}")
        row.update({k: str(v) for k, v in meta.items()})
        if parsed is not None:
            if is_probe:
                row.update(
                    probe_was_announced_target="1" if parsed.get("was_announced_target") else "0",
                    probe_confidence_0_100=str(min(100, max(0, int(parsed.get("confidence_0_100", 0) or 0)))),
                    probe_recalls_specific_deal="1" if parsed.get("recalls_specific_deal") else "0",
                    probe_acquirer_name_guess=str(parsed.get("acquirer_name_guess", ""))[:120],
                    probe_brief_reason=str(parsed.get("brief_reason", ""))[:300],
                )
            else:
                row.update({k: str(v) for k, v in parse_and_clamp(parsed).items()})
            row["json_raw"] = json.dumps(parsed)[:4000]
        return row

    n_ok = n_err = 0
    t_start = time.monotonic()
    try:
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = {pool.submit(work, item): item for item in todo}
            for i, fut in enumerate(as_completed(futures), start=1):
                row = fut.result()
                if row.get("error") == "skipped_max_cost":
                    continue  # not written: retryable next run
                writer.write(row)
                if row["parse_ok"] == "1":
                    n_ok += 1
                else:
                    n_err += 1
                if args.verbose or i % 25 == 0 or i == len(todo):
                    rate = i / max(time.monotonic() - t_start, 1e-9)
                    print(f"  [{i}/{len(todo)}] ok={n_ok} err={n_err} "
                          f"${meter.total_usd:.2f} spent | {rate:.1f} calls/s")
                if meter.stop_event.is_set():
                    print(f"  !! --max-cost ${args.max_cost:.2f} reached -- finishing in-flight "
                          f"calls and stopping (resume later; nothing is lost).")
    finally:
        writer.close()

    manifest_path = args.output_dir / "ma_event_llm_manifest.csv"
    cache_after = load_llm_cache(out_path, columns)
    manifest = pd.DataFrame([{
        "run_at": pd.Timestamp.now(tz="UTC").isoformat(),
        "task": args.task, "model": args.model, "variant": variant,
        "run_tag": args.repeat_tag, "prompt_version": PROMPT_VERSION,
        "calls_made": meter.calls, "calls_ok": n_ok, "calls_err": n_err,
        "input_tokens": meter.input_tokens, "output_tokens": meter.output_tokens,
        "cost_usd_run": round(meter.total_usd, 4),
        "rows_total_cache": len(cache_after),
    }])
    header = not manifest_path.exists()
    manifest.to_csv(manifest_path, mode="a", header=header, index=False)

    print(f"\nDone. {n_ok:,} scored ok, {n_err:,} failed (retryable) | "
          f"run cost ${meter.total_usd:.2f} ({meter.input_tokens:,} in / {meter.output_tokens:,} out tokens)")
    print(f"  cache now {len(cache_after):,} rows -> {out_path.relative_to(PROJECT_ROOT)}")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Score cached M&A event-window news with an LLM, resumably and cost-capped.")
    p.add_argument("--task", choices=["extract", "day0", "probe"], default="extract")
    p.add_argument("--events", type=Path, default=DEFAULT_EVENTS)
    p.add_argument("--news-cache", type=Path, default=DEFAULT_NEWS_CACHE)
    p.add_argument("--blackout-cache", type=Path, default=DEFAULT_BLACKOUT_CACHE)
    p.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    p.add_argument("--model", default="gpt-5-mini")
    p.add_argument("--base-url", default=None,
                   help="Override API base URL, e.g. https://openrouter.ai/api/v1 for OpenRouter "
                        "(default: OpenAI). OpenRouter models use namespaced IDs like openai/gpt-4o-mini.")
    p.add_argument("--api-key-env", default="OPENAI_API_KEY",
                   help="Env var (in environment or .env) holding the API key; use OPENROUTER_API_KEY "
                        "with --base-url https://openrouter.ai/api/v1.")
    p.add_argument("--reasoning-effort", default="minimal",
                   help="Passed to reasoning models (gpt-5 family); pass '' for non-reasoning models "
                        "like gpt-4o-mini. Auto-dropped if the model rejects it.")
    p.add_argument("--mask-names", action="store_true",
                   help="Blank the company's own name tokens from headlines (contamination A/B).")
    p.add_argument("--repeat-tag", default="r1",
                   help="Change (e.g. r2) to re-score the same keys for consistency measurement.")
    p.add_argument("--limit-events", type=int, default=0,
                   help="Deterministic nested subset of N events (0 = all).")
    p.add_argument("--limit", type=int, default=0, help="Cap calls this run (smoke tests).")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--max-cost", type=float, default=20.0, help="Per-run USD cap.")
    p.add_argument("--price-in", type=float, default=None, help="Override $/1M input tokens.")
    p.add_argument("--price-out", type=float, default=None, help="Override $/1M output tokens.")
    p.add_argument("--max-headlines", type=int, default=60)
    p.add_argument("--max-output-tokens", type=int, default=2000)
    p.add_argument("--probe-horizon-days", type=int, default=120,
                   help="Probe horizon; 120d keeps the baseline as-of date a clean negative "
                        "(announcement is 187d after it, 67d beyond the horizon).")
    p.add_argument("--dry-run", action="store_true", help="Print prompts + cost estimate; no API calls.")
    p.add_argument("--dry-run-show", type=int, default=3, help="Prompts to print in --dry-run.")
    p.add_argument("--verbose", action="store_true")
    return p.parse_args()


if __name__ == "__main__":
    run(parse_args())
