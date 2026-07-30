"""
Onboarding script — this is what makes JobPilot usable by anyone, not just the
original author. Point it at one or more resume files (PDF or DOCX — pass
multiple if you have different tailored versions of your own resume) and it will:

  1. Extract the text from each file
  2. Use Claude to merge them into ONE comprehensive, truthful master resume,
     written to data/resume_base.json
  3. Use Claude to suggest target job titles and ATS keywords based on that
     resume, and write them into config.yaml
  4. Leave a clear TODO for the one thing it can't infer from a resume:
     your target locations (a resume tells you where someone *is*, not
     necessarily where they want to *work*)

Nothing is auto-submitted or auto-decided permanently — config.yaml and
data/resume_base.json are both plain text files you can open and edit by hand
at any time after this runs.

Usage:
    python -m src.onboard path/to/resume.pdf
    python -m src.onboard resume_v1.pdf resume_v2.pdf resume_v3.docx

Requires ANTHROPIC_API_KEY to be set in your environment (or .env file).
"""
import json
import os
import sys

import anthropic
import yaml
from pypdf import PdfReader
from docx import Document as DocxDocument

MODEL = "claude-sonnet-4-6"

RESUME_SCHEMA_EXAMPLE = """
{
  "contact": {"name": "", "email": "", "phone": "", "location": "", "linkedin": "", "github": ""},
  "summary": "2-3 sentence professional summary",
  "education": [{"institution": "", "location": "", "program": "", "dates": "", "notes": ["..."]}],
  "experience": [{"id": "short_slug", "organization": "", "location": "", "role": "", "dates": "", "bullets": ["..."]}],
  "projects": [{"name": "", "dates": "", "bullets": ["..."], "tech": ["..."]}],
  "leadership": [{"organization": "", "role": "", "dates": "", "bullets": ["..."]}],
  "certifications": ["..."],
  "skills": {"languages": ["..."], "libraries_and_tools": ["..."], "concepts": ["..."]},
  "additional": {"languages_spoken": {"fluent": ["..."], "basic": ["..."]}, "interests": ["..."]}
}
"""

MERGE_PROMPT = """You will be given one or more versions of the same person's \
resume (they may be tailored differently for different roles, e.g. one for \
software jobs, one for sales, one for admin work). Merge them into ONE \
comprehensive, maximally detailed, truthful master resume.

Rules:
- Never invent information that isn't present in at least one input version.
- Where the same bullet appears in different phrasings across versions, keep \
the most detailed/specific version.
- Where different versions include different bullets for the same role \
(because they emphasized different angles), include ALL of them — the goal is \
maximum truthful detail; JobPilot will pick which parts to emphasize per job \
posting later.
- Output ONLY a JSON object matching this shape (no markdown fences, no \
preamble):

{schema}

RESUME VERSIONS:
{resumes}
"""

FILTERS_PROMPT = """Based on this resume, suggest a job search configuration \
for an autonomous job-matching tool.

RESUME:
{resume_json}

Return ONLY a JSON object (no markdown fences, no preamble):
{{
  "suggested_roles": ["8-12 specific job titles this person is qualified for \
and would plausibly want, ranging across any distinct career directions \
visible in the resume (e.g. don't only suggest software roles if the resume \
also shows sales/admin/instruction experience)"],
  "suggested_keywords": ["15-20 skills/tools/certifications from the resume \
that are worth scoring job postings against"]
}}
"""


def extract_text(path: str) -> str:
    if path.lower().endswith(".pdf"):
        reader = PdfReader(path)
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    elif path.lower().endswith(".docx"):
        doc = DocxDocument(path)
        return "\n".join(p.text for p in doc.paragraphs)
    else:
        raise ValueError(f"Unsupported file type (need .pdf or .docx): {path}")


def call_claude(client: anthropic.Anthropic, prompt: str, max_tokens: int) -> dict:
    response = client.messages.create(
        model=MODEL, max_tokens=max_tokens, messages=[{"role": "user", "content": prompt}]
    )
    raw = "".join(b.text for b in response.content if b.type == "text").strip()
    raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    return json.loads(raw)


def build_master_resume(client: anthropic.Anthropic, resume_texts: list[str]) -> dict:
    combined = "\n\n=== NEXT RESUME VERSION ===\n\n".join(resume_texts)
    prompt = MERGE_PROMPT.format(schema=RESUME_SCHEMA_EXAMPLE, resumes=combined)
    return call_claude(client, prompt, max_tokens=4000)


def suggest_search_filters(client: anthropic.Anthropic, resume: dict) -> dict:
    prompt = FILTERS_PROMPT.format(resume_json=json.dumps(resume, indent=2)[:6000])
    return call_claude(client, prompt, max_tokens=1000)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: set ANTHROPIC_API_KEY in your environment (or .env file) first.")
        sys.exit(1)

    paths = sys.argv[1:]
    for p in paths:
        if not os.path.exists(p):
            print(f"ERROR: file not found: {p}")
            sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)

    print(f"Reading {len(paths)} resume file(s)...")
    texts = [extract_text(p) for p in paths]

    print("Merging into a master resume profile (this calls Claude, takes ~10-20s)...")
    resume = build_master_resume(client, texts)

    os.makedirs("data", exist_ok=True)
    with open("data/resume_base.json", "w", encoding="utf-8") as f:
        json.dump(resume, f, indent=2)
    print("✓ Wrote data/resume_base.json")

    print("Suggesting job search filters based on your resume...")
    filters = suggest_search_filters(client, resume)

    with open("config.yaml", "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    config["search"]["roles"] = filters.get("suggested_roles", config["search"]["roles"])
    config["search"]["boost_keywords"] = filters.get(
        "suggested_keywords", config["search"]["boost_keywords"]
    )

    with open("config.yaml", "w", encoding="utf-8") as f:
        yaml.dump(config, f, sort_keys=False, allow_unicode=True)
    print("✓ Updated config.yaml with suggested roles & keywords")

    print(
        "\nDone. Two things worth reviewing before your first run:\n"
        "  1. config.yaml -> 'locations': a resume shows where you ARE, not "
        "necessarily where you want to work. Set your real target locations.\n"
        "  2. config.yaml -> 'roles'/'boost_keywords': these are AI-suggested "
        "based on your resume — skim them and edit/add anything.\n"
        "Everything else is ready. Run: python -m src.main"
    )


if __name__ == "__main__":
    main()
