"""Small chat-facing interface: validate, build, inspect, edit, verify, pack."""
from __future__ import annotations
import argparse
import json
import sys
import tempfile
import zipfile
from pathlib import Path
from jsonschema import ValidationError
from .contract import load_config, validate_config, source_identity
from .pipeline import build, bundle_path, runtime_contract, output_lock
from .delivery import verify_delivery
from .engine import sha
from .fonts import register_fonts


def _accepted(output):
    output=Path(output).resolve(); state=bundle_path(output)
    manifest=load_config(state/'manifest.json')
    if manifest['build']['qa_status']!='PASS' or manifest['build']['final_pdf_sha256']!=sha(output):
        raise ValueError('DELIVERY_FAIL: output differs from its accepted build receipt; restore the PDF and its .build folder together from the same editable archive')
    qa=load_config(state/'qa/qa_manifest.json')
    if qa['pdf_sha256']!=sha(output): raise ValueError('DELIVERY_FAIL: rendered QA receipt does not match')
    verify_delivery(output,state/'source.json')
    return state,manifest


def edit_page(output, selector, replacement):
    state,manifest=_accepted(output)
    cfg=load_config(state/'source.json')
    # Numeric selectors are the page number shown by a PDF viewer, including cover.
    if str(selector).isdigit():
        index=int(selector)-1
        if not 0<=index<len(cfg['pages']): raise ValueError('EDIT_FAIL: page number is out of range')
    else:
        index=next((i for i,p in enumerate(cfg['pages']) if p['id']==selector),None)
        if index is None: raise ValueError(f'EDIT_FAIL: unknown page {selector}')
    old=cfg['pages'][index]
    page=load_config(replacement)
    if page.get('id')!=old['id']: raise ValueError(f"EDIT_FAIL: replacement must retain id {old['id']!r}")
    cfg['pages'][index]=page
    # Resolve existing evidence before writing a temporary candidate outside the
    # accepted bundle. A failed edit never changes its source.json.
    for p in cfg['pages']:
        if p['type']=='image_text':
            base=Path(replacement).resolve().parent if p['id']==page['id'] else state
            p['image']=str((base/Path(p['image']).expanduser()).resolve())
    with tempfile.TemporaryDirectory(prefix='report-edit-') as tmp:
        candidate=Path(tmp)/'source.json'; candidate.write_text(json.dumps(cfg,ensure_ascii=False))
        build(candidate,output,only_ids={old['id']},strict_only=True,expected_source_sha=manifest['build']['source_sha256'])
    return load_config(bundle_path(output)/'manifest.json')['build']


def result(output):
    state=bundle_path(output); info=load_config(state/'manifest.json')['build']
    return {'status':info['qa_status'],'pdf':str(Path(output).resolve()),'editable_source':str(state/'source.json'),
            'qa':str(state/'qa'),'mode':info['mode'],'rendered_pages':info['rendered_ids'],
            'unchanged_pages':info['reused_ids'],'seconds':info['duration_seconds']}


def pack_report(output, archive):
    output=Path(output).resolve(); archive=Path(archive).resolve(); state=bundle_path(output)
    if archive.suffix.lower()!='.zip' or archive.is_dir():
        raise ValueError('PACK_FAIL: archive must be a .zip file')
    if archive==output or archive==state or state in archive.parents:
        raise ValueError('PACK_FAIL: archive must be outside the editable bundle and differ from the PDF')
    # Hold the writer's lock from acceptance through archive commit. Otherwise
    # an edit can replace the source/pages halfway through creating the ZIP.
    with output_lock(output):
        _accepted(output)
        archive.parent.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=archive.parent) as tmp:
            tmpzip=Path(tmp)/'bundle.zip'
            with zipfile.ZipFile(tmpzip,'w',zipfile.ZIP_DEFLATED) as z:
                z.write(output,output.name)
                for f in sorted(state.rglob('*')):
                    if f.is_file(): z.write(f,state.name+'/'+str(f.relative_to(state)))
            tmpzip.replace(archive)
    return {'status':'PASS','archive':str(archive)}


def main(argv=None):
    parser=argparse.ArgumentParser(description='Compile and safely revise multilingual reports.')
    sub=parser.add_subparsers(dest='command',required=True)
    sub.add_parser('doctor',help='Check runtime and bundled fonts; no network required.')
    p=sub.add_parser('validate'); p.add_argument('input')
    p=sub.add_parser('build'); p.add_argument('input'); p.add_argument('output')
    p.add_argument('--only',action='append',default=[]); p.add_argument('--strict-only',action='store_true')
    p.add_argument('--force',action='store_true'); p.add_argument('--preview',action='store_true')
    p=sub.add_parser('inspect'); p.add_argument('output')
    p=sub.add_parser('edit'); p.add_argument('output'); p.add_argument('--page',required=True); p.add_argument('--replacement',required=True)
    p=sub.add_parser('verify'); p.add_argument('output'); p.add_argument('--config')
    p=sub.add_parser('pack'); p.add_argument('output'); p.add_argument('archive')
    args=parser.parse_args(argv)
    try:
        if args.command=='doctor':
            contract=runtime_contract(register_fonts())
            answer={'status':'PASS','engine':contract['engine'],'python':contract['python'],
                    'libraries':contract['libraries'],'fonts':contract['fonts'],'bidi':contract['bidi'].splitlines()[0]}
        elif args.command=='validate':
            cfg=validate_config(load_config(args.input)); source_identity(cfg,Path(args.input).resolve().parent)
            answer={'status':'PASS','pages':len(cfg['pages'])}
        elif args.command=='build':
            build(args.input,args.output,only_ids=args.only,strict_only=args.strict_only,force=args.force,run_qa=not args.preview)
            answer=result(args.output)
        elif args.command=='inspect':
            _,manifest=_accepted(args.output)
            answer={'pdf':str(Path(args.output).resolve()),'pages':manifest['pages']}
        elif args.command=='edit':
            edit_page(args.output,args.page,args.replacement); answer=result(args.output)
        elif args.command=='verify':
            state,_=_accepted(args.output)
            answer=verify_delivery(args.output,args.config or state/'source.json')
        elif args.command=='pack':
            answer=pack_report(args.output,args.archive)
        print(json.dumps(answer,ensure_ascii=False,indent=2))
        return 0
    except (ValueError,RuntimeError,OSError,KeyError,ValidationError) as exc:
        print(json.dumps({'status':'FAIL','error':str(exc)},ensure_ascii=False),file=sys.stderr)
        return 1
