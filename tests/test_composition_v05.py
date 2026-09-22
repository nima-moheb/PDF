from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import fitz
from jsonschema import ValidationError, validate
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from reportkit.engine import SCHEMA, build, clean_text, register_fonts, wrap
from reportkit.qa import preflight_and_render

ROOT = Path(__file__).resolve().parents[1]


class CompositionV05Tests(unittest.TestCase):
    def test_persian_cleanup_removes_artifact_controls_but_keeps_zwnj(self):
        dirty = "خ\ufeffلاصه نقش\u200cها و كاربرد يک\u200f گزارش"
        cleaned = clean_text(dirty)
        self.assertEqual(cleaned, "خلاصه نقش\u200cها و کاربرد یک گزارش")
        self.assertNotIn("\ufeff", cleaned)
        self.assertNotIn("\u200f", cleaned)
        self.assertIn("\u200c", cleaned)

    def test_summary_cards_cannot_use_empty_fake_values(self):
        cfg = json.loads((ROOT / "examples/regression_crm_fa.json").read_text(encoding="utf-8"))
        summary = next(p for p in cfg["pages"] if p["type"] == "summary")
        summary["cards"][0]["value"] = ""
        with self.assertRaises(ValidationError):
            validate(cfg, SCHEMA)

    def test_font_registration_refuses_unapproved_fallbacks(self):
        with patch("reportkit.engine._font_dirs", return_value=[Path("/definitely/missing")]), \
             patch("reportkit.engine._convert_plex_runtime", return_value=(None, None)):
            with self.assertRaisesRegex(RuntimeError, "FONT_SETUP_FAIL: exact approved fonts are required"):
                register_fonts()

    def test_persian_cover_subtitle_orphan_control(self):
        register_fonts()
        subtitle = "هر نقش چه می‌بیند، چه کاری می‌تواند انجام دهد و چطور با بقیه نقش‌ها ارتباط دارد"
        lines = wrap(subtitle, "Fa", 11.45, 115 * 72 / 25.4, True)
        self.assertGreaterEqual(len(lines[-1].replace("\u00a0", " ").split()), 2)

    def test_real_crm_regressions_pass_density_qa(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            for name in ("regression_crm_en.json", "regression_crm_fa.json"):
                out = td / name.replace(".json", ".pdf")
                build(ROOT / "examples" / name, out)
                qa = json.loads((td / "qa/qa_manifest.json").read_text(encoding="utf-8"))
                for page in qa["pages"]:
                    if page["type"] in {"summary", "text", "cards", "comparison", "table", "timeline"}:
                        self.assertGreater(page["body_reach"], 0.60, (name, page))

    def test_rtl_table_puts_logical_first_column_on_the_right(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "fa.pdf"
            build(ROOT / "examples/regression_crm_fa.json", out)
            page = fitz.open(out)[4]
            words = page.get_text("words")
            # Presentation forms make exact Persian extraction renderer-dependent.
            # Use the English tokens that exist in separate logical columns instead:
            # Technical belongs in the leftmost condition column, while the role
            # cell is Persian on the far right. Verify the Latin Technical token is
            # not incorrectly placed on the right half of the table.
            tech = [w for w in words if "Technical" in w[4]]
            self.assertTrue(tech)
            self.assertLess(max(w[0] for w in tech), page.rect.width * 0.5)

    def test_sparse_page_gate_rejects_decoratively_empty_page(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            pdf = td / "sparse.pdf"
            c = canvas.Canvas(str(pdf), pagesize=A4)
            # Plenty of decorative ink: this must not be mistaken for content density.
            c.setStrokeGray(0.90)
            for x in range(20, 580, 18):
                c.line(x, 20, x, 820)
            for y in range(20, 820, 18):
                c.line(20, y, 575, y)
            c.setFillGray(0.15)
            c.drawString(70, 690, "One tiny content block")
            c.showPage(); c.save()
            with self.assertRaisesRegex(RuntimeError, "SPARSE_PAGE_FAIL"):
                preflight_and_render(pdf, td / "qa", expected_pages=1, page_types=["cards"])


if __name__ == "__main__":
    unittest.main()
