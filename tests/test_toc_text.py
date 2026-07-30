"""Tests for compact TOC text extraction."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline.page_mapping import PageMapping
from pipeline.toc import apply_page_mapping_to_toc_text, parse_document_title, validate_toc_text

SAMPLE = """# CREDIT AGREEMENT

ARTICLE I - Definitions | 1
  Section 1.01 - Defined Terms | 1
ARTICLE II - The Credits | 15
"""


class TocTextTests(unittest.TestCase):
    def test_validate_and_title(self) -> None:
        text = validate_toc_text(SAMPLE)
        self.assertEqual(parse_document_title(text), "CREDIT AGREEMENT")

    def test_rejects_json(self) -> None:
        with self.assertRaises(ValueError):
            validate_toc_text('{"table_of_contents": {}}')

    def test_apply_page_mapping(self) -> None:
        mapping = PageMapping(
            toc_page_kind="printed",
            printed_page_one_pdf_page=6,
            offset_pdf_minus_printed=5,
            method="llm_content_start",
            confidence="medium",
        )
        out = apply_page_mapping_to_toc_text(SAMPLE, mapping)
        self.assertIn("ARTICLE I - Definitions | 6", out)
        self.assertIn("Section 1.01 - Defined Terms | 6", out)
        self.assertIn("ARTICLE II - The Credits | 20", out)


if __name__ == "__main__":
    unittest.main()
