# hn-keyword-watch

A small, dependency-free Python watcher that scans Hacker News for keywords and buying-intent phrases ("looking for a tool", "alternative to", "any recommendations"...) and prints the stories and comments that match.

It only reads public data from two official sources:

- **Algolia HN Search API** (`hn.algolia.com/api/v1/search_by_date`). Full-text search, newest first. This is the default.
- **Official HN Firebase API** (`hacker-news.firebaseio.com/v0`). Walks back through the newest items one by one.

## Install

```bash
pip install hn-keyword-watch
# or from a checkout:
pip install .
```

Python 3.9+ and no third-party dependencies. Package page: [pypi.org/project/hn-keyword-watch](https://pypi.org/project/hn-keyword-watch/).

## Usage

```bash
# Default buying-intent phrases, last 24 hours, via Algolia
hn-keyword-watch

# Your own phrases, last 48 hours
hn-keyword-watch "looking for a crm" "alternative to hubspot" --hours 48

# JSON lines on stdout (pipe into jq or another script) and save everything to a file
hn-keyword-watch "social listening" --json --out matches.json

# Scan the 300 newest items via the official Firebase API instead
hn-keyword-watch "is there a tool" --source firebase --scan 300

# Keep running and check every 10 minutes
hn-keyword-watch "alternative to notion" --watch 600

# Optional: send each match to your own Slack or Discord incoming webhook
hn-keyword-watch "need a crm" --watch 900 --webhook "$MY_WEBHOOK_URL"
```

Matching is case-insensitive and on whole words, so `crm` matches "need a CRM." but not "crmify". With Algolia each phrase is sent as a quoted query and then checked again locally.

Example output:

```
[story] 2026-10-23 14:03 UTC by someone | matched: alternative to
  Show HN: A European alternative to WhatsApp for work chats
  https://news.ycombinator.com/item?id=50209191
```

As a library:

```python
from hn_keyword_watch import search_algolia, find_matches

items = search_algolia('"looking for a tool"', hits_per_page=50)
for m in find_matches(items, ["looking for a tool"]):
    print(m.url, m.matched)
```

## Limits

- Algolia returns at most 1,000 hits per query, so narrow the window (`--hours`) for very common phrases.
- The Firebase source makes one request per item, so `--scan` is slow for big numbers. Use Algolia for wide searches.
- `--watch` keeps a seen-set in memory only. Restarting it can print a match again.
- Phrase matching is literal. It won't tell you whether a post is actually a buying signal. For that, see [intent-score](../intent-score).

## Be a good API citizen

- Both APIs are free and public with no key, so please keep the load low. The CLI pauses between phrases and won't poll more often than every 60 seconds.
- Read the [HN API docs](https://github.com/HackerNews/API) and [Algolia HN Search docs](https://hn.algolia.com/api) and follow any rate limits they publish.
- This tool only reads. Don't use it to spam people who post on HN. Reply by hand, and only when you can actually help.

If you'd rather not run this yourself, [Prospy](https://prospy.io) does social listening and AI lead generation across X/Twitter, Reddit, Bluesky and Hacker News, surfacing buying-intent posts.

## Source and issues

The canonical repo is on Codeberg: [codeberg.org/prospy/hn-keyword-watch](https://codeberg.org/prospy/hn-keyword-watch). It's mirrored to GitHub at [github.com/prospy-io/hn-keyword-watch](https://github.com/prospy-io/hn-keyword-watch). Issues and pull requests are welcome on either.

## Development

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

## License

MIT
