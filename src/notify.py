"""
Sends a daily digest to Discord and writes docs/data.json — the data file the
static dashboard (docs/index.html) fetches and renders client-side.

Splitting data (this file) from presentation (docs/index.html, which is
handwritten once and never regenerated) keeps every daily run fast and keeps
the dashboard's design stable across runs.
"""
import json
import os
from datetime import datetime, timezone

import requests


def send_discord_digest(scored_postings, threshold: int):
    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL")
    if not webhook_url:
        print("[notify] DISCORD_WEBHOOK_URL not set — skipping Discord digest")
        return

    strong_matches = [s for s in scored_postings if s.score >= threshold]
    if not strong_matches:
        content = "**JobPilot daily run:** no new strong matches today."
    else:
        lines = [f"**JobPilot found {len(strong_matches)} new strong matches:**\n"]
        for s in strong_matches[:10]:
            lines.append(
                f"• **{s.score}/100** — [{s.posting.title} @ {s.posting.company}]"
                f"({s.posting.url}) ({s.posting.location})"
            )
        content = "\n".join(lines)

    try:
        requests.post(webhook_url, json={"content": content}, timeout=10)
    except requests.RequestException as e:
        print(f"[notify] Discord post failed: {e}")


def write_data_json(scored_postings, output_dir: str = "docs"):
    """Writes docs/data.json — consumed by the dashboard's client-side JS."""
    jobs = []
    for s in scored_postings:
        p = s.posting
        jobs.append(
            {
                "score": s.score,
                "title": p.title,
                "company": p.company,
                "location": p.location,
                "url": p.url,
                "source": p.source,
                "salary": p.salary,
                "salary_min": p.salary_min,
                "job_type": p.job_type,
                "posted_date": p.posted_date,
                "description": (p.description or "")[:400],
                "matched_keywords": s.matched_keywords,
            }
        )

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="minutes"),
        "count": len(jobs),
        "jobs": jobs,
    }

    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, "data.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    print(f"[notify] Wrote {len(jobs)} postings to {path}")
