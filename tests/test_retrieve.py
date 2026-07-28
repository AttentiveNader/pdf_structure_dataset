"""Tests for PageIndex-style page parsing and retrieval."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline.retrieve import parse_pages, remove_fields


class RetrieveTests(unittest.TestCase):
    def test_parse_pages(self) -> None:
        self.assertEqual(parse_pages("12"), [12])
        self.assertEqual(parse_pages("5-7"), [5, 6, 7])
        self.assertEqual(parse_pages("3,8"), [3, 8])
        self.assertEqual(parse_pages("5-7, 10"), [5, 6, 7, 10])

    def test_remove_fields(self) -> None:
        tree = {
            "title": "A",
            "page": 1,
            "text": "secret",
            "children": [{"title": "B", "text": "x", "children": []}],
        }
        slim = remove_fields(tree, fields=["text"])
        self.assertNotIn("text", slim)
        self.assertNotIn("text", slim["children"][0])


if __name__ == "__main__":
    unittest.main()
