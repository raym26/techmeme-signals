# techmeme-signals

Turns a daily Techmeme newsletter digest into weekly investment signal analysis, delivered as an email plus rows in a Google Sheet.

Originally an n8n workflow (`techmeme_market_signals_n8n.json`, kept in this repo for reference — not executed by anything here), ported to a plain Python script.

## How it works

Two independent pipelines share one Google Sheet, scheduled together by `main.py`:

- **Daily ingest** (`ingest_pipeline.py`, runs at 21:00): reads unprocessed Techmeme digest emails over IMAP, extracts structured signal rows via Claude (headline, company, category, sentiment, ticker, signal strength, ...), and appends them to the sheet. Dedup is via a Gmail label the script manages itself, not the read/unread flag — so reading the digest in Gmail before the job runs doesn't cause it to be skipped. Bounded to the last 4 weeks of mail; older backlog is left alone.
- **Weekly report** (`pipeline.py`, runs Fridays at 17:45): reads the accumulated signals, sends them to Claude for analysis, and emails back a narrative report — buy/sell signals by sector, crypto implications, second-order-effect picks worth investigating, and a short **AI Watch** section (2-3 notable AI developments from the week, picked for being interesting rather than for their investment angle) — plus a structured table of ticker-level recommendations. Older signals are pruned from the sheet on a rolling window after each run.

See `CLAUDE.md` for the full architecture writeup, key gotchas, and manual commands.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# fill in: ANTHROPIC_API_KEY, GOOGLE_SERVICE_ACCOUNT_FILE + GOOGLE_SHEET_ID,
# GMAIL_ADDRESS + GMAIL_APP_PASSWORD (generate one at myaccount.google.com/apppasswords)
```

`config.py` fails fast if a required env var is missing.

## Running it

```bash
# One manual daily ingest pass
python -c "from ingest_pipeline import run; run()"

# One manual weekly report pass
python -c "from pipeline import run; run()"

# Long-running scheduler (daily ingest 21:00, weekly report Fri 17:45) --
# meant to run continuously in a background terminal (tmux/screen)
python main.py
```

## Roadmap

- **Multi-newsletter ingest.** Techmeme is the first source; the ingest side is meant to generalize to other e-newsletters over time, so a single pipeline can pull signals from more than one daily digest rather than being Techmeme-specific.
