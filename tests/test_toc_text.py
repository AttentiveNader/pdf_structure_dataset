"""Tests for compact TOC text extraction."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline.toc import parse_document_title, validate_toc_text

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


if __name__ == "__main__":
    unittest.main()
