"""
Job Bank connector.

Job Bank (jobbank.gc.ca) has no public API, so this hits the public search-results
HTML page directly (same page a browser loads) and parses job cards. This is a
best-effort scraper — Job Bank's markup does change occasionally, so if this starts
returning 0 results, check SEARCH_URL / the CSS selectors below first.

No API key required.
"""
import requests
from bs4 import BeautifulSoup

from .base import JobSource, JobPosting, infer_job_type

SEARCH_URL = "https://www.jobbank.gc.ca/jobsearch/jobsearch"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}


class JobBankSource(JobSource):
    name = "jobbank"

    def fetch(self, config: dict) -> list[JobPosting]:
        keywords = config["sources"]["jobbank"].get("keywords", ["student"])
        roles = config["search"]["roles"]
        locations = config["search"]["locations"]

        postings: list[JobPosting] = []
        seen_ids = set()

        for role in roles:
            for location in locations:
                if location.lower() == "remote":
                    loc_param = "Canada"
                else:
                    loc_param = location.split(",")[0]  # jobbank wants city name

                query = role
                if any(k.lower() in role.lower() for k in keywords) is False:
                    query = f"{role}"

                params = {
                    "searchstring": query,
                    "locationstring": loc_param,
                    "sort": "M",  # most recent first
                }

                try:
                    resp = requests.get(
                        SEARCH_URL, params=params, headers=HEADERS, timeout=20
                    )
                    resp.raise_for_status()
                except requests.RequestException as e:
                    print(f"[jobbank] Request failed for '{role}' in '{location}': {e}")
                    continue

                soup = BeautifulSoup(resp.text, "html.parser")
                cards = soup.select("article.resultJobItem")

                for card in cards:
                    link_el = card.select_one("a.resultJobItemTitle")
                    if not link_el:
                        continue
                    job_id = card.get("id", link_el.get("href", ""))
                    if job_id in seen_ids:
                        continue
                    seen_ids.add(job_id)

                    title = link_el.get_text(strip=True)
                    href = link_el.get("href", "")
                    url = (
                        f"https://www.jobbank.gc.ca{href}"
                        if href.startswith("/")
                        else href
                    )
                    company_el = card.select_one("li.business")
                    location_el = card.select_one("li.location")
                    summary_el = card.select_one("span.job-desc-text")
                    description = summary_el.get_text(strip=True) if summary_el else ""

                    postings.append(
                        JobPosting(
                            source="jobbank",
                            title=title,
                            company=company_el.get_text(strip=True)
                            if company_el
                            else "Unknown",
                            location=location_el.get_text(strip=True)
                            if location_el
                            else location,
                            url=url,
                            description=description,
                            external_id=job_id,
                            job_type=infer_job_type(title, description),
                        )
                    )

        print(f"[jobbank] Fetched {len(postings)} unique postings")
        return postings
