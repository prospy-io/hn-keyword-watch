"""Core logic: fetch Hacker News items and match them against phrases.

Two read-only sources are supported:

* Algolia HN Search API (https://hn.algolia.com/api) - fast full-text search.
* Official HN Firebase API (https://github.com/HackerNews/API) - newest items.
"""

from __future__ import annotations

import html
import json
import re
import time
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field
from typing import Callable, Iterable, Iterator

ALGOLIA_URL = "https://hn.algolia.com/api/v1/search_by_date"
FIREBASE_URL = "https://hacker-news.firebaseio.com/v0"
HN_ITEM_URL = "https://news.ycombinator.com/item?id={}"
USER_AGENT = "hn-keyword-watch/0.1 (+https://prospy.io)"

Fetcher = Callable[[str], object]

_TAG_RE = re.compile(r"<[^>]+>")


def http_get_json(url: str, timeout: float = 15.0) -> object:
    """GET a URL and decode the JSON body."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 - fixed https hosts
        return json.loads(resp.read().decode("utf-8"))


def clean_html(text: str | None) -> str:
    """HN text fields contain HTML; strip tags and unescape entities."""
    if not text:
        return ""
    text = text.replace("<p>", "\n\n")
    return html.unescape(_TAG_RE.sub("", text)).strip()


@dataclass
class Match:
    id: int
    type: str  # "story" or "comment"
    author: str
    created_at: int  # unix seconds
    title: str
    text: str
    url: str
    matched: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def _compile(phrases: Iterable[str]) -> list[tuple[str, re.Pattern[str]]]:
    out = []
    for p in phrases:
        p = p.strip()
        if not p:
            continue
        # Whole-word, case-insensitive; internal whitespace matches any whitespace.
        body = r"\s+".join(re.escape(w) for w in p.split())
        out.append((p, re.compile(rf"(?<!\w){body}(?!\w)", re.IGNORECASE)))
    return out


def match_text(text: str, phrases: Iterable[str]) -> list[str]:
    """Return the phrases that occur in ``text`` (case-insensitive, whole words)."""
    return [p for p, rx in _compile(phrases) if rx.search(text)]


def _from_algolia(hit: dict) -> Match:
    is_comment = "comment" in hit.get("_tags", []) or bool(hit.get("comment_text"))
    oid = int(hit["objectID"])
    return Match(
        id=oid,
        type="comment" if is_comment else "story",
        author=hit.get("author") or "",
        created_at=int(hit.get("created_at_i") or 0),
        title=hit.get("title") or hit.get("story_title") or "",
        text=clean_html(hit.get("comment_text") or hit.get("story_text")),
        url=HN_ITEM_URL.format(oid),
    )


def _from_firebase(item: dict, parent_title: str = "") -> Match:
    return Match(
        id=int(item["id"]),
        type=item.get("type", ""),
        author=item.get("by") or "",
        created_at=int(item.get("time") or 0),
        title=item.get("title") or parent_title,
        text=clean_html(item.get("text")),
        url=HN_ITEM_URL.format(item["id"]),
    )


def search_algolia(
    query: str,
    since: int | None = None,
    hits_per_page: int = 50,
    tags: str = "(story,comment)",
    fetch: Fetcher = http_get_json,
) -> list[Match]:
    """Full-text search on Algolia's HN index, newest first."""
    params = {"query": query, "tags": tags, "hitsPerPage": str(hits_per_page)}
    if since:
        params["numericFilters"] = f"created_at_i>{int(since)}"
    data = fetch(f"{ALGOLIA_URL}?{urllib.parse.urlencode(params)}")
    return [_from_algolia(h) for h in data.get("hits", [])]  # type: ignore[union-attr]


def scan_firebase(
    count: int = 200,
    fetch: Fetcher = http_get_json,
    delay: float = 0.0,
) -> Iterator[Match]:
    """Walk back ``count`` items from the newest HN item via the official API."""
    max_id = int(fetch(f"{FIREBASE_URL}/maxitem.json"))  # type: ignore[arg-type]
    for item_id in range(max_id, max(max_id - count, 0), -1):
        item = fetch(f"{FIREBASE_URL}/item/{item_id}.json")
        if delay:
            time.sleep(delay)
        if not isinstance(item, dict) or item.get("deleted") or item.get("dead"):
            continue
        if item.get("type") not in ("story", "comment"):
            continue
        yield _from_firebase(item)


def find_matches(items: Iterable[Match], phrases: list[str]) -> list[Match]:
    """Keep items whose title or text contains at least one phrase."""
    out = []
    for m in items:
        hits = match_text(f"{m.title}\n{m.text}", phrases)
        if hits:
            m.matched = hits
            out.append(m)
    return out
