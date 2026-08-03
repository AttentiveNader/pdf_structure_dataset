"""Tests for TOC file-backed document store."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline.document_store import CreditDocumentStore

SAMPLE_TOC = """# CREDIT AGREEMENT

ARTICLE I - Definitions | 6
  Section 1.01 - Defined Terms | 6
"""

SAMPLE_PDF = ROOT / "test_astro.pdf"


class DocumentStoreTests(unittest.TestCase):
    def test_from_toc_file(self) -> None:
        if not SAMPLE_PDF.is_file():
            self.skipTest("sample PDF not available")

        with tempfile.TemporaryDirectory() as tmp:
            toc_path = Path(tmp) / "doc.toc.txt"
            toc_path.write_text(SAMPLE_TOC + "\n", encoding="utf-8")

            store = CreditDocumentStore.from_toc_file(SAMPLE_PDF, toc_path)
            self.assertEqual(store.document_title, "CREDIT AGREEMENT")
            self.assertIn("ARTICLE I - Definitions | 6", store.toc_text)
            self.assertEqual(store.toc_page_numbers_are, "pdf")
            self.assertGreater(store.page_count, 0)
            info = store.as_doc_info()
            self.assertEqual(info["document_title"], "CREDIT AGREEMENT")
            self.assertEqual(info["toc_page_numbers_are"], "pdf")


if __name__ == "__main__":
    unittest.main()
