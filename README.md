# JobPilot — Autonomous Job & Co-op Matching Pipeline

JobPilot searches multiple job boards every day, scores each posting against your
target roles/locations, and produces an ATS-tailored version of your resume for every
strong match — so all you have to do is review and hit submit.

It runs for free on a daily schedule using **GitHub Actions**, with results published
to a simple dashboard via **GitHub Pages** and pushed to **Discord** for instant alerts.

## Why this exists

Manually re-checking Job Bank, Indeed, and niche co-op boards every day (and hand-editing
a resume for each posting to survive an ATS keyword filter) doesn't scale. JobPilot
automates the repetitive 90%: discovery, scoring, and first-draft tailoring — while
keeping a human in the loop for the final decision to apply.

## Architecture

```
┌─────────────┐    ┌──────────────┐    ┌───────────────┐    ┌────────────────┐
│  Sources     │───▶│  Matcher     │───▶│  Tailor (LLM) │───▶│  Notify/Publish │
│ Adzuna API   │    │ keyword +    │    │ rewrites      │    │ Discord webhook │
│ Job Bank     │    │ location +   │    │ resume bullets│    │ GitHub Pages    │
│ Magnet       │    │ recency score│    │ per posting   │    │ dashboard       │
└─────────────┘    └──────────────┘    └───────────────┘    └────────────────┘
        ▲                                                            │
        └──────────────── runs daily via GitHub Actions cron ────────┘
```

| Stage | What it does | Tech |
|---|---|---|
| **Sources** | Pulls fresh postings from each configured board | Python + `requests` / free job APIs |
| **Matcher** | Scores each posting 0–100 against `config.yaml` (roles, locations, keywords) and flags duplicates already seen | Pure Python, no paid services |
| **Tailor** | For postings above the score threshold, rewrites your resume bullets to mirror the posting's language/keywords (ATS optimization) and generates a tailored `.docx` | Anthropic Claude API (or free Gemini API — swappable) |
| **Notify** | Posts a daily digest to Discord and updates a static dashboard | Discord webhook + GitHub Pages |

## Sources covered

| Source | Status | Method |
|---|---|---|
| Indeed / general job boards | ✅ Automated | Adzuna API (free tier, aggregates Indeed + others) |
| Job Bank — Canada Summer Jobs | ✅ Automated | Targeted search + fetch (Job Bank has no public API) |
| Magnet (magnet.today) | ✅ Automated (best-effort) | Public search page scrape |
| LinkedIn | ⚠️ Manual-check only | LinkedIn's ToS prohibits automated scraping — JobPilot instead generates a pre-filled saved-search link for you to check by hand |
| RBC / Workday-based co-op portals, WaterlooWorks-style boards | 🚧 Phase 2 | Most require an institutional login; see `src/sources/base.py` for how to add a new source |

## Making it your own (works for anyone, not just the original author)

JobPilot isn't hard-coded to one person's resume. The `src/onboard.py` script
takes any resume file(s) — PDF or DOCX, and you can pass several versions if
you've tailored your resume differently for different roles — and:

1. Extracts the text
2. Uses Claude to merge everything into one comprehensive, truthful master
   profile → writes `data/resume_base.json`
3. Uses Claude to suggest target job titles and ATS keywords based on that
   resume → writes them into `config.yaml`

Run it once, review the two files it touches (both are plain text — nothing
is locked in), and you're set up:

```bash
python -m src.onboard path/to/your_resume.pdf
# or, with multiple versions of your own resume:
python -m src.onboard resume_general.pdf resume_technical.pdf resume_sales.pdf
```

The one thing it can't infer from a resume alone is *where you want to work*
(a resume shows where you live, not necessarily your target search area) —
the script leaves a clear note to fill in `locations` in `config.yaml`
yourself.

## Setup (all free)

1. **Fork/clone this repo.**
2. **Get free API keys:**
   - [Adzuna](https://developer.adzuna.com/) — free developer account (app ID + key)
   - [Anthropic Console](https://console.anthropic.com/) (usage-based, a few cents/month for this volume) **or** [Google AI Studio](https://aistudio.google.com/) for a free-tier Gemini key — pick one, `src/tailor.py` supports both
   - A [Discord webhook URL](https://support.discord.com/hc/en-us/articles/228383668) for your own server (free, 2 minutes to set up)
3. **Add repo secrets** (Settings → Secrets and variables → Actions):
   - `ADZUNA_APP_ID`, `ADZUNA_APP_KEY`
   - `ANTHROPIC_API_KEY` (or `GEMINI_API_KEY`)
   - `DISCORD_WEBHOOK_URL`
4. **Fill in `data/resume_base.json`** with your real resume content (structured — see comments in the file).
5. **Edit `config.yaml`** with your target roles, locations, and keywords.
6. **Enable GitHub Pages** (Settings → Pages → source: `docs/` folder on `main`).
7. Push to `main` — the workflow in `.github/workflows/daily_run.yml` runs automatically every day at 8am ET, and can also be triggered manually from the Actions tab.

## Running locally

```bash
pip install -r requirements.txt
cp .env.example .env   # fill in your keys
python -m src.main
```

## Project structure

```
jobpilot/
├── .github/workflows/daily_run.yml   # cron automation
├── config.yaml                       # your search criteria
├── data/
│   ├── resume_base.json              # your resume, structured
│   └── seen_jobs.json                # dedupe state (auto-updated)
├── src/
│   ├── sources/                      # one module per job board
│   ├── matcher.py                    # scoring engine
│   ├── tailor.py                     # LLM resume tailoring
│   ├── resume_writer.py              # generates tailored .docx
│   ├── notify.py                     # Discord + dashboard
│   └── main.py                       # orchestrator
└── docs/index.html                   # published dashboard (GitHub Pages)
```

## Why this is worth putting on a resume/GitHub

This project demonstrates: API integration, ETL/data pipeline design, CI/CD via
GitHub Actions, prompt engineering for structured LLM output, and a real deployed
artifact (GitHub Pages dashboard) — not just a script that runs once.

## License

MIT
