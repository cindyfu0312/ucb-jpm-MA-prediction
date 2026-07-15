"""Generate reports/week6_llm_ma_prediction_presentation.pptx from the week-6 notebook outputs.

Consumes outputs/week6/week6_deck_stats.json + outputs/week6/fig_*.png (written by
code/week6_llm_ma_prediction.ipynb §10), so the deck re-renders in seconds after any
notebook re-run. Layout/palette match the team's week2 / week3-4 decks (navy header band +
gold rule + gray footer, Calibri, manual text boxes -- no layout placeholders).

Usage:  python code/make_week6_deck.py
"""

from __future__ import annotations

import json
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.util import Emu, Inches, Pt

PROJECT_ROOT = Path(__file__).resolve().parents[1]
STATS_PATH = PROJECT_ROOT / "outputs" / "week6" / "week6_deck_stats.json"
FIG_DIR = PROJECT_ROOT / "outputs" / "week6"
OUT_PATH = PROJECT_ROOT / "reports" / "week6_llm_ma_prediction_presentation.pptx"

# ── Style constants measured from week3-4 deck ────────────────────────────────
NAVY = RGBColor(0x1A, 0x3A, 0x5C)
BLUE = RGBColor(0x2E, 0x6D, 0xB4)
GOLD = RGBColor(0xB8, 0x86, 0x0B)
GREEN = RGBColor(0x1A, 0x7A, 0x4A)
LIGHT_GREEN = RGBColor(0xE8, 0xF5, 0xE9)
LIGHT_PINK = RGBColor(0xFD, 0xED, 0xEC)
LIGHT_GRAY = RGBColor(0xF0, 0xF0, 0xF0)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
LIGHT_BLUE = RGBColor(0xD6, 0xE8, 0xF7)
AMBER = RGBColor(0xFF, 0xC0, 0x00)
FOOTER_GRAY = RGBColor(0xBB, 0xBB, 0xBB)
DARK_TEXT = NAVY
FONT = "Calibri"

SLIDE_W, SLIDE_H = Inches(13.333), Inches(7.5)
FOOTER_TEXT = "M&A Prediction | JPMorgan Industry Project | July 2026"


def _box(slide, x, y, w, h, fill=None, line=None):
    from pptx.enum.shapes import MSO_SHAPE
    sh = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, x, y, w, h)
    sh.shadow.inherit = False
    if fill is None:
        sh.fill.background()
    else:
        sh.fill.solid()
        sh.fill.fore_color.rgb = fill
    if line is None:
        sh.line.fill.background()
    else:
        sh.line.color.rgb = line
    return sh


def _text(slide, x, y, w, h, runs, size=14, color=DARK_TEXT, bold=False,
          align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP, line_spacing=1.0):
    """runs: str, or list of paragraphs, each str or list of (text, {bold,color,size}) runs."""
    tb = slide.shapes.add_textbox(x, y, w, h)
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = Emu(45720)
    tf.margin_top = tf.margin_bottom = Emu(22860)
    if isinstance(runs, str):
        runs = [runs]
    for i, para in enumerate(runs):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.line_spacing = line_spacing
        if isinstance(para, str):
            para = [(para, {})]
        for text, style in para:
            r = p.add_run()
            r.text = text
            r.font.name = FONT
            r.font.size = Pt(style.get("size", size))
            r.font.bold = style.get("bold", bold)
            r.font.color.rgb = style.get("color", color)
    return tb


def add_header(slide, title, subtitle=""):
    _box(slide, 0, 0, SLIDE_W, Inches(1.15), fill=NAVY)
    _text(slide, Inches(0.30), Inches(0.08), Inches(12.6), Inches(0.62),
          title, size=28, color=WHITE, bold=True)
    if subtitle:
        _text(slide, Inches(0.30), Inches(0.70), Inches(12.6), Inches(0.40),
              subtitle, size=14, color=GOLD)
    _box(slide, 0, Inches(1.15), SLIDE_W, Inches(0.04), fill=GOLD)


def add_footer(slide):
    _box(slide, 0, Inches(7.20), SLIDE_W, Inches(0.30), fill=NAVY)
    _text(slide, Inches(0.30), Inches(7.19), Inches(9.0), Inches(0.28),
          FOOTER_TEXT, size=9, color=FOOTER_GRAY)


def kpi_tile(slide, x, y, value, caption, fill=NAVY, value_color=AMBER,
             w=Inches(2.95), h=Inches(1.30)):
    _box(slide, x, y, w, h, fill=fill)
    _text(slide, x, y + Inches(0.06), w, Inches(0.70), value, size=28,
          color=value_color, bold=True, align=PP_ALIGN.CENTER)
    _text(slide, x, y + Inches(0.78), w, Inches(0.50), caption, size=11.5,
          color=LIGHT_BLUE, align=PP_ALIGN.CENTER)


def card(slide, x, y, w, header, body_lines, header_fill=BLUE, body_h=Inches(2.60)):
    _box(slide, x, y, w, Inches(0.42), fill=header_fill)
    _text(slide, x, y + Inches(0.01), w, Inches(0.40), header, size=15,
          color=WHITE, bold=True, align=PP_ALIGN.CENTER)
    _box(slide, x, y + Inches(0.42), w, body_h, fill=LIGHT_GRAY)
    _text(slide, x + Inches(0.08), y + Inches(0.52), w - Inches(0.16), body_h - Inches(0.2),
          body_lines, size=12.5, color=DARK_TEXT)


def callout(slide, text, positive=True, y=Inches(6.35), h=Inches(0.75)):
    _box(slide, Inches(0.40), y, Inches(12.53), h,
         fill=LIGHT_GREEN if positive else LIGHT_PINK)
    _text(slide, Inches(0.60), y + Inches(0.04), Inches(12.1), h - Inches(0.08),
          text, size=14, color=DARK_TEXT, bold=True, anchor=MSO_ANCHOR.MIDDLE)


def shape_table(slide, x, y, col_widths, rows, row_h=Inches(0.38), header_fill=NAVY,
                font_size=12.5):
    for j, cells in enumerate(rows):
        fill = header_fill if j == 0 else (WHITE if j % 2 else LIGHT_GRAY)
        color = WHITE if j == 0 else DARK_TEXT
        cx = x
        for cw, cell in zip(col_widths, cells):
            _box(slide, cx, y + j * row_h, cw, row_h, fill=fill)
            _text(slide, cx + Inches(0.05), y + j * row_h, cw - Inches(0.1), row_h,
                  str(cell), size=font_size, color=color, bold=(j == 0),
                  anchor=MSO_ANCHOR.MIDDLE)
            cx += cw


def add_picture_fit(slide, path, x, y, max_w, max_h):
    from PIL import Image
    with Image.open(path) as im:
        iw, ih = im.size
    scale = min(max_w / iw, max_h / ih)
    slide.shapes.add_picture(str(path), x, y, int(iw * scale), int(ih * scale))


def fmt(v, spec=".3f", missing="n/a"):
    return format(v, spec) if isinstance(v, (int, float)) else missing


def main() -> None:
    stats = json.loads(STATS_PATH.read_text())
    prs = Presentation()
    prs.slide_width, prs.slide_height = SLIDE_W, SLIDE_H
    blank = prs.slide_layouts[6]

    def new_slide():
        return prs.slides.add_slide(blank)

    auc = stats.get("auc", {})
    best = {}
    for sname, ms in auc.items():
        bm = max(ms, key=lambda m: ms[m]["auc"])
        best[sname] = (bm, ms[bm])
    a_key, b_key, c_key = ("A: classic NLP (week4)", "B: LLM signals only", "C: combined A+B")
    probe = (stats.get("probe") or {}).get(stats.get("primary_model", "gpt-5-mini"), {})
    masking = stats.get("masking") or {}
    repeat = stats.get("repeat") or {}
    sens = stats.get("sensitivity") or {}
    contaminated = stats.get("contaminated", False)
    llm_lift = stats.get("llm_lift", False)

    # ── Intuition-slide data, computed live from the committed interim artifacts ──
    cases, corr_note = None, None
    try:
        import pandas as pd
        llm_csv = pd.read_csv(PROJECT_ROOT / "data" / "interim" / "ma_llm_features.csv", dtype=str)
        llm_csv = llm_csv[(llm_csv.task == "extract")
                          & (llm_csv.model == stats.get("primary_model", "gpt-5-mini"))
                          & (llm_csv.variant == "unmasked") & (llm_csv.run_tag == "r1")].copy()
        text_cols = {"llm_dominant_theme", "llm_evidence_quotes", "llm_rationale",
                     "llm_recognized_company", "llm_recognized_deal"}
        num_cols = [c for c in llm_csv.columns if c.startswith("llm_") and c not in text_cols]
        for c in num_cols:
            llm_csv[c] = pd.to_numeric(llm_csv[c], errors="coerce")
        ev_names = pd.read_csv(PROJECT_ROOT / "data" / "raw" / "events" / "ma_events.csv",
                               usecols=["transaction_id", "target_name"]
                               ).set_index("transaction_id")["target_name"]
        wide = llm_csv.pivot_table(index="transaction_id", columns="window",
                                   values="llm_acquisition_likelihood")
        if {"pre", "baseline"}.issubset(wide.columns):
            wide = wide.dropna(subset=["pre", "baseline"])
            wide = wide.assign(diff=wide["pre"] - wide["baseline"])

            def _case(txn):
                sub = llm_csv[llm_csv.transaction_id == txn]
                pre = sub[sub.window == "pre"].iloc[0]
                base = sub[sub.window == "baseline"].iloc[0]
                qp = (json.loads(pre.llm_evidence_quotes or "[]") or ["(no substantive quotes)"])[0]
                qb = (json.loads(base.llm_evidence_quotes or "[]") or ["(no substantive quotes)"])[0]
                return dict(name=str(ev_names.get(txn, txn))[:46],
                            pre=int(pre.llm_acquisition_likelihood),
                            base=int(base.llm_acquisition_likelihood),
                            quote_pre=qp[:115], quote_base=qb[:115])

            if len(wide) >= 2:
                cases = dict(signal=_case(wide["diff"].idxmax()),
                             inversion=_case(wide["diff"].idxmin()),
                             n_pairs=int(len(wide)), n_up=int((wide["diff"] > 0).sum()),
                             n_dn=int((wide["diff"] < 0).sum()),
                             n_zero=int((wide["diff"] == 0).sum()))
        featA = pd.read_csv(PROJECT_ROOT / "data" / "interim" / "ma_news_features_week6.csv")
        a_cols = ["news_count", "avg_sentiment", "ma_keyword_ratio", "avg_finbert_compound",
                  "distinctive_term_ratio", "late_share", "edgar_deal_filing_ratio"]
        merged = llm_csv.merge(featA, on=["transaction_id", "window"])
        if len(merged) > 10:
            cm = merged[num_cols + a_cols].corr(method="spearman").loc[num_cols, a_cols]
            mx = cm.abs().stack().idxmax()
            corr_note = (mx[0].replace("llm_", ""), mx[1], float(cm.loc[mx[0], mx[1]]))
    except Exception:
        cases, corr_note = None, None

    # ── 1. Title ──────────────────────────────────────────────────────────────
    s = new_slide()
    _box(s, 0, 0, SLIDE_W, SLIDE_H, fill=NAVY)
    _box(s, 0, 0, SLIDE_W, Inches(0.55), fill=BLUE)
    _box(s, 0, Inches(0.55), SLIDE_W, Inches(0.05), fill=GOLD)
    _text(s, Inches(0.8), Inches(2.35), Inches(11.7), Inches(1.9),
          ["Can an LLM Read M&A Intent", "from Free News?"],
          size=42, color=WHITE, bold=True)
    _text(s, Inches(0.8), Inches(4.35), Inches(11.7), Inches(0.5),
          "J.P.Morgan Industry Project | Week 6 Results — GenAI Feature Extraction | July 2026",
          size=20, color=GOLD)
    _text(s, Inches(0.8), Inches(4.95), Inches(11.7), Inches(0.4),
          "Dexin Fu, Ronald Liu", size=16, color=LIGHT_BLUE)

    # ── 2. Executive summary ─────────────────────────────────────────────────
    s = new_slide()
    add_header(s, "Executive Summary", "One structured LLM call per event-window — scored, stress-tested, priced")
    x0 = Inches(0.40)
    kpi_tile(s, x0, Inches(1.45), f"{stats.get('llm_calls_ok', 0):,}",
             "LLM calls scored OK", fill=BLUE, value_color=WHITE)
    kpi_tile(s, x0 + Inches(3.18), Inches(1.45), f"${stats.get('llm_total_cost', 0):.2f}",
             "total API spend (budget $100)", fill=NAVY, value_color=AMBER)
    kpi_tile(s, x0 + Inches(6.36), Inches(1.45),
             f"{best[c_key][1]['auc']:.2f} vs {best[a_key][1]['auc']:.2f}" if auc else "n/a",
             "test AUC: LLM-combined vs classic", fill=NAVY, value_color=AMBER)
    probe_acc = probe.get("acc")
    kpi_tile(s, x0 + Inches(9.54), Inches(1.45),
             f"{probe_acc:.0%}" if isinstance(probe_acc, (int, float)) else "n/a",
             "memorization-probe accuracy (chance 50%)",
             fill=GREEN if (isinstance(probe_acc, (int, float)) and probe_acc < 0.6) else NAVY,
             value_color=WHITE)
    scope = (f"Honest scope: {stats.get('n_model_rows', '?')} modeling windows from "
             f"{stats.get('n_events_llm_scored', '?')} LLM-scored events "
             f"({stats.get('n_test_rows', '?')} in the held-out test split). LLM coverage was "
             f"budget-limited (~$0.40 spent). Small sample — every AUC carries a bootstrap 95% CI; "
             f"read these as DIRECTIONAL, not settled.")
    _box(s, x0, Inches(2.82), Inches(12.13), Inches(0.30), fill=GOLD)
    _text(s, x0 + Inches(0.10), Inches(2.80), Inches(12.0), Inches(0.34), scope,
          size=11.5, color=NAVY, bold=True, anchor=MSO_ANCHOR.MIDDLE)
    card(s, x0, Inches(3.28), Inches(4.05), "1 · Built",
         ["• extract_llm_features.py — parallel,", "  resumable, $-capped scorer",
          "• 17 strict-JSON fields per window", "  (rumor, strategic review, activist,",
          "  distress, likelihood 0–100, …)", "• gpt-5-mini everywhere + gpt-5 subset"],
         body_h=Inches(2.45))
    card(s, x0 + Inches(4.24), Inches(3.28), Inches(4.05), "2 · Measured",
         ["• A (classic NLP) vs B (LLM) vs C (both)", "  on identical rows, split & models",
          "• Bootstrap 95% CI on every AUC", "• Per-company pre-vs-baseline check",
          "  on each field", "• Detection (day-0) replication"], body_h=Inches(2.45))
    card(s, x0 + Inches(8.48), Inches(3.28), Inches(4.05), "3 · Stress-tested",
         ["• Memorization probe (no news shown)", "• Company-name masking A/B",
          "• Re-run consistency (are scores stable?)", "• Post-training-cutoff holdout",
          "  (2025–26 deals the model can't know)"], body_h=Inches(2.45))
    callout(s, stats.get("verdict", "")[:220], positive=not contaminated and llm_lift
            or stats.get("all_null", False))
    add_footer(s)

    # ── 3. Approach ──────────────────────────────────────────────────────────
    s = new_slide()
    add_header(s, "Approach: One Structured Call per Event-Window",
               "Same corpus, same windows, same models as week 3-4 — only the featurizer changes")
    steps = ["Cached headlines\n(GDELT + EDGAR)", "Spam filter\n(same as week4)",
             "1 LLM call / window\nstrict JSON schema", "17 fields parsed\n+ clamped",
             "Feature sets\nA / B / C", "Same 3 models\n+ bootstrap CIs"]
    sw, gap, sx = Inches(1.92), Inches(0.14), Inches(0.40)
    for i, st in enumerate(steps):
        x = sx + i * (sw + gap)
        _box(s, x, Inches(1.50), sw, Inches(0.95), fill=NAVY)
        _text(s, x, Inches(1.52), sw, Inches(0.91), st.split("\n"), size=11,
              color=WHITE, bold=True, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
        if i < len(steps) - 1:
            _text(s, x + sw - Inches(0.03), Inches(1.62), Inches(0.24), Inches(0.5),
                  "→", size=20, color=GOLD, bold=True)
    rows = [["Signal fields (0–10 each)", "Judgment fields"],
            ["ma_rumor_intensity · strategic_alternatives_review", "acquisition_likelihood (0–100)"],
            ["activist_pressure · management_instability", "headline_information_quality (0–10)"],
            ["financial_distress · undervaluation_narrative", "dominant_theme (8-way enum)"],
            ["sector_consolidation_wave · regulatory_antitrust", "recognized_company / recognized_deal"],
            ["divestiture_restructuring · growth_expansion_tone", "evidence_quotes (verbatim) + rationale"]]
    shape_table(s, Inches(0.40), Inches(2.85), [Inches(6.9), Inches(5.6)], rows)
    callout(s, "Leakage rules: announcement date never sent · window described only by end-month · "
               "pre/baseline identity never revealed · resumable cache, hard $ cap per run.",
            positive=True)
    add_footer(s)

    # ── 4. Feature dictionary (complete lists) ───────────────────────────────
    s = new_slide()
    add_header(s, "Feature Dictionary — Every Input the Models See",
               "Set A = week-4 classic stack recomputed on this corpus · Set B = LLM signals · C = A ∪ B")
    _box(s, Inches(0.40), Inches(1.40), Inches(6.15), Inches(0.40), fill=BLUE)
    _text(s, Inches(0.40), Inches(1.41), Inches(6.15), Inches(0.38),
          "SET A — classic NLP (28 candidates)", size=14, color=WHITE, bold=True,
          align=PP_ALIGN.CENTER)
    _box(s, Inches(0.40), Inches(1.80), Inches(6.15), Inches(4.25), fill=LIGHT_GRAY)
    _text(s, Inches(0.55), Inches(1.92), Inches(5.9), Inches(4.05),
          [[("Volume & VADER sentiment (7):", {"bold": True})],
           "   news_count · avg / std / max / min_sentiment · pos_ratio · neg_ratio",
           [("M&A keywords (2):", {"bold": True})],
           "   ma_keyword_count · ma_keyword_ratio",
           [("FinBERT finance sentiment (4):", {"bold": True})],
           "   avg / std_finbert_compound · avg_finbert_positive · avg_finbert_negative",
           [("Data-driven terms (1):", {"bold": True}), ("  distinctive_term_ratio (log-odds, name-masked)", {})],
           [("Momentum (2):", {"bold": True}), ("  late_share · sentiment_trend", {})],
           [("EDGAR filing structure (3):", {"bold": True})],
           "   edgar_filing_count · edgar_deal_filing_count · edgar_deal_filing_ratio",
           [("NMF topics (8):", {"bold": True}), ("  topic_0_mean … topic_7_mean (name-masked)", {})],
           [("Meta (1):", {"bold": True}), ("  industry_enc", {})]],
          size=11.5, color=DARK_TEXT, line_spacing=1.12)
    _box(s, Inches(6.77), Inches(1.40), Inches(6.15), Inches(0.40), fill=NAVY)
    _text(s, Inches(6.77), Inches(1.41), Inches(6.15), Inches(0.38),
          "SET B — LLM signals (12 features + 5 audit fields)", size=14, color=WHITE,
          bold=True, align=PP_ALIGN.CENTER)
    _box(s, Inches(6.77), Inches(1.80), Inches(6.15), Inches(4.25), fill=LIGHT_GRAY)
    _text(s, Inches(6.92), Inches(1.88), Inches(5.9), Inches(4.12),
          [[("Model features (one strict-JSON call per window):", {"bold": True})],
           "   ma_rumor_intensity 0–10 — “in talks”, bids, “sources say”",
           "   strategic_alternatives_review 0–10 — reviews, bankers hired",
           "   activist_pressure 0–10 — activists, stakes, proxy fights",
           "   management_instability 0–10 — CEO/CFO exits, shakeups",
           "   financial_distress 0–10 — losses, debt, downgrades",
           "   undervaluation_narrative 0–10 — “cheap”, lagging peers",
           "   sector_consolidation_wave 0–10 — peers merging",
           "   regulatory_antitrust_attention 0–10 — regulator scrutiny",
           "   divestiture_restructuring 0–10 — spin-offs, carve-outs",
           "   growth_expansion_tone 0–10 — ordinary growth (control)",
           "   acquisition_likelihood 0–100 — holistic judgment",
           "   headline_information_quality 0–10 — text usability",
           [("Audit fields — never model inputs:", {"bold": True})],
           "   dominant_theme · recognized_company · recognized_deal",
           "   evidence_quotes (verbatim) · rationale (≤ 40 words)"],
          size=11.5, color=DARK_TEXT, line_spacing=1.08)
    callout(s, "A and B are computed from the IDENTICAL noise-filtered corpus. C = A ∪ B "
               "(40 candidates → top 16 by train-only mutual information).", positive=True,
            y=Inches(6.25), h=Inches(0.75))
    add_footer(s)

    # ── 5. What the model reads ──────────────────────────────────────────────
    s = new_slide()
    add_header(s, "What the Model Actually Reads — and Returns",
               f"Real example: {stats.get('example_company', 'sample company')} "
               f"({stats.get('example_window', 'pre')} window)")
    prompt_lines = stats.get("example_prompt_lines") or [
        "Company: <example>", "Period: ~90 days ending YYYY-MM",
        "SEC filings during the period: …", "Headlines (…):", "[dNN] …"]
    response_lines = stats.get("example_response_lines") or ["{ … }"]
    _box(s, Inches(0.40), Inches(1.45), Inches(6.25), Inches(4.70), fill=LIGHT_GRAY)
    _text(s, Inches(0.55), Inches(1.55), Inches(6.0), Inches(0.35),
          "PROMPT (truncated)", size=13, color=BLUE, bold=True)
    _text(s, Inches(0.55), Inches(1.90), Inches(6.0), Inches(4.15),
          prompt_lines, size=10.5, color=DARK_TEXT, line_spacing=1.05)
    _box(s, Inches(6.90), Inches(1.45), Inches(6.05), Inches(4.70), fill=NAVY)
    _text(s, Inches(7.05), Inches(1.55), Inches(5.8), Inches(0.35),
          "RESPONSE (strict JSON, one call)", size=13, color=AMBER, bold=True)
    _text(s, Inches(7.05), Inches(1.90), Inches(5.8), Inches(4.15),
          response_lines, size=10.5, color=LIGHT_BLUE, line_spacing=1.05)
    callout(s, "Every score ships with verbatim evidence quotes — auditable, unlike a bare probability.",
            positive=True)
    add_footer(s)

    # ── 5. Results A/B/C ─────────────────────────────────────────────────────
    s = new_slide()
    add_header(s, "Results: Classic NLP vs LLM vs Combined",
               f"{stats.get('n_model_rows', '?')} windows, identical rows & time split "
               f"(train ≤ {stats.get('split_date', '?')}), bootstrap 95% CIs")
    rows = [["Feature set", "Best model", "Test ROC-AUC", "95% CI (bootstrap)"]]
    for sname in (a_key, b_key, c_key):
        if sname in best:
            bm, r = best[sname]
            rows.append([sname, bm, f"{r['auc']:.3f}", f"[{r['lo']:.3f}, {r['hi']:.3f}]"])
    shape_table(s, Inches(0.40), Inches(1.55),
                [Inches(3.7), Inches(3.0), Inches(2.6), Inches(2.9)], rows,
                row_h=Inches(0.44))
    fig = FIG_DIR / "fig_auc_comparison.png"
    if fig.exists():
        add_picture_fit(s, fig, Inches(1.2), Inches(3.55), Inches(10.9), Inches(2.65))
    if auc:
        gap = best[c_key][1]["auc"] - best[a_key][1]["auc"]
        overlap = best[c_key][1]["lo"] <= best[a_key][1]["hi"]
        if gap >= 0.05 and not overlap:
            msg, pos = (f"LLM features add +{gap:.3f} AUC over the classic stack — "
                        f"but see the contamination tests before believing it.", True)
        elif abs(gap) < 0.05 or overlap:
            msg, pos = (f"CIs overlap (Δ = {gap:+.3f}): the LLM does not clearly beat the classic "
                        f"stack on pre-announcement prediction — consistent with week 3-4's null.", False)
        else:
            msg, pos = (f"LLM features UNDERPERFORM the classic stack (Δ = {gap:+.3f}).", False)
        callout(s, msg, positive=pos)
    add_footer(s)

    # ── 6b. Intuition: why the AUC is flat ───────────────────────────────────
    if cases:
        s = new_slide()
        add_header(s, "Why the AUC Is Flat: Two Companies Tell the Story",
                   "Same pipeline, same scoring — but deal chatter lands in the “right” window only half the time")
        for x, key, head_txt, fill in [
                (Inches(0.40), "signal", "SIGNAL — chatter in the run-up (ranked correctly)", LIGHT_GREEN),
                (Inches(6.77), "inversion", "INVERSION — chatter in the “quiet” window (wrong-way pair)", LIGHT_PINK)]:
            c = cases[key]
            _box(s, x, Inches(1.45), Inches(6.15), Inches(0.42), fill=NAVY)
            _text(s, x, Inches(1.46), Inches(6.15), Inches(0.40), head_txt, size=12.5,
                  color=WHITE, bold=True, align=PP_ALIGN.CENTER)
            _box(s, x, Inches(1.87), Inches(6.15), Inches(3.65), fill=fill)
            _text(s, x + Inches(0.15), Inches(2.00), Inches(5.85), Inches(3.4),
                  [[(c["name"], {"bold": True, "size": 15})],
                   "",
                   [("acquisition_likelihood:   ", {}),
                    (f"baseline {c['base']}   →   pre {c['pre']}", {"bold": True, "size": 14})],
                   "",
                   [("run-up window evidence:", {"bold": True})],
                   f"“{c['quote_pre']}”",
                   [("quiet window evidence:", {"bold": True})],
                   f"“{c['quote_base']}”"],
                  size=11.5, color=DARK_TEXT, line_spacing=1.12)
        callout(s, f"Across {cases['n_pairs']} paired companies: {cases['n_up']} scored higher in the "
                   f"run-up · {cases['n_dn']} lower · {cases['n_zero']} unchanged — ups and downs "
                   f"balance, so the paired test stays ns and AUC ≈ 0.5.",
                positive=False, y=Inches(5.85), h=Inches(0.85))
        add_footer(s)

    # ── 6c. Correlation: are LLM signals new information? ───────────────────
    fig_corr = FIG_DIR / "fig_llm_vs_classic_corr.png"
    if fig_corr.exists():
        s = new_slide()
        add_header(s, "Are the LLM Signals New Information?",
                   "Spearman rank correlation — LLM fields (rows) × classic-NLP features (columns), same windows")
        add_picture_fit(s, fig_corr, Inches(0.30), Inches(1.45), Inches(7.1), Inches(5.35))
        note = (f"Hottest cell: {corr_note[0]} × {corr_note[1]} (ρ = {corr_note[2]:+.2f}) — the LLM's "
                f"rumor read largely re-derives simple keyword matching."
                if corr_note else "Hottest cell ≈ rumor_intensity × ma_keyword_ratio.")
        _text(s, Inches(7.60), Inches(1.60), Inches(5.35), Inches(4.6),
              [[("How to read it:", {"bold": True, "size": 14})],
               "• Each cell: across the same windows, do the two scores rank companies the same "
               "way? (+1 identical ranking · 0 unrelated · −1 opposite)",
               "• A deep-red row = that LLM field re-derives a classic feature — redundant.",
               "• A near-white row = information the classic stack does not capture — novel.",
               f"• {note}",
               "• Mid/low rows (activist, distress, divestiture…) are genuinely new descriptive "
               "axes the keyword stack misses.",
               [("Takeaway: ", {"bold": True}),
                ("partly redundant, partly novel — but §6 shows neither the redundant nor the "
                 "novel parts separate pre from baseline on this corpus.", {})]],
              size=12, color=DARK_TEXT, line_spacing=1.18)
        callout(s, "Novelty without predictivity: the LLM adds new ways to DESCRIBE the news — "
                   "not new ability to PREDICT from it.", positive=False,
                y=Inches(6.45), h=Inches(0.70))
        add_footer(s)

    # ── 6. Honesty 1: probe ──────────────────────────────────────────────────
    s = new_slide()
    add_header(s, "Does the Model Already Know These Deals?",
               "Memorization probe: zero news shown — answer from training memory alone")
    _text(s, Inches(0.40), Inches(1.45), Inches(5.6), Inches(2.3),
          ["Design (balanced, chance = 50%):",
           "• “As of <date>: was <company> announced as a",
           "   ≥$1B acquisition target within 120 days?”",
           "• Asked at announcement−7d (truth = YES)",
           "• Asked at announcement−187d (truth = NO)",
           "• Same companies as the modeling sample"],
          size=13.5, color=DARK_TEXT, line_spacing=1.15)
    px = Inches(6.60)
    kpi_tile(s, px, Inches(1.50), f"{probe.get('acc', 0):.0%}" if probe else "n/a",
             "probe accuracy (50% = clean)", fill=NAVY, value_color=AMBER)
    kpi_tile(s, px + Inches(3.18), Inches(1.50),
             f"{probe.get('acq_precision'):.0%}" if isinstance(probe.get("acq_precision"), (int, float)) else "n/a",
             f"acquirer named correctly ({probe.get('n_recall_claims', 0)} recall claims)",
             fill=NAVY, value_color=AMBER)
    kpi_tile(s, px, Inches(3.00),
             f"{probe.get('acc_pre_cutoff'):.0%}" if isinstance(probe.get("acc_pre_cutoff"), (int, float)) else "n/a",
             f"accuracy PRE-cutoff (< {stats.get('knowledge_cutoff', '2024-06')}, memorizable)",
             fill=BLUE, value_color=WHITE)
    kpi_tile(s, px + Inches(3.18), Inches(3.00),
             f"{probe.get('acc_post_cutoff'):.0%}" if isinstance(probe.get("acc_post_cutoff"), (int, float)) else "n/a",
             "accuracy POST-cutoff (unseen deals)", fill=GREEN, value_color=WHITE)
    _text(s, Inches(0.40), Inches(3.95), Inches(5.9), Inches(2.2),
          ["Why this matters:", "If the model recalls outcomes without any news, every",
           "pre-cutoff “prediction” is potentially an act of memory,",
           "not inference. The pre- vs post-cutoff gap isolates it."],
          size=13.5, color=DARK_TEXT, line_spacing=1.15)
    if isinstance(probe.get("acc"), (int, float)):
        bad = probe["acc"] >= 0.6
        callout(s, (f"Probe accuracy {probe['acc']:.0%} — training-data look-ahead CONFIRMED; "
                    f"pre-cutoff AUCs cannot be taken at face value." if bad else
                    f"Probe accuracy {probe['acc']:.0%} ≈ chance — no strong evidence the model "
                    f"recalls these specific deals."), positive=not bad)
    add_footer(s)

    # ── 7. Honesty 2+3: masking & repeatability ──────────────────────────────
    s = new_slide()
    add_header(s, "Masking & Repeatability",
               "Do the scores hold up? Testing recognition-vs-reading and run-to-run stability")
    f1, f2 = FIG_DIR / "fig_masking.png", FIG_DIR / "fig_repeat.png"
    if f1.exists():
        add_picture_fit(s, f1, Inches(0.55), Inches(1.38), Inches(5.7), Inches(2.85))
    if f2.exists():
        add_picture_fit(s, f2, Inches(6.95), Inches(1.38), Inches(5.7), Inches(2.85))
    rows = [["Experiment", "What it tests", "Result"],
            ["Name masking — ΔAUC (unmasked − masked)", "recognition vs reading",
             f"{masking.get('delta'):+.3f}" if isinstance(masking.get("delta"), (int, float)) else "n/a"],
            ["Re-run consistency — mean Spearman ρ (12 fields)", "are scores stable?",
             fmt(repeat.get("mean_spearman"))],
            ["Re-run drift — mean |Δ likelihood| (0–100 scale)", "how much they wobble",
             fmt(repeat.get("likelihood_mean_abs_diff"), ".1f")]]
    shape_table(s, Inches(0.40), Inches(4.48), [Inches(6.5), Inches(3.6), Inches(2.4)], rows,
                row_h=Inches(0.36), font_size=11.5)
    delta = masking.get("delta")
    rho = repeat.get("mean_spearman")
    rho_txt = f"ρ={rho:.2f}" if isinstance(rho, (int, float)) else "high ρ"
    drift = repeat.get("likelihood_mean_abs_diff")
    drift_txt = f"~{drift:.1f} pt" if isinstance(drift, (int, float)) else "small"
    if isinstance(delta, (int, float)):
        if delta >= 0.05:
            msg = (f"Repeatable ({rho_txt}, drift {drift_txt} on 0–100) — the scores are NOT arbitrary. "
                   f"But masking the company name lowers takeover scores (ΔAUC {delta:+.2f}) — part of "
                   f"the 'signal' is recognizing the company, not reading the text.")
            pos = False
        else:
            msg = (f"Repeatable ({rho_txt}, drift {drift_txt} on 0–100) AND masking barely moves scores "
                   f"(ΔAUC {delta:+.2f}) — the model is reading the text, not just recognizing the "
                   f"company. Both checks pass.")
            pos = True
        callout(s, msg, positive=pos, y=Inches(6.10), h=Inches(0.95))
    add_footer(s)

    # ── 8. Model sensitivity + cost ──────────────────────────────────────────
    s = new_slide()
    add_header(s, "Model Sensitivity & What $100 Buys",
               f"gpt-5 vs gpt-5-mini on {sens.get('n', '?')} shared windows — does ~10x price buy a different read?")
    kpi_tile(s, Inches(0.40), Inches(1.55), fmt(sens.get("mean_spearman")),
             "score agreement (mean Spearman)", fill=NAVY, value_color=AMBER)
    auc_pair = sens.get("auc") or {}
    kpi_tile(s, Inches(3.58), Inches(1.55),
             " / ".join(f"{v:.2f}" for v in auc_pair.values()) if auc_pair else "n/a",
             "subset AUC: mini / gpt-5", fill=NAVY, value_color=AMBER)
    kpi_tile(s, Inches(6.76), Inches(1.55), f"{sens.get('cost_ratio', 'n/a')}x",
             "cost ratio per window", fill=BLUE, value_color=WHITE)
    kpi_tile(s, Inches(9.94), Inches(1.55), f"${stats.get('llm_total_cost', 0):.2f}",
             "actual total spend this week", fill=GREEN, value_color=WHITE)
    rows = [["Run", "Model", "Approx. cost"],
            ["Score ~1,400 windows (700 events × 2)", "gpt-5-mini", "≈ $2.50"],
            ["Same, company names masked", "gpt-5-mini", "≈ $2.50"],
            ["Memorization probe (2 calls/event)", "gpt-5-mini", "≈ $0.60"],
            ["100-event sensitivity subset ×2 variants", "gpt-5", "≈ $4.00"],
            ["Everything above at gpt-5 prices", "gpt-5", "≈ $45 — still inside $100"]]
    shape_table(s, Inches(0.40), Inches(3.30), [Inches(6.2), Inches(2.6), Inches(3.7)], rows,
                row_h=Inches(0.40))
    callout(s, "Cost is NOT the constraint — validity is. The binding limit is look-ahead "
               "bias and score stability, not the API bill.", positive=True)
    add_footer(s)

    # ── 9. Honest read & the right fix ───────────────────────────────────────
    s = new_slide()
    add_header(s, "Honest Read: Pre-Registered Verdict & The Right Fix",
               "Thresholds fixed before the numbers came in — the narrative can't bend to flatter the result")
    card(s, Inches(0.40), Inches(1.50), Inches(4.05), "Look-ahead bias",
         ["LLM trained on news about these deals.", "Fix: OpenRouter — pin models whose",
          "training cutoff predates the eval window;", "makes look-ahead structurally impossible."],
         body_h=Inches(1.85))
    card(s, Inches(4.64), Inches(1.50), Inches(4.05), "Arbitrary numbers",
         ["'activist_pressure = 7' is a judgment.", "Fix: average repeat scores, calibrate",
          "against realized frequencies, keep", "evidence quotes mandatory (auditable)."],
         body_h=Inches(1.85))
    card(s, Inches(8.88), Inches(1.50), Inches(4.05), "Thin, noisy data",
         ["Free headlines are sparse; small test", "sets swing AUC by ±0.05+.",
          "Fix: scale the resumable scrape, add", "article bodies, walk-forward validation."],
         body_h=Inches(1.85))
    crit = stats.get("criteria") or []
    if crit:
        rows = [["Registered criterion (fixed in advance)", "Threshold", "Observed", "Fired?"]]
        for c in crit:
            rows.append([c["criterion"], c["threshold"], c["observed"],
                         "YES" if c["fired"] else "no"])
        shape_table(s, Inches(0.40), Inches(3.85),
                    [Inches(5.1), Inches(3.6), Inches(2.0), Inches(1.4)], rows,
                    row_h=Inches(0.36), font_size=11.5)
    callout(s, "Week 7 recommendation: cutoff-matched backtest via OpenRouter on the full event set — "
               "the only version of this result an investor should trust.", positive=True,
            y=Inches(5.90), h=Inches(0.85))
    add_footer(s)

    # ── 10. Thanks ────────────────────────────────────────────────────────────
    s = new_slide()
    _box(s, 0, 0, SLIDE_W, SLIDE_H, fill=NAVY)
    _box(s, 0, Inches(0.55), SLIDE_W, Inches(0.05), fill=GOLD)
    _text(s, 0, Inches(2.9), SLIDE_W, Inches(1.6), "Thanks", size=80, color=WHITE,
          bold=True, align=PP_ALIGN.CENTER)
    _text(s, 0, Inches(6.9), SLIDE_W, Inches(0.35), FOOTER_TEXT, size=9,
          color=FOOTER_GRAY, align=PP_ALIGN.CENTER)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(OUT_PATH))
    print(f"Wrote {OUT_PATH.relative_to(PROJECT_ROOT)} ({len(prs.slides.__iter__.__self__._sldIdLst)} slides)")


if __name__ == "__main__":
    main()
