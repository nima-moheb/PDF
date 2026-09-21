from __future__ import annotations
import copy, json, tempfile, unittest
from pathlib import Path
from pypdf import PdfReader
from reportkit.engine import build, scrub
from reportkit.rtl import visual_runs

ROOT=Path(__file__).resolve().parents[1]
EXAMPLE=ROOT/'examples/client_report.json'

class EngineTests(unittest.TestCase):
    def test_public_safety_rejects_internal_language(self):
        with self.assertRaises(ValueError): scrub({'x':'TODO: tell Nima later'})

    def test_rtl_preserves_latin_tokens(self):
        runs=visual_runs('رشد Google Search Console برابر 42.6% در Laravel 13.19 است')
        joined=''.join(x[1] for x in runs)
        self.assertIn('Google Search Console',joined)
        self.assertIn('42.6%',joined)
        self.assertIn('Laravel 13.19',joined)

    def test_missing_evidence_is_hard_failure(self):
        cfg=json.loads(EXAMPLE.read_text())
        cfg['pages']=[cfg['pages'][0], {'id':'bad-image','type':'image_text','title':'Evidence','text':'Required'}]
        with tempfile.TemporaryDirectory() as td:
            inp=Path(td)/'x.json'; out=Path(td)/'r.pdf'; inp.write_text(json.dumps(cfg))
            with self.assertRaisesRegex(ValueError,'ASSET_FAIL'): build(inp,out)

    def test_resume_annotation_exists(self):
        with tempfile.TemporaryDirectory() as td:
            out=Path(td)/'r.pdf'; build(EXAMPLE,out)
            rd=PdfReader(out)
            urls=[]
            for page in rd.pages:
                for a in page.get('/Annots',[]) or []:
                    obj=a.get_object(); action=obj.get('/A')
                    if action and action.get('/URI'): urls.append(action.get('/URI'))
            self.assertIn('https://nima-moheb.github.io/myCV/',urls)

    def test_page_surgery_keeps_other_artifacts_byte_identical(self):
        with tempfile.TemporaryDirectory() as td:
            td=Path(td); cfg=json.loads(EXAMPLE.read_text()); inp=td/'r.json'; inp.write_text(json.dumps(cfg))
            out=td/'report.pdf'; before=build(inp,out)
            cfg2=copy.deepcopy(cfg)
            for p in cfg2['pages']:
                if p['id']=='trend': p['analysis']=p['analysis']+' Surgical edit.'
            inp.write_text(json.dumps(cfg2)); after=build(inp,out,only_ids={'trend'})
            for pid in before:
                if pid=='trend': self.assertNotEqual(before[pid]['sha256'],after[pid]['sha256'])
                else: self.assertEqual(before[pid]['sha256'],after[pid]['sha256'],pid)

if __name__=='__main__': unittest.main()
