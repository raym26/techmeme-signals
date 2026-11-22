# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A Python port of an n8n workflow (`techmeme_market_signals_n8n.json`, kept for reference — not executed by anything here) that turns a daily Techmeme newsletter digest into weekly investment signal analysis, delivered as an email plus rows in a Google Sheet.

## Commands

No test suite, linter, or build step exists yet — this is a plain Python script project running out of `.venv`.

```bash
source .venv/bin/activate
pip install -r requirements.txt

# Run one full weekly analysis pass manually (reads Sheet3, calls Claude, appends
# WeeklyReports, emails, prunes Sheet3)
python -c "from pipeline import run; run()"

# Run one daily ingest pass manually (reads unprocessed Techmeme digest emails via IMAP,
# extracts signals via Claude, appends to Sheet3, labels those emails processed)
python -c "from ingest_pipeline import run; run()"

# main.py (APScheduler, long-running foreground/background process) is NOT what's
# actually deployed -- see "Scheduling" below. It's kept as a manual alternative,
# e.g. for running both jobs continuously on a non-macOS box.
python main.py
```

Config lives in `.env` (see `.env.example`); `config.py` fails fast if a required var is missing.

## Scheduling

Production scheduling is two launchd LaunchAgents, not `main.py`. `launchd/com.raymundo.techmeme-daily-ingest.plist` and `launchd/com.raymundo.techmeme-weekly-report.plist` are installed under `~/Library/LaunchAgents` and each fire `scripts/run_pipeline.sh` at the same times `main.py` uses (daily ingest 21:00, weekly report Fri 17:45) — check with `launchctl list | grep techmeme`. Each firing execs a fresh one-shot `python3 -c "..."` process (`scripts/run_pipeline.sh`), not a persistent daemon, so a code change takes effect on the next scheduled run automatically; there is nothing to "restart." `main.py`'s APScheduler loop duplicates this schedule but is not what's running — don't assume it's live without checking `launchctl list` first.

`scripts/run_pipeline.sh` also polls (`.venv/bin/python3 -c "pass"`, up to 20x15s) before running: launchd fires right after a `pmset`-scheduled wake, and with FileVault on, the encrypted volume can still be settling then, raising `OSError: [Errno 11] Resource deadlock avoided` when the venv's site files are read before it's ready.

## Architecture

Two independent pipelines share one Google Sheet (`GOOGLE_SHEET_ID`).

**Daily ingest** (`ingest_pipeline.py`): `gmail_reader.py` (IMAP, authenticated with the same Gmail App Password used for outbound mail) pulls Techmeme digest emails not yet tagged `config.TECHMEME_PROCESSED_LABEL`, bounded to the last `config.ROLLING_WINDOW_DAYS` (via Gmail's `after:` search) → `extractor.py` (Claude Haiku 5.5, `config.EXTRACTOR_MODEL`, `output_config.format` JSON schema) turns the raw digest text into rows matching Sheet3's schema (`sheets_client.SIGNAL_COLUMNS`) → appended to Sheet3, emails labeled processed. It processes every unprocessed digest found within that window, oldest first, so a missed day catches up automatically in one run; older unprocessed digests are deliberately left alone (not labeled, not deleted) rather than backfilled, since they'd just be pruned from Sheet3 by the next weekly run anyway.

**Weekly report** (`pipeline.py`, Fridays 17:45): reads all of Sheet3 → `aggregate.py` splits signals into `current_week` (full detail, last `config.CURRENT_WEEK_DAYS`) vs `prior_weeks_summary` (aggregate counts + high-value signals only, for the rest of the rolling window) — this tiering keeps the prompt bounded regardless of how much has accumulated, while still surfacing multi-week momentum → `analyzer.py` (Claude Sonnet 5.5, `config.ANALYZER_MODEL`, structured output: `narrative_markdown` + `recommendations[]` + `market_summary`; the narrative's five required sections include an **AI WATCH** section — 2-3 notable AI developments picked for interest, not investment relevance, deliberately outside the market-signal framing of the other sections) → `recommendations.py` maps the structured `recommendations` onto WeeklyReports rows → `html_report.py` renders `narrative_markdown` via the `markdown` library and builds a separate deterministic HTML table from the structured `recommendations` array → emailed via `emailer.py` (SMTP, Gmail App Password) → `sheets_client.prune_signal_rows()` drops signals older than `config.ROLLING_WINDOW_DAYS` (default 28).

**Sheet3 is a rolling window, not a weekly-reset sheet.** Signals accumulate across `ROLLING_WINDOW_DAYS` and are only pruned by the weekly pipeline — the daily ingest never deletes anything.

## Key gotchas

- **Sheets writes must use `valueInputOption="RAW"`, never `"USER_ENTERED"`.** `USER_ENTERED` makes Sheets interpret values the way a human typing them would — a `"2026-06-27"` date string silently converts to Sheets' internal date-serial type, breaking every date comparison downstream (`aggregate.py`'s current/prior-week split, `prune_signal_rows`'s cutoff filter). This already happened once in production and required a live-data repair. `sheets_client.py` uses `RAW` everywhere for exactly this reason.
- **`recommendations.py` maps structured data; it does not parse text.** An earlier version regex-scanned Claude's freeform markdown for BUY/SELL sections (ported from the original n8n "Code" node) — this was demonstrably unreliable in practice (duplicated content, truncated output, wrong ticker extraction). `analyzer.py` now asks Claude for structured JSON directly via `output_config.format`.
- **`narrative_markdown` must not restate the recommendations table in prose.** The prompt in `analyzer.py` explicitly forbids a "top stock recommendations" section in the narrative — that data lives only in the structured `recommendations` array and is rendered as its own table in `html_report.py`. Duplicating it in prose is what caused the response to run out of tokens and drop the second-order-effects section before this was fixed.
- **The daily ingest dedups via a dedicated Gmail label (`config.TECHMEME_PROCESSED_LABEL`, default `techmeme-processed`), not the read/unread flag.** An earlier version used IMAP `UNSEEN` search, which silently skipped any digest the user read in Gmail before the 21:00 job ran — read state and "already ingested" are not the same thing. `gmail_reader.fetch_unprocessed_digests()` searches for Techmeme mail lacking that label (via Gmail's `X-GM-RAW`/`X-GM-LABELS` IMAP extensions) and `mark_as_processed()` applies it after a digest's signals are written to Sheet3. Removing the label from a Techmeme email will cause it to be reprocessed (and re-appended to Sheet3) on the next scheduled run.
