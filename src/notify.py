"""
Sends a daily digest to Discord and regenerates the static dashboard in docs/
(served for free via GitHub Pages).
"""
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


def write_dashboard(scored_postings, output_dir: str = "docs"):
    """Regenerates docs/index.html — a plain static page GitHub Pages can serve."""
    rows = []
    for s in scored_postings:
        p = s.posting
        rows.append(
            f"""
            <tr>
              <td>{s.score}</td>
              <td><a href="{p.url}" target="_blank" rel="noopener">{p.title}</a></td>
              <td>{p.company}</td>
              <td>{p.location}</td>
              <td>{p.source}</td>
            </tr>"""
        )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>JobPilot Dashboard</title>
<style>
  body {{ font-family: -apple-system, Segoe UI, Roboto, sans-serif; margin: 2rem;
          background: #fafafa; color: #222; }}
  h1 {{ font-size: 1.4rem; }}
  table {{ border-collapse: collapse; width: 100%; background: white; }}
  th, td {{ text-align: left; padding: 8px 12px; border-bottom: 1px solid #eee;
            font-size: 0.9rem; }}
  th {{ background: #222; color: white; }}
  tr:hover {{ background: #f5f5f5; }}
  .updated {{ color: #666; font-size: 0.85rem; margin-bottom: 1rem; }}
</style>
</head>
<body>
  <h1>JobPilot — Matched Postings</h1>
  <p class="updated">Last updated: {datetime.now(timezone.utc).isoformat(timespec="minutes")} UTC</p>
  <table>
    <thead>
      <tr><th>Score</th><th>Title</th><th>Company</th><th>Location</th><th>Source</th></tr>
    </thead>
    <tbody>
      {''.join(rows) if rows else '<tr><td colspan="5">No matches yet.</td></tr>'}
    </tbody>
  </table>
</body>
</html>
"""
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, "index.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[notify] Dashboard written to {path}")
