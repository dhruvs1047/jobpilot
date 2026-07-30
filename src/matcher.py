"""
Scores each JobPosting 0-100 against config.yaml criteria. Pure keyword/heuristic
matching — no external API calls, so this stage is free and fast even with
hundreds of postings.
"""
import re
from dataclasses import dataclass

from src.sources.base import JobPosting


@dataclass
class ScoredPosting:
    posting: JobPosting
    score: int
    matched_keywords: list[str]


def _normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]", " ", text.lower())


def score_posting(posting: JobPosting, config: dict) -> ScoredPosting:
    text = _normalize(f"{posting.title} {posting.description}")
    location_text = _normalize(posting.location)

    score = 0
    matched: list[str] = []

    # 1. Role relevance (up to 40 pts) — does the title/description contain
    #    one of the target role phrases?
    roles = config["search"]["roles"]
    for role in roles:
        role_norm = _normalize(role)
        if role_norm in text:
            score += 40
            matched.append(role)
            break
    else:
        # partial credit if most words of a role phrase appear
        for role in roles:
            words = _normalize(role).split()
            hits = sum(1 for w in words if w in text)
            if words and hits / len(words) >= 0.6:
                score += 20
                matched.append(f"{role} (partial)")
                break

    # 2. Location relevance (up to 25 pts)
    locations = config["search"]["locations"]
    for loc in locations:
        if loc.lower() == "remote" and "remote" in text:
            score += 25
            break
        city = _normalize(loc.split(",")[0])
        if city and city in location_text:
            score += 25
            break

    # 3. Boosted skill/keyword overlap (up to 25 pts, ~3pts per keyword hit)
    boost_keywords = config["search"].get("boost_keywords", [])
    hits = [kw for kw in boost_keywords if _normalize(kw) in text]
    score += min(25, len(hits) * 3)
    matched.extend(hits)

    # 4. Recency (up to 10 pts) — newer postings get a small bump.
    #    (Left as a flat bonus here since date formats vary by source; sources
    #    that supply reliable posted_date can be extended to taper this.)
    if posting.posted_date:
        score += 10

    score = min(100, score)
    return ScoredPosting(posting=posting, score=score, matched_keywords=matched)


def rank_postings(
    postings: list[JobPosting], config: dict, seen_fingerprints: set[str]
) -> list[ScoredPosting]:
    """Score, filter out already-seen postings, and sort best-first."""
    fresh = [p for p in postings if p.fingerprint() not in seen_fingerprints]
    scored = [score_posting(p, config) for p in fresh]
    scored.sort(key=lambda s: s.score, reverse=True)
    return scored
