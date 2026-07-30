"""
Magnet (magnet.today) connector — Canadian job board popular for co-ops/internships.

Best-effort public-page scrape, same caveat as jobbank.py: if Magnet redesigns
their search page, update the selectors below.
"""
import requests
from bs4 import BeautifulSoup

from .base import JobSource, JobPosting

SEARCH_URL = "https://magnet.today/en/jobs"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}


class MagnetSource(JobSource):
    name = "magnet"

    def fetch(self, config: dict) -> list[JobPosting]:
        roles = config["search"]["roles"]
        postings: list[JobPosting] = []
        seen_ids = set()

        for role in roles:
            params = {"q": role}
            try:
                resp = requests.get(
                    SEARCH_URL, params=params, headers=HEADERS, timeout=20
                )
                resp.raise_for_status()
            except requests.RequestException as e:
                print(f"[magnet] Request failed for '{role}': {e}")
                continue

            soup = BeautifulSoup(resp.text, "html.parser")
            cards = soup.select("div.job-card, article.job-listing")

            for card in cards:
                link_el = card.select_one("a")
                if not link_el:
                    continue
                href = link_el.get("href", "")
                if href in seen_ids:
                    continue
                seen_ids.add(href)

                title_el = card.select_one("h2, h3, .job-title")
                company_el = card.select_one(".company, .employer-name")
                location_el = card.select_one(".location")

                url = (
                    f"https://magnet.today{href}"
                    if href.startswith("/")
                    else href
                )

                postings.append(
                    JobPosting(
                        source="magnet",
                        title=title_el.get_text(strip=True) if title_el else role,
                        company=company_el.get_text(strip=True)
                        if company_el
                        else "Unknown",
                        location=location_el.get_text(strip=True)
                        if location_el
                        else "",
                        url=url,
                        description="",
                        external_id=href,
                    )
                )

        print(f"[magnet] Fetched {len(postings)} unique postings")
        return postings
