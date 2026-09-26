from __future__ import annotations

import copy
import hashlib
import json
import tempfile
import fitz
import unittest
from pathlib import Path

from jsonschema import ValidationError, validate
from pypdf import PdfReader
from PIL import Image

from reportkit import build
from reportkit.engine import SCHEMA, _cover_meta_cells, scrub
from reportkit.delivery import verify_delivery
from reportkit.visual_v05 import clean_text, _ensure_bundled_vazirmatn, _font_has_required_persian
from reportkit.rtl import visual_runs, visual_rtl

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples/client_report.json"


def file_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class EngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import os
        os.environ["REPORTKIT_ALLOW_PERSIAN_FALLBACK"] = "1"
        os.environ["REPORTKIT_INTERNAL_TEST"] = "1"

    def test_public_safety_rejects_internal_language(self):
        with self.assertRaises(ValueError):
            scrub({"x": "TODO: tell Nima later"})

    def test_schema_rejects_layout_and_style_overrides(self):
        cfg = json.loads(EXAMPLE.read_text())
        table = next(p for p in cfg["pages"] if p["id"] == "table")
        table["widths"] = [1, 1, 1, 1]
        with self.assertRaises(ValidationError):
            validate(cfg, SCHEMA)
        cfg = json.loads(EXAMPLE.read_text())
        cfg["pages"][1]["footer"] = "custom"
        with self.assertRaises(ValidationError):
            validate(cfg, SCHEMA)

    def test_rtl_preserves_latin_tokens_using_bidi_order(self):
        text = "رشد Google Search Console برابر 42.6% در Laravel 13.19 است"
        visual = visual_rtl(text)
        joined = "".join(x[1] for x in visual_runs(text))
        self.assertEqual(visual, joined)
        self.assertIn("Google Search Console", joined)
        self.assertIn("42.6%", joined)
        self.assertIn("Laravel 13.19", joined)

    def test_missing_evidence_is_hard_failure(self):
        cfg = json.loads(EXAMPLE.read_text())
        cfg["pages"] = [
            cfg["pages"][0],
            {"id": "bad-image", "type": "image_text", "title": "Evidence", "image": "missing.png", "text": "Required"},
        ]
        with tempfile.TemporaryDirectory() as td:
            inp = Path(td) / "x.json"
            out = Path(td) / "r.pdf"
            inp.write_text(json.dumps(cfg))
            with self.assertRaisesRegex(ValueError, "ASSET_FAIL"):
                build(inp, out, run_qa=False)

    def test_relative_evidence_path_resolves_from_report_json(self):
        # Real image fixture: the evidence path itself is what this test exercises.
        cfg = json.loads(EXAMPLE.read_text())
        cfg["pages"] = [
            cfg["pages"][0],
            {"id": "evidence", "type": "image_text", "title": "Evidence", "image": "assets/evidence.png", "text": "Real evidence image."},
        ]
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            (td / "assets").mkdir()
            Image.new("RGB", (24, 24), "white").save(td / "assets/evidence.png")
            inp = td / "report.json"
            inp.write_text(json.dumps(cfg))
            build(inp, td / "out/report.pdf")
            self.assertTrue((td / "out/qa/page-002.png").exists())

    def test_closing_exposes_real_resume_url_without_view_resume_label(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "r.pdf"
            build(EXAMPLE, out)
            rd = PdfReader(out)
            urls = []
            for page in rd.pages:
                for a in page.get("/Annots", []) or []:
                    obj = a.get_object()
                    action = obj.get("/A")
                    if action and action.get("/URI"):
                        urls.append(action.get("/URI"))
            self.assertIn("https://nima-moheb.github.io/myCV/", urls)
            visible = "\n".join((page.extract_text() or "") for page in rd.pages)
            self.assertNotIn("VIEW RESUME", visible.upper())

    def test_clean_builds_are_byte_identical(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            a = td / "a/report.pdf"
            b = td / "b/report.pdf"
            build(EXAMPLE, a)
            build(EXAMPLE, b)
            self.assertEqual(file_sha(a), file_sha(b))
            for pa, pb in zip(sorted((a.parent / "pages").glob("*.pdf")), sorted((b.parent / "pages").glob("*.pdf"))):
                self.assertEqual(file_sha(pa), file_sha(pb), pa.name)

    def test_page_surgery_keeps_unaffected_artifacts_byte_identical(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            cfg = json.loads(EXAMPLE.read_text())
            inp = td / "r.json"
            inp.write_text(json.dumps(cfg))
            out = td / "report.pdf"
            before = build(inp, out)
            cfg2 = copy.deepcopy(cfg)
            for p in cfg2["pages"]:
                if p["id"] == "trend":
                    p["analysis"] += " Surgical edit."
            inp.write_text(json.dumps(cfg2))
            after = build(inp, out, only_ids={"trend"})
            for pid in before:
                if pid == "trend":
                    self.assertNotEqual(before[pid]["sha256"], after[pid]["sha256"])
                else:
                    self.assertEqual(before[pid]["sha256"], after[pid]["sha256"], pid)
            manifest = json.loads((td / "manifest.json").read_text())
            self.assertEqual(manifest["build"]["mode"], "surgical")

    def test_surgery_auto_expands_for_unrequested_changed_page(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            cfg = json.loads(EXAMPLE.read_text())
            inp = td / "r.json"
            inp.write_text(json.dumps(cfg))
            out = td / "report.pdf"
            before = build(inp, out)
            cfg["pages"][1]["intro"] += " Changed outside requested page."
            inp.write_text(json.dumps(cfg))
            after = build(inp, out, only_ids={"trend"})
            self.assertNotEqual(before["summary"]["sha256"], after["summary"]["sha256"])
            self.assertEqual(before["narrative"]["sha256"], after["narrative"]["sha256"])
            manifest = json.loads((td / "manifest.json").read_text())
            self.assertEqual(manifest["build"]["mode"], "surgical-expanded")

    def test_global_change_invalidates_surgery_and_rebuilds_all(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            cfg = json.loads(EXAMPLE.read_text())
            inp = td / "r.json"
            inp.write_text(json.dumps(cfg))
            out = td / "report.pdf"
            before = build(inp, out)
            cfg["meta"]["theme"] = "purple"
            inp.write_text(json.dumps(cfg))
            after = build(inp, out, only_ids={"trend"})
            self.assertNotEqual(before["cover"]["sha256"], after["cover"]["sha256"])
            self.assertNotEqual(before["summary"]["sha256"], after["summary"]["sha256"])
            manifest = json.loads((td / "manifest.json").read_text())
            self.assertEqual(manifest["build"]["mode"], "surgical-invalidated-full")

    def test_table_never_silently_truncates(self):
        cfg = json.loads(EXAMPLE.read_text())
        table = next(p for p in cfg["pages"] if p["id"] == "table")
        table["rows"][0][0] = "X" * 500
        cfg["pages"] = [cfg["pages"][0], table]
        with tempfile.TemporaryDirectory() as td:
            inp = Path(td) / "x.json"
            out = Path(td) / "r.pdf"
            inp.write_text(json.dumps(cfg))
            with self.assertRaisesRegex(ValueError, "FIT_FAIL"):
                build(inp, out, run_qa=False)

    def test_rendered_qa_is_created(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "r.pdf"
            build(EXAMPLE, out)
            qa = json.loads((Path(td) / "qa/qa_manifest.json").read_text())
            self.assertEqual(len(qa["pages"]), 10)
            self.assertEqual(qa["pdf_sha256"], file_sha(out))
            self.assertTrue(all(p["ink_fraction"] > 0.006 for p in qa["pages"]))

    def test_persian_cover_localizes_nima_author_identity(self):
        meta = {"author": "Nima Moheb", "recipient": "کارفرما", "date": "شهریور ۱۴۰۵"}
        self.assertEqual(_cover_meta_cells(meta, True)[2][1], "نیما محب")
        self.assertEqual(_cover_meta_cells(meta, False)[0][1], "Nima Moheb")
        fa = json.loads((ROOT / "examples/cover_showcase_fa.json").read_text())
        self.assertEqual(fa["meta"]["author"], "نیما محب")

    def test_cover_showcases_render_all_five_variants_in_ltr_and_rtl(self):
        for name in ("cover_showcase_en.json", "cover_showcase_fa.json"):
            src = ROOT / "examples" / name
            with tempfile.TemporaryDirectory() as td:
                out = Path(td) / "covers.pdf"
                build(src, out)
                rd = PdfReader(out)
                self.assertEqual(len(rd.pages), 5)
                self.assertTrue((Path(td) / "qa/page-005.png").exists())

    def test_persian_cover_auto_mirrors_and_builds(self):
        src = ROOT / "examples/persian_cover.json"
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "fa.pdf"
            build(src, out)
            rd = PdfReader(out)
            self.assertEqual(len(rd.pages), 2)
            self.assertAlmostEqual(float(rd.pages[0].mediabox.width), 595.2756, places=1)
            self.assertAlmostEqual(float(rd.pages[0].mediabox.height), 841.8898, places=1)


    def test_v05_rejects_repetitive_cards_report(self):
        cfg = json.loads((ROOT / "examples" / "real_case_regression_fa.json").read_text())
        card = cfg["pages"][3]
        cfg["pages"] = [
            cfg["pages"][0],
            *[
                dict(card, id=f"role-{i}", title=f"نقش {i}")
                for i in range(1, 7)
            ],
        ]
        with tempfile.TemporaryDirectory() as td:
            inp = Path(td) / "x.json"
            out = Path(td) / "r.pdf"
            inp.write_text(json.dumps(cfg, ensure_ascii=False))
            with self.assertRaisesRegex(RuntimeError, "QA_VARIETY_FAIL"):
                build(inp, out)

    def test_v05_strips_pasted_invisible_controls_but_keeps_zwnj(self):
        self.assertEqual(clean_text("خ\ufeffلاصه نقش\u200fها"), "خلاصه نقشها")
        self.assertEqual(clean_text("نقش\u200cها"), "نقش\u200cها")

    def test_v05_real_case_regressions_render(self):
        for name, pages in (
            ("real_case_regression_en.json", 4),
            ("real_case_regression_fa.json", 6),
        ):
            src = ROOT / "examples" / name
            with tempfile.TemporaryDirectory() as td:
                out = Path(td) / "case.pdf"
                build(src, out)
                self.assertEqual(len(PdfReader(out).pages), pages)
                self.assertTrue((Path(td) / "qa" / f"page-{pages:03d}.png").exists())

    def test_v05_density_guard_rejects_short_single_group_page(self):
        cfg = json.loads((ROOT / "examples" / "real_case_regression_en.json").read_text())
        cfg["pages"] = [
            cfg["pages"][0],
            {
                "id": "too-empty",
                "type": "text",
                "title": "Too empty",
                "eyebrow": "TEST",
                "blocks": [
                    {"kind": "heading", "text": "One point"},
                    {"kind": "text", "text": "Short."},
                ],
            },
        ]
        with tempfile.TemporaryDirectory() as td:
            inp = Path(td) / "x.json"
            out = Path(td) / "r.pdf"
            inp.write_text(json.dumps(cfg))
            with self.assertRaisesRegex(RuntimeError, "QA_DENSITY_FAIL"):
                build(inp, out)


    def test_v06_persian_output_never_draws_zwnj_controls(self):
        src = ROOT / "examples" / "real_case_regression_fa.json"
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "fa.pdf"
            build(src, out)
            doc = fitz.open(out)
            extracted = "\n".join(page.get_text() for page in doc)
            self.assertNotIn("\u200c", extracted)
            self.assertNotIn("\u200d", extracted)

    def test_v06_persian_cover_has_no_english_decorative_chrome(self):
        src = ROOT / "examples" / "cover_showcase_fa.json"
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "covers.pdf"
            build(src, out)
            extracted = "\n".join(page.get_text() for page in fitz.open(out)).upper()
            for token in (
                "NIMA REPORT ENGINE",
                "STRUCTURED / FINAL",
                "DATA / INSIGHT / IMPACT",
                "REPORT COMPLETE",
            ):
                self.assertNotIn(token, extracted)

    def test_v06_summary_metrics_are_visually_dominant(self):
        src = ROOT / "examples" / "real_case_regression_fa.json"
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "fa.pdf"
            build(src, out)
            page = fitz.open(out)[1]
            found = []
            for block in page.get_text("dict")["blocks"]:
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        if span.get("text", "").strip() in {"۷", "۳", "۵", "۲"}:
                            found.append(float(span["size"]))
            self.assertEqual(len(found), 4)
            self.assertTrue(all(size >= 36 for size in found), found)

    def test_v06_persian_page_chrome_is_localized(self):
        src = ROOT / "examples" / "real_case_regression_fa.json"
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "fa.pdf"
            build(src, out)
            extracted = "\n".join(page.get_text() for page in fitz.open(out)[1:]).upper()
            self.assertNotIn("PAGE", extracted)


    def test_v061_delivery_gate_rejects_non_engine_pdf(self):
        from reportlab.pdfgen import canvas
        with tempfile.TemporaryDirectory() as td:
            bad = Path(td) / "adhoc.pdf"
            c = canvas.Canvas(str(bad))
            c.drawString(72, 720, "Ad hoc PDF")
            c.showPage()
            c.save()
            with self.assertRaisesRegex(RuntimeError, "missing Nima Report Engine"):
                verify_delivery(bad)

    def test_v061_delivery_gate_rejects_persian_fallback_as_production(self):
        src = ROOT / "examples" / "real_case_regression_fa.json"
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "fa.pdf"
            build(src, out)
            with self.assertRaisesRegex(RuntimeError, "does not embed Vazirmatn"):
                verify_delivery(out, src)

    def test_v061_delivery_gate_accepts_repo_output_in_internal_test_mode(self):
        src = ROOT / "examples" / "real_case_regression_fa.json"
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "fa.pdf"
            build(src, out)
            result = verify_delivery(
                out,
                src,
                expected_engine_version="0.6.1",
                allow_test_font_fallback=True,
            )
            self.assertEqual(result["status"], "PASS")


    def test_v062_bundled_vazirmatn_materializes_offline_with_required_glyphs(self):
        import os
        previous = os.environ.get("REPORTKIT_FONT_DIR")
        with tempfile.TemporaryDirectory() as td:
            os.environ["REPORTKIT_FONT_DIR"] = td
            try:
                paths = _ensure_bundled_vazirmatn()
                self.assertEqual(set(paths), {400, 500, 700})
                for path in paths.values():
                    self.assertTrue(path.exists(), path)
                    self.assertTrue(_font_has_required_persian(path), path)
            finally:
                if previous is None:
                    os.environ.pop("REPORTKIT_FONT_DIR", None)
                else:
                    os.environ["REPORTKIT_FONT_DIR"] = previous


if __name__ == "__main__":
    unittest.main()
