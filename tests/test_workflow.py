from __future__ import annotations
import copy
import io
import json
import os
import shutil
import tempfile
import unittest
from decimal import Decimal
from contextlib import redirect_stderr
from pathlib import Path
from unittest.mock import patch
import fitz
from PIL import Image
from fontTools.ttLib import TTFont
from reportkit import build
from reportkit import engine as e
from reportkit.cli import edit_page, _accepted, main
from reportkit.contract import load_config, validate_config
from reportkit.delivery import verify_delivery
from reportkit.fonts import FONT_DIR
from reportkit.pipeline import bundle_path, output_lock
from reportkit.pricing import calculate

ROOT=Path(__file__).resolve().parents[1]


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.cfg=load_config(ROOT/'examples/quick_report_en.json')
        self.source=self.root/'report.json'; self.out=self.root/'report.pdf'
        self.save()

    def save(self):
        self.source.write_text(json.dumps(self.cfg,ensure_ascii=False))

    def manifest(self):
        return load_config(bundle_path(self.out)/'manifest.json')

    def snapshot(self):
        state=bundle_path(self.out)
        return {'pdf':e.sha(self.out),**{str(p.relative_to(state)):e.sha(p) for p in state.rglob('*') if p.is_file()}}

    def test_unchanged_build_reuses_all_pages_and_pngs(self):
        build(self.source,self.out); first=self.snapshot()
        build(self.source,self.out); second=self.snapshot(); m=self.manifest()['build']
        self.assertEqual(m['rendered_ids'],[])
        self.assertEqual(m['qa_rendered_pages'],0)
        self.assertEqual(first['pdf'],second['pdf'])
        for path in first:
            if path.endswith('.png') or path.startswith('pages/'):
                self.assertEqual(first[path],second[path],path)

    def test_page_number_edit_preserves_other_page_bytes_and_renders(self):
        build(self.source,self.out); before=self.snapshot()
        replacement=copy.deepcopy(self.cfg['pages'][1]); replacement['title']='Decision summary'
        p=self.root/'page.json'; p.write_text(json.dumps(replacement))
        edit_page(self.out,'2',p)
        after=self.snapshot(); m=self.manifest()['build']
        self.assertEqual(m['changed_ids'],['summary'])
        self.assertEqual(m['rendered_ids'],['summary'])
        self.assertEqual(m['qa_rendered_pages'],1)
        for name in ('001-cover.pdf','003-pricing.pdf','004-closing.pdf'):
            self.assertEqual(before['pages/'+name],after['pages/'+name])
        for number in (1,3,4):
            name=f'qa/page-{number:03d}.png'; self.assertEqual(before[name],after[name])
        self.assertEqual(load_config(bundle_path(self.out)/'source.json')['pages'][1]['title'],'Decision summary')

    def test_failed_page_edit_preserves_pdf_source_and_bundle(self):
        build(self.source,self.out); before=self.snapshot()
        page=copy.deepcopy(self.cfg['pages'][1]); page['intro']='Very long explanatory material. '*300
        p=self.root/'page.json'; p.write_text(json.dumps(page))
        with self.assertRaisesRegex(ValueError,'FIT_FAIL'): edit_page(self.out,'2',p)
        self.assertEqual(before,self.snapshot())

    def test_strict_edit_rejects_other_page_and_shared_changes(self):
        build(self.source,self.out); before=self.snapshot()
        self.cfg['pages'][3]['text']+=' An additional next step.'; self.save()
        with self.assertRaisesRegex(ValueError,'untouched pages'): build(self.source,self.out,only_ids={'summary'},strict_only=True)
        self.assertEqual(before,self.snapshot())
        self.cfg['meta']['theme']='green'; self.save()
        with self.assertRaisesRegex(ValueError,'shared dependencies'): build(self.source,self.out,only_ids={'summary'},strict_only=True)
        self.assertEqual(before,self.snapshot())

    def test_changed_runtime_invalidates_surgery(self):
        from reportkit import pipeline
        build(self.source,self.out)
        original=pipeline.runtime_contract
        with patch.object(pipeline,'runtime_contract',side_effect=lambda f:{**original(f),'test_runtime_change':'new'}):
            build(self.source,self.out,only_ids={'summary'})
        self.assertEqual(self.manifest()['build']['mode'],'surgical-invalidated-full')
        self.assertEqual(len(self.manifest()['build']['rendered_ids']),4)

    def test_changed_font_bytes_invalidate_cache_in_same_process(self):
        build(self.source,self.out)
        override=self.root/'fonts'; override.mkdir()
        p=override/'Vazirmatn-Regular.ttf'; shutil.copyfile(FONT_DIR/p.name,p)
        with TTFont(p) as font:
            font['head'].fontRevision+=.001; font.save(p)
        with patch.dict(os.environ,{'REPORTKIT_FONT_DIR':str(override)}):
            build(self.source,self.out,only_ids={'summary'})
        self.assertEqual(self.manifest()['build']['mode'],'surgical-invalidated-full')
        self.assertEqual(len(self.manifest()['build']['rendered_ids']),4)

    def test_two_reports_in_one_directory_do_not_share_state(self):
        build(self.source,self.out); before=self.snapshot()
        other=self.root/'other.pdf'
        self.cfg['meta']['recipient']='Another client'; self.save(); build(self.source,other)
        self.assertEqual(before,self.snapshot())
        self.assertNotEqual(bundle_path(self.out),bundle_path(other))

    def test_failed_delivery_gate_preserves_last_good_report(self):
        build(self.source,self.out); before=self.snapshot(); original=e.header_footer
        def wrong(c,meta,number,title,theme): return original(c,meta,number+1,title,theme)
        with patch.object(e,'header_footer',side_effect=wrong):
            with self.assertRaisesRegex(RuntimeError,'wrong page counter'): build(self.source,self.out,force=True)
        self.assertEqual(before,self.snapshot())

    def test_source_mismatch_and_preview_fail_delivery(self):
        build(self.source,self.out)
        self.cfg['meta']['recipient']='Incorrect recipient'; self.save()
        with self.assertRaisesRegex(RuntimeError,'source/config identity'): verify_delivery(self.out,self.source)
        before=self.snapshot()
        with self.assertRaisesRegex(ValueError,'PREVIEW_FAIL'): build(self.source,self.out,run_qa=False)
        self.assertEqual(before,self.snapshot())
        build(self.source,self.root/'preview.pdf',run_qa=False)
        with self.assertRaisesRegex(RuntimeError,'preview'): verify_delivery(self.root/'preview.pdf',self.source,allow_test_font_fallback=True)

    def test_unsupported_glyph_fails_before_publishing(self):
        build(self.source,self.out); before=self.snapshot()
        self.cfg['pages'][1]['intro']+=' 🧪'; self.save()
        with self.assertRaisesRegex(ValueError,'GLYPH_FAIL'): build(self.source,self.out)
        self.assertEqual(before,self.snapshot())

    def test_exact_prices_and_required_content_are_guarded(self):
        page=self.cfg['pages'][2]
        self.assertEqual(calculate(page)['total'],Decimal('2000.00'))
        page['expected_total']='1999.99'
        with self.assertRaisesRegex(ValueError,'PRICE_FAIL'): validate_config(self.cfg)
        page['expected_total']='2000.00'; self.cfg['requirements']['required_text']=['Approved statement']
        with self.assertRaisesRegex(ValueError,'missing exact text'): validate_config(self.cfg)
        self.cfg['requirements'].pop('required_text'); page['items'][0]['unit_price']='2250.00'; page['expected_total']='3000.00'
        with self.assertRaisesRegex(ValueError,'preserve'): validate_config(self.cfg)

    def test_decimal_rounding_zero_prices_and_currency_precision(self):
        page=copy.deepcopy(self.cfg['pages'][2]); page.pop('expected_total')
        page['items']=[{'description':'Part A','quantity':'3','unit_price':'0.10'},{'description':'Part B','quantity':'1','unit_price':'0'}]
        self.assertEqual(calculate(page)['total'],Decimal('.30'))
        page['currency']='IRT'
        with self.assertRaisesRegex(ValueError,'currency-precision'): calculate(page)
        self.assertEqual(e.clean_text(0) if hasattr(e,'clean_text') else __import__('reportkit.visual_v05',fromlist=['clean_text']).clean_text(0),'0')

    def test_duplicate_json_keys_and_nonfinite_values_rejected(self):
        for raw in ('{"a":1,"a":2}','{"value":NaN}','{"value":Infinity}'):
            self.source.write_text(raw)
            with self.assertRaises(ValueError): load_config(self.source)

    def test_cli_schema_error_is_actionable_json(self):
        self.cfg['pages'][2]['currency']='INVALID'; self.save()
        error=io.StringIO()
        with redirect_stderr(error):
            code=main(['validate',str(self.source)])
        self.assertEqual(code,1)
        answer=json.loads(error.getvalue())
        self.assertEqual(answer['status'],'FAIL')
        self.assertIn('pages/2/currency',answer['error'])
        self.assertNotIn('Traceback',answer['error'])

    def test_fractional_signed_chart_retains_meaningful_axis_ticks(self):
        chart=next(p for p in load_config(ROOT/'examples/client_report.json')['pages'] if p['type']=='chart_text')
        chart['chart'].update(type='bar',labels=['Decrease','Unchanged','Increase'],data=[-.1,0,.2])
        self.cfg.pop('requirements'); self.cfg['pages']=[self.cfg['pages'][0],chart]; self.save()
        build(self.source,self.out)
        with fitz.open(self.out) as doc:
            lines=doc[1].get_text().splitlines()
        self.assertIn('-0.116',lines)
        self.assertIn('0.232',lines)
        self.assertIn('0',lines)
        self.assertNotIn('-0',lines)

    def test_tampered_cache_and_preview_renders_are_repaired(self):
        build(self.source,self.out); state=bundle_path(self.out)
        expected=e.sha(self.out)
        (state/'pages/002-summary.pdf').write_bytes(b'corrupt')
        build(self.source,self.out)
        self.assertEqual(e.sha(self.out),expected)
        self.assertEqual(self.manifest()['build']['rendered_ids'],['summary'])
        (state/'qa/page-003.png').write_bytes(b'corrupt')
        build(self.source,self.out)
        self.assertEqual(self.manifest()['build']['rendered_ids'],[])
        self.assertEqual(self.manifest()['build']['qa_rendered_pages'],1)

    def test_relocated_bundle_keeps_images_and_accepts_page_edit(self):
        image=self.root/'evidence.png'; Image.new('RGB',(200,100),'#658CF0').save(image)
        self.cfg['pages'].insert(2,{'id':'evidence','type':'image_text','title':'Evidence','image':'evidence.png','text':'An example image used to test a portable report.'})
        self.save(); build(self.source,self.out)
        moved=self.root/'moved'; moved.mkdir(); destination=moved/'report.pdf'
        shutil.copyfile(self.out,destination); shutil.copytree(bundle_path(self.out),bundle_path(destination))
        image.unlink()
        _accepted(destination)
        replacement=copy.deepcopy(self.cfg['pages'][1]); replacement['title']='A revised summary'
        p=self.root/'page.json'; p.write_text(json.dumps(replacement))
        edit_page(destination,'summary',p)
        self.assertTrue((bundle_path(destination)/'assets').is_dir())
        _accepted(destination)

    def test_incorrect_recipient_snapshot_or_lost_update_fails(self):
        build(self.source,self.out); old=self.manifest()['build']['source_sha256']
        self.cfg['pages'][1]['title']='New summary'; self.save(); build(self.source,self.out)
        with self.assertRaisesRegex(ValueError,'EDIT_CONFLICT'):
            build(self.source,self.out,only_ids={'summary'},strict_only=True,expected_source_sha=old)

    def test_foreign_bundle_directory_and_busy_output_are_protected(self):
        state=bundle_path(self.out); state.mkdir(); (state/'important.txt').write_text('keep')
        with self.assertRaisesRegex(ValueError,'unrecognized bundle'): build(self.source,self.out)
        self.assertEqual((state/'important.txt').read_text(),'keep')
        shutil.rmtree(state)
        with output_lock(self.out):
            with self.assertRaisesRegex(RuntimeError,'BUILD_BUSY'): build(self.source,self.out)
        build(self.source,self.out)  # Stable lock file is safe to reuse after release.

    def test_explicit_language_controls_counters_with_mixed_content(self):
        self.cfg['pages'][1]['title']='خلاصه'; self.save()
        build(self.source,self.out)
        result=verify_delivery(self.out,self.source)
        self.assertEqual(result['status'],'PASS')
        with fitz.open(self.out) as doc:
            self.assertIn('PAGE',doc[1].get_text())
            self.assertTrue(any('Vazirmatn' in f[3] for f in doc[1].get_fonts()))

if __name__=='__main__': unittest.main()
