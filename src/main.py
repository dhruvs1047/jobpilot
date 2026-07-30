"""
JobPilot orchestrator — runs the full daily pipeline:
  fetch -> score/dedupe -> tailor resume for strong matches -> notify + dashboard

Run locally with:  python -m src.main
Runs automatically via .github/workflows/daily_run.yml
"""
import json
import os

from src.config import load_config
from src.matcher import rank_postings
from src.notify import send_discord_digest, write_dashboard
from src.resume_writer import write_resume_docx
from src.sources.adzuna import AdzunaSource
from src.sources.jobbank import JobBankSource
from src.sources.magnet import MagnetSource
from src.tailor import tailor_resume_for_posting

SEEN_JOBS_PATH = "data/seen_jobs.json"
RESUME_BASE_PATH = "data/resume_base.json"
OUTPUT_DIR = "output/tailored_resumes"

SOURCES = {
    "adzuna": AdzunaSource,
    "jobbank": JobBankSource,
    "magnet": MagnetSource,
}


def load_seen_fingerprints() -> set[str]:
    if not os.path.exists(SEEN_JOBS_PATH):
        return set()
    with open(SEEN_JOBS_PATH, "r", encoding="utf-8") as f:
        return set(json.load(f))


def save_seen_fingerprints(fingerprints: set[str]):
    os.makedirs(os.path.dirname(SEEN_JOBS_PATH), exist_ok=True)
    with open(SEEN_JOBS_PATH, "w", encoding="utf-8") as f:
        json.dump(sorted(fingerprints), f, indent=2)


def main():
    config = load_config()

    all_postings = []
    for name, source_cls in SOURCES.items():
        if config["sources"].get(name, {}).get("enabled", False):
            all_postings.extend(source_cls().fetch(config))

    seen = load_seen_fingerprints()
    scored = rank_postings(all_postings, config, seen)

    print(f"[main] {len(scored)} new postings scored this run")

    threshold = config["search"].get("tailor_threshold", 65)
    strong_matches = [s for s in scored if s.score >= threshold]

    if strong_matches and os.path.exists(RESUME_BASE_PATH):
        with open(RESUME_BASE_PATH, "r", encoding="utf-8") as f:
            resume_base = json.load(f)

        os.makedirs(OUTPUT_DIR, exist_ok=True)
        for s in strong_matches:
            tailored = tailor_resume_for_posting(resume_base, s.posting)
            safe_name = "".join(
                c if c.isalnum() else "_" for c in f"{s.posting.company}_{s.posting.title}"
            )[:80]
            out_path = os.path.join(OUTPUT_DIR, f"{safe_name}.docx")
            write_resume_docx(tailored, out_path, job_title=s.posting.title)
            print(f"[main] Tailored resume written: {out_path}")

    write_dashboard(scored)
    send_discord_digest(scored, threshold)

    # mark everything we saw this run (not just matches) so we never re-alert on it
    new_fingerprints = seen | {s.posting.fingerprint() for s in scored}
    save_seen_fingerprints(new_fingerprints)


if __name__ == "__main__":
    main()
