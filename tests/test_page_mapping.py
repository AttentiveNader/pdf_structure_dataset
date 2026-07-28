"""Tests for last-word page mapping."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline.page_mapping import (
    PageMapping,
    convert_page_spec_printed_to_pdf,
    last_word_page_label,
    parse_page_label_token,
    roman_to_int,
)


class PageMappingTests(unittest.TestCase):
    def test_roman(self) -> None:
        self.assertEqual(roman_to_int("iv"), 4)
        self.assertEqual(roman_to_int("xii"), 12)

    def test_parse_labels(self) -> None:
        self.assertEqual(parse_page_label_token("1"), ("arabic", 1))
        self.assertEqual(parse_page_label_token("ii"), ("roman", 2))

    def test_last_word(self) -> None:
        self.assertEqual(last_word_page_label("Body text continues here. 12"), ("arabic", 12))
        self.assertEqual(last_word_page_label("Cover page\n\niii"), ("roman", 3))
        self.assertIsNone(last_word_page_label("No page number on this sheet"))

    def test_convert_spec(self) -> None:
        m = PageMapping(
            toc_page_kind="printed",
            printed_page_one_pdf_page=6,
            offset_pdf_minus_printed=5,
            method="last_word",
            confidence="high",
        )
        self.assertEqual(convert_page_spec_printed_to_pdf("1-3", m), "6-8")


if __name__ == "__main__":
    unittest.main()
