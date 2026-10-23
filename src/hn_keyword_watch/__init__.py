"""Watch Hacker News for keywords and buying-intent phrases."""

from .core import Match, find_matches, match_text, search_algolia, scan_firebase

__all__ = ["Match", "find_matches", "match_text", "search_algolia", "scan_firebase"]
__version__ = "0.1.0"
