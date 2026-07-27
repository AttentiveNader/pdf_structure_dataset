"""Tests for LaTeX structure parsing."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline.latex_parse import LatexParseError, extract_flat_nodes, parse_latex_structure


SAMPLE = r"""
\input{latex_schema.tex}
\begin{document}
\creditdocumenttitle{CREDIT AGREEMENT}
\creditarticle{ARTICLE I}
\creditsection{Section 1.01}
\creditsubsection{1.01(a)}
\creditarticle{ARTICLE II}
\creditschedule{Commitment Schedule}
\end{document}
"""


class LatexParseTests(unittest.TestCase):
    def test_flat_nodes(self) -> None:
        title, flat = extract_flat_nodes(SAMPLE)
        self.assertEqual(title, "CREDIT AGREEMENT")
        self.assertEqual(len(flat), 5)
        self.assertEqual(flat[0]["level"], 1)

    def test_tree(self) -> None:
        tree = parse_latex_structure(SAMPLE)
        self.assertEqual(tree["title"], "CREDIT AGREEMENT")
        self.assertEqual(len(tree["children"]), 3)
        self.assertEqual(tree["children"][0]["title"], "ARTICLE I")
        self.assertEqual(len(tree["children"][0]["children"]), 1)

    def test_unbalanced_raises(self) -> None:
        bad = r"\creditarticle{ARTICLE I"
        with self.assertRaises(LatexParseError):
            parse_latex_structure(bad)


if __name__ == "__main__":
    unittest.main()
