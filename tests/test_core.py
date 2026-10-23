import json
import unittest

from hn_keyword_watch import cli
from hn_keyword_watch.core import clean_html, find_matches, match_text, scan_firebase, search_algolia


ALGOLIA_FIXTURE = {
    "hits": [
        {
            "objectID": "101",
            "_tags": ["comment", "author_alice"],
            "author": "alice",
            "created_at_i": 1700000000,
            "comment_text": "We are <i>looking for a tool</i> to track mentions &amp; leads.",
            "story_title": "Ask HN: Social listening?",
        },
        {
            "objectID": "102",
            "_tags": ["story"],
            "author": "bob",
            "created_at_i": 1700000100,
            "title": "Show HN: My weekend project",
            "story_text": None,
        },
    ]
}


class MatchTextTests(unittest.TestCase):
    def test_case_insensitive_phrase(self):
        self.assertEqual(match_text("Any RECOMMENDATIONS here?", ["any recommendations"]), ["any recommendations"])

    def test_whole_words_only(self):
        self.assertEqual(match_text("crmify is great", ["crm"]), [])
        self.assertEqual(match_text("need a crm.", ["crm"]), ["crm"])

    def test_whitespace_flexible(self):
        self.assertEqual(match_text("alternative\n to Foo", ["alternative to"]), ["alternative to"])

    def test_clean_html(self):
        self.assertEqual(clean_html("a <b>b</b> &amp; c"), "a b & c")
        self.assertEqual(clean_html(None), "")


class AlgoliaTests(unittest.TestCase):
    def test_search_builds_url_and_parses(self):
        seen = {}

        def fake(url):
            seen["url"] = url
            return ALGOLIA_FIXTURE

        items = search_algolia('"looking for a tool"', since=1699999999, fetch=fake)
        self.assertIn("numericFilters=created_at_i%3E1699999999", seen["url"])
        self.assertEqual([i.id for i in items], [101, 102])
        self.assertEqual(items[0].type, "comment")
        self.assertEqual(items[0].title, "Ask HN: Social listening?")
        self.assertIn("track mentions & leads", items[0].text)
        matches = find_matches(items, ["looking for a tool"])
        self.assertEqual([m.id for m in matches], [101])
        self.assertEqual(matches[0].url, "https://news.ycombinator.com/item?id=101")


class FirebaseTests(unittest.TestCase):
    def test_scan_skips_dead_and_non_posts(self):
        db = {
            "maxitem.json": 5,
            "item/5.json": {"id": 5, "type": "comment", "by": "c", "time": 1, "text": "Is there a tool for this?"},
            "item/4.json": {"id": 4, "type": "comment", "dead": True, "text": "is there a tool"},
            "item/3.json": {"id": 3, "type": "poll", "title": "is there a tool"},
            "item/2.json": None,
            "item/1.json": {"id": 1, "type": "story", "by": "s", "time": 2, "title": "Hello"},
        }

        def fake(url):
            return db[url.split("/v0/")[1]]

        items = list(scan_firebase(count=5, fetch=fake))
        self.assertEqual([i.id for i in items], [5, 1])
        self.assertEqual([m.id for m in find_matches(items, ["is there a tool"])], [5])


class CliTests(unittest.TestCase):
    def test_json_output_and_dedupe(self):
        calls = []

        def fake_search(query, since=None, hits_per_page=50):
            calls.append(query)
            from hn_keyword_watch.core import _from_algolia

            return [_from_algolia(h) for h in ALGOLIA_FIXTURE["hits"]]

        orig = cli.search_algolia
        cli.search_algolia = fake_search
        try:
            args = cli.build_parser().parse_args(["looking for a tool", "track mentions", "--json"])
            seen = set()
            first = cli.run_once(args, args.phrases, seen, None)
            second = cli.run_once(args, args.phrases, seen, None)
        finally:
            cli.search_algolia = orig
        self.assertEqual(calls[:2], ['"looking for a tool"', '"track mentions"'])
        self.assertEqual(len(first), 1)
        self.assertEqual(first[0].matched, ["looking for a tool", "track mentions"])
        self.assertEqual(second, [])
        json.dumps(first[0].to_dict())

    def test_watch_minimum(self):
        self.assertEqual(cli.main(["--watch", "5"]), 2)


if __name__ == "__main__":
    unittest.main()
