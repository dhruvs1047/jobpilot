"""
Shared data model + base class for job source connectors.

To add a new source (e.g. a Workday-based company careers page):
1. Create src/sources/your_source.py
2. Subclass JobSource and implement fetch()
3. Return a list of JobPosting objects
4. Register it in src/main.py
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class JobPosting:
    source: str
    title: str
    company: str
    location: str
    url: str
    description: str
    posted_date: Optional[str] = None
    external_id: Optional[str] = None
    salary: Optional[str] = None
    salary_min: Optional[float] = None  # numeric, for filtering — None if unknown
    job_type: Optional[str] = None  # e.g. "Full-time", "Part-time", "Internship", "Contract"

    def fingerprint(self) -> str:
        """Stable id used for de-duplication across daily runs."""
        base = f"{self.source}|{self.title}|{self.company}|{self.url}"
        return base.lower().strip()


class JobSource:
    name = "base"

    def fetch(self, config: dict) -> list[JobPosting]:
        raise NotImplementedError


def infer_job_type(title: str, description: str = "", explicit: Optional[str] = None) -> str:
    """Best-effort job type label. Prefers an explicit value from the source's
    own API (most reliable); falls back to keyword matching on the posting
    text (used for sources with no structured field, e.g. scraped boards)."""
    if explicit:
        return explicit

    text = f"{title} {description}".lower()
    if "internship" in text or "intern " in text or text.startswith("intern"):
        return "Internship"
    if "co-op" in text or "coop" in text:
        return "Co-op"
    if "part-time" in text or "part time" in text:
        return "Part-time"
    if "contract" in text or "temporary" in text or "temp " in text:
        return "Contract"
    if "full-time" in text or "full time" in text:
        return "Full-time"
    return "Not specified"
