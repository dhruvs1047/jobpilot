"""
Tailors a resume to a specific job posting: rewrites bullets to mirror the
posting's language/keywords (for ATS matching) AND selects only the most
relevant projects/leadership entries, so the output is a real ~1-page resume
rather than a dump of every bullet the candidate has ever written.

Everything here is one API call per posting — cheap and fast. Facts that
shouldn't change (contact info, education, certifications, skills list,
dates, organization names) are never touched by the model; only which items
are shown and how their bullets are worded is up to the model.

Env var required: ANTHROPIC_API_KEY
"""
import copy
import json
import os

import anthropic

MODEL = "claude-sonnet-4-6"

TAILOR_PROMPT = """You are tailoring a resume for one specific job posting. \
You will select the most relevant content and rewrite bullets to mirror the \
posting's own language (this helps pass ATS keyword filters) — but you must \
NEVER invent experience, skills, tools, or metrics that aren't already present \
in the candidate's master resume below. Only rephrase, reorder, and select \
from what's true.

Guidelines:
- Rewrite the summary (2-3 sentences) to foreground what's relevant to this posting.
- For EVERY entry under "experience", keep it (real work history is always shown) \
but select only its 2-3 most relevant bullets, reworded to mirror posting language.
- From "projects", select ONLY the 2-3 most relevant to this posting. Drop the rest. \
Keep 2-3 bullets each, reworded.
- From "leadership", select ONLY the 1-2 most relevant to this posting (or none, \
if nothing fits and experience/projects already make a strong case). Keep 1-2 \
bullets each, reworded.
- The goal is a resume a human could realistically read in under a minute — \
concise and relevant beats comprehensive.

JOB POSTING:
Title: {title}
Company: {company}
Description: {description}

CANDIDATE'S MASTER RESUME (source of truth — do not add facts not here):
{master_resume}

Return ONLY a JSON object with this exact shape (no markdown fences, no preamble):
{{
  "summary": "...",
  "experience": [{{"id": "...", "bullets": ["...", "..."]}}],
  "projects": [{{"name": "...", "bullets": ["...", "..."]}}],
  "leadership": [{{"organization": "...", "bullets": ["...", "..."]}}]
}}
The "id"/"name"/"organization" values must exactly match ones from the master \
resume so they can be matched back up.
"""


def _call_claude(client: anthropic.Anthropic, prompt: str, max_tokens: int) -> dict:
    response = client.messages.create(
        model=MODEL, max_tokens=max_tokens, messages=[{"role": "user", "content": prompt}]
    )
    raw = "".join(b.text for b in response.content if b.type == "text").strip()
    raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    return json.loads(raw)


def tailor_resume_for_posting(resume: dict, posting) -> dict:
    """Returns a new resume dict: same contact/education/certifications/skills/
    additional as the master, but with summary/experience/projects/leadership
    selected and rewritten for this specific posting."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("[tailor] ANTHROPIC_API_KEY not set — using master resume unchanged")
        return copy.deepcopy(resume)

    client = anthropic.Anthropic(api_key=api_key)
    prompt = TAILOR_PROMPT.format(
        title=posting.title,
        company=posting.company,
        description=posting.description[:3000],
        master_resume=json.dumps(resume, indent=2),
    )

    try:
        result = _call_claude(client, prompt, max_tokens=2000)
    except (json.JSONDecodeError, anthropic.APIError) as e:
        print(f"[tailor] LLM tailoring failed ({e}) — using master resume unchanged")
        return copy.deepcopy(resume)

    tailored = copy.deepcopy(resume)
    tailored["summary"] = result.get("summary", resume.get("summary", ""))

    # Map tailored bullets back onto the matching master entries, by id/name.
    exp_by_id = {e["id"]: e for e in resume.get("experience", [])}
    tailored["experience"] = []
    for item in result.get("experience", []):
        base = exp_by_id.get(item.get("id"))
        if base:
            entry = copy.deepcopy(base)
            entry["bullets"] = item.get("bullets", entry["bullets"])
            tailored["experience"].append(entry)
    if not tailored["experience"]:
        tailored["experience"] = copy.deepcopy(resume.get("experience", []))

    proj_by_name = {p["name"]: p for p in resume.get("projects", [])}
    tailored["projects"] = []
    for item in result.get("projects", []):
        base = proj_by_name.get(item.get("name"))
        if base:
            entry = copy.deepcopy(base)
            entry["bullets"] = item.get("bullets", entry["bullets"])
            tailored["projects"].append(entry)

    lead_by_org = {l["organization"]: l for l in resume.get("leadership", [])}
    tailored["leadership"] = []
    for item in result.get("leadership", []):
        base = lead_by_org.get(item.get("organization"))
        if base:
            entry = copy.deepcopy(base)
            entry["bullets"] = item.get("bullets", entry["bullets"])
            tailored["leadership"].append(entry)

    return tailored
