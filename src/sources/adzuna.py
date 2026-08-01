"""
Adzuna API connector.

Adzuna aggregates postings from Indeed and many other boards and offers a free
developer tier (generous request quota, no cost). Sign up: https://developer.adzuna.com/

Env vars required: ADZUNA_APP_ID, ADZUNA_APP_KEY
"""
import os
import requests

from .base import JobSource, JobPosting, infer_job_type

BASE_URL = "https://api.adzuna.com/v1/api/jobs/{country}/search/1"


class AdzunaSource(JobSource):
    name = "adzuna"

    def fetch(self, config: dict) -> list[JobPosting]:
        app_id = os.environ.get("ADZUNA_APP_ID")
        app_key = os.environ.get("ADZUNA_APP_KEY")
        if not app_id or not app_key:
            print("[adzuna] Skipping — ADZUNA_APP_ID / ADZUNA_APP_KEY not set")
            return []

        country = config["sources"]["adzuna"].get("country", "ca")
        roles = config["search"]["roles"]
        locations = config["search"]["locations"]
        radius = config["search"].get("location_radius_km", 30)
        max_age = config["search"].get("max_posting_age_days", 14)

        postings: list[JobPosting] = []
        seen_urls = set()

        for role in roles:
            for location in locations:
                if location.lower() == "remote":
                    params = {
                        "app_id": app_id,
                        "app_key": app_key,
                        "what": role,
                        "where": "Canada",
                        "max_days_old": max_age,
                        "results_per_page": 20,
                        "content-type": "application/json",
                    }
                else:
                    params = {
                        "app_id": app_id,
                        "app_key": app_key,
                        "what": role,
                        "where": location,
                        "distance": radius,
                        "max_days_old": max_age,
                        "results_per_page": 20,
                        "content-type": "application/json",
                    }

                try:
                    resp = requests.get(
                        BASE_URL.format(country=country), params=params, timeout=20
                    )
                    resp.raise_for_status()
                    data = resp.json()
                except requests.RequestException as e:
                    print(f"[adzuna] Request failed for '{role}' in '{location}': {e}")
                    continue

                for item in data.get("results", []):
                    url = item.get("redirect_url", "")
                    if url in seen_urls:
                        continue
                    seen_urls.add(url)

                    title = item.get("title", "").strip()
                    description = item.get("description", "")
                    explicit_type = _adzuna_job_type(item)

                    postings.append(
                        JobPosting(
                            source="adzuna",
                            title=title,
                            company=(item.get("company") or {}).get(
                                "display_name", "Unknown"
                            ),
                            location=(item.get("location") or {}).get(
                                "display_name", location
                            ),
                            url=url,
                            description=description,
                            posted_date=item.get("created"),
                            external_id=str(item.get("id")),
                            salary=_format_salary(item),
                            salary_min=item.get("salary_min"),
                            job_type=infer_job_type(title, description, explicit_type),
                        )
                    )

        print(f"[adzuna] Fetched {len(postings)} unique postings")
        return postings


def _adzuna_job_type(item: dict) -> str | None:
    contract_type = (item.get("contract_type") or "").lower()   # permanent / contract
    contract_time = (item.get("contract_time") or "").lower()   # full_time / part_time
    if contract_type == "contract":
        return "Contract"
    if contract_time == "part_time":
        return "Part-time"
    if contract_time == "full_time":
        return "Full-time"
    return None


def _format_salary(item: dict) -> str | None:
    lo, hi = item.get("salary_min"), item.get("salary_max")
    if lo and hi:
        return f"${lo:,.0f}–${hi:,.0f}"
    return None
