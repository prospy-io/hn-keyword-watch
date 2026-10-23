"""Command line entry point for hn-keyword-watch."""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request
from datetime import datetime, timezone

from . import __version__
from .core import USER_AGENT, Match, find_matches, scan_firebase, search_algolia

DEFAULT_PHRASES = [
    "looking for a tool",
    "any recommendations",
    "alternative to",
    "recommend a",
    "willing to pay",
    "is there a tool",
]


def format_text(m: Match) -> str:
    when = datetime.fromtimestamp(m.created_at, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    snippet = " ".join(m.text.split())
    if len(snippet) > 200:
        snippet = snippet[:197] + "..."
    lines = [f"[{m.type}] {when} by {m.author} | matched: {', '.join(m.matched)}"]
    lines += [f"  {x}" for x in (m.title, snippet) if x]
    lines.append(f"  {m.url}")
    return "\n".join(lines)


def post_webhook(url: str, m: Match) -> None:
    """Send one match to *your own* Slack or Discord incoming webhook."""
    msg = f"HN match ({', '.join(m.matched)}): {m.title or m.text[:80]} {m.url}"
    body = json.dumps({"text": msg, "content": msg}).encode()  # Slack uses text, Discord uses content
    req = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json", "User-Agent": USER_AGENT}
    )
    urllib.request.urlopen(req, timeout=15).close()  # noqa: S310 - user-supplied webhook


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="hn-keyword-watch",
        description="Watch Hacker News for keywords and buying-intent phrases (read-only).",
    )
    p.add_argument("phrases", nargs="*", help="phrases to match (default: a small buying-intent list)")
    p.add_argument("--source", choices=["algolia", "firebase"], default="algolia")
    p.add_argument("--hours", type=float, default=24, help="algolia: look back this many hours (default 24)")
    p.add_argument("--limit", type=int, default=50, help="algolia: hits per phrase (max 1000)")
    p.add_argument("--scan", type=int, default=200, help="firebase: number of newest items to scan")
    p.add_argument("--json", action="store_true", help="print JSON lines instead of text")
    p.add_argument("--out", help="also write all matches to this JSON file")
    p.add_argument("--webhook", help="optional: your own Slack/Discord incoming webhook URL")
    p.add_argument("--watch", type=int, metavar="SECONDS", help="repeat every N seconds (min 60)")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return p


def run_once(args: argparse.Namespace, phrases: list[str], seen: set[int], since: int | None) -> list[Match]:
    if args.source == "algolia":
        items: dict[int, Match] = {}
        for phrase in phrases:
            # Quote the phrase so Algolia matches it as a phrase, then confirm locally.
            for m in search_algolia(f'"{phrase}"', since=since, hits_per_page=args.limit):
                items.setdefault(m.id, m)
            time.sleep(0.2)  # be polite
        candidates = list(items.values())
    else:
        candidates = list(scan_firebase(count=args.scan))
    matches = [m for m in find_matches(candidates, phrases) if m.id not in seen]
    matches.sort(key=lambda m: m.created_at, reverse=True)
    seen.update(m.id for m in matches)
    return matches


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    phrases = args.phrases or DEFAULT_PHRASES
    if args.watch is not None and args.watch < 60:
        print("--watch must be at least 60 seconds", file=sys.stderr)
        return 2
    seen: set[int] = set()
    collected: list[dict] = []
    since: int | None = int(time.time() - args.hours * 3600)
    while True:
        started = int(time.time())
        matches = run_once(args, phrases, seen, since)
        for m in matches:
            print(json.dumps(m.to_dict()) if args.json else format_text(m) + "\n", flush=True)
            if args.webhook:
                try:
                    post_webhook(args.webhook, m)
                except Exception as exc:  # keep watching even if the webhook fails
                    print(f"webhook error: {exc}", file=sys.stderr)
        collected.extend(m.to_dict() for m in matches)
        if args.out:
            with open(args.out, "w", encoding="utf-8") as fh:
                json.dump(collected, fh, indent=2)
        if not args.json:
            print(f"-- {len(matches)} new match(es) from {args.source}", file=sys.stderr)
        if args.watch is None:
            return 0
        since = started - 60  # small overlap; seen-set removes duplicates
        time.sleep(args.watch)


if __name__ == "__main__":
    raise SystemExit(main())
