import csv
import tempfile
import unittest
from pathlib import Path

from src.sourcing.tweetclaw_import import load_tweetclaw_export


class TweetClawImportTest(unittest.TestCase):
    def test_loads_tweetclaw_rows_as_feed_entries(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "tweetclaw.csv"
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "id",
                        "text",
                        "createdAt",
                        "authorUsername",
                        "likeCount",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "id": "123",
                        "text": "Open-source agents need reviewable evidence.",
                        "createdAt": "2026-06-30T00:00:00Z",
                        "authorUsername": "xquik",
                        "likeCount": "42",
                    }
                )

            entries = load_tweetclaw_export(path)

        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].source_feed_name, "TweetClaw export")
        self.assertEqual(entries[0].author, "xquik")
        self.assertEqual(entries[0].link, "https://x.com/xquik/status/123")
        self.assertIn("reviewable evidence", entries[0].summary)
        self.assertIn("likeCount=42", entries[0].summary)

    def test_skips_empty_rows(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "tweetclaw.csv"
            path.write_text("id,text,url\n,,\n", encoding="utf-8")

            entries = load_tweetclaw_export(path)

        self.assertEqual(entries, [])


if __name__ == "__main__":
    unittest.main()
