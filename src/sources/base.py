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

    def fingerprint(self) -> str:
        """Stable id used for de-duplication across daily runs."""
        base = f"{self.source}|{self.title}|{self.company}|{self.url}"
        return base.lower().strip()


class JobSource:
    name = "base"

    def fetch(self, config: dict) -> list[JobPosting]:
        raise NotImplementedError
