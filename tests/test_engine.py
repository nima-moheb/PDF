from __future__ import annotations

import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from jsonschema import ValidationError, validate
from pypdf import PdfReader
from PIL import Image

from reportkit.engine import SCHEMA, _cover_meta_cells, build, scrub
from reportkit.rtl import visual_runs, visual_rtl

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples/client_report.json"


def file_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class EngineTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
