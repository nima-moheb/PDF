"""One transaction from semantic input to verified final PDF."""
from __future__ import annotations
import contextlib
import ctypes
import importlib.metadata
import hashlib
import json
import os
import platform
import shutil
import tempfile
import threading
import time
from pathlib import Path
from pypdf import PdfReader, PdfWriter
from . import engine as e
from .contract import canonical_hash, load_config, normalized_config, source_identity, validate_config
from .fonts import register_fonts
from .qa import preflight_and_render
from .rtl import _fribidi
from .visual_v05 import _density_check

ENGINE_VERSION = '0.7.1'
_BUILD_LOCK = threading.RLock()  # Legacy visual components temporarily change module globals.


def bundle_path(out_pdf):
    path = Path(out_pdf).resolve()
    return path.with_name(path.stem + '.build')


def runtime_contract(fonts):
    root = Path(__file__).parent
    lib = _fribidi()
    bidi = 'python-fallback'
    if lib:
        try:
            bidi = ctypes.c_char_p.in_dll(lib, 'fribidi_version_info').value.decode()
        except (ValueError, AttributeError):
            bidi = str(lib._name)
    return {
        'engine': ENGINE_VERSION, 'python': platform.python_version(), 'bidi': bidi,
        'libraries': {name: importlib.metadata.version(name) for name in
                      ('reportlab', 'pypdf', 'fonttools', 'PyMuPDF', 'jsonschema', 'pillow')},
        'code': {p.name: e.sha(p) for p in sorted(root.glob('*.py'))},
        'schema': e.sha(root / 'data/report.schema.json'),
        'themes': e.sha(root / 'data/themes.json'), 'fonts': fonts,
    }


@contextlib.contextmanager
def output_lock(out_pdf):
    # OS locks are released after a crash. Keep the inode stable so queued
    # processes cannot accidentally lock two different files for one output.
    lock = out_pdf.with_name(out_pdf.name + '.lock')
    stream = lock.open('a+b')
    try:
        if os.name == 'nt':
            import msvcrt
            if lock.stat().st_size == 0:
                stream.write(b'0'); stream.flush()
            stream.seek(0)
            try: msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError: raise RuntimeError(f'BUILD_BUSY: {out_pdf.name}') from None
        else:
            import fcntl
            try: fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError: raise RuntimeError(f'BUILD_BUSY: {out_pdf.name}') from None
        yield
    finally:
        stream.close()


def _previous(out_pdf, state):
    try:
        manifest = load_config(state / 'manifest.json')
        if manifest['build']['final_pdf_sha256'] != e.sha(out_pdf):
            return None
        return manifest
    except (OSError, ValueError, KeyError, TypeError):
        return None


def _portable(cfg, config_dir, dest):
    cfg = normalized_config(cfg)
    for page in cfg['pages']:
        if page['type'] != 'image_text':
            continue
        src = (config_dir / Path(page['image']).expanduser()).resolve()
        if not src.is_file():
            raise ValueError(f"ASSET_FAIL: image page {page['id']} requires {src}")
        data = src.read_bytes()
        rel = Path('assets') / (hashlib.sha256(data).hexdigest() + src.suffix.lower())
        (dest / rel).parent.mkdir(exist_ok=True)
        (dest / rel).write_bytes(data)
        page['image'] = rel.as_posix()
    return cfg


def build(config_path, out_pdf, only_ids=None, run_qa=True, *, strict_only=False, force=False, expected_source_sha=None):
    """Reuse unchanged pages; commit only after all gates pass.

    strict_only aborts when shared inputs or any unrequested page have changed.
    """
    start = time.perf_counter()
    config_path = Path(config_path).resolve(); out_pdf = Path(out_pdf).resolve()
    if out_pdf.suffix.lower() != '.pdf':
        raise ValueError('BUILD_FAIL: output filename must end in .pdf')
    if config_path == out_pdf:
        raise ValueError('BUILD_FAIL: input and output must be different files')
    cfg = validate_config(load_config(config_path))
    requested = set(only_ids or [])
    known = {p['id'] for p in cfg['pages']}
    if requested - known:
        raise ValueError('SURGERY_FAIL: unknown page ids: ' + ', '.join(sorted(requested-known)))
    if strict_only and (not requested or force or not run_qa):
        raise ValueError('SURGERY_FAIL: strict edit requires page ids, QA, and no --force')
    out_pdf.parent.mkdir(parents=True, exist_ok=True)
    state = bundle_path(out_pdf)
    with _BUILD_LOCK, output_lock(out_pdf), tempfile.TemporaryDirectory(prefix=f'.{out_pdf.stem}-', dir=out_pdf.parent) as tmp:
        tmp = Path(tmp); stage = tmp / 'bundle'; stage.mkdir()
        cfg = _portable(cfg, config_path.parent, stage)
        fonts = register_fonts()
        runtime = runtime_contract(fonts)
        global_hash = canonical_hash({'runtime': runtime, 'meta': cfg['meta'],
                                      'requirements': cfg.get('requirements', {}),
                                      'structure': [p['id'] for p in cfg['pages']]})
        if state.exists():
            try:
                owner = load_config(state / 'manifest.json')
                if 'engine_version' not in owner.get('build', {}): raise ValueError('unknown owner')
            except (OSError, ValueError, TypeError):
                raise ValueError(f'BUILD_FAIL: refusing to replace unrecognized bundle directory {state}') from None
        previous = _previous(out_pdf, state)
        if not run_qa and previous and previous['build'].get('qa_status') == 'PASS':
            raise ValueError('PREVIEW_FAIL: use a separate output path; an accepted PDF cannot be replaced by a preview')
        if expected_source_sha is not None and (not previous or previous['build'].get('source_sha256') != expected_source_sha):
            raise ValueError('EDIT_CONFLICT: the accepted report changed since this edit was prepared')
        valid_global = previous and previous['build'].get('global_fingerprint') == global_hash
        inputs = {p['id']: canonical_hash(p) for p in cfg['pages']}
        changed = set(known)
        if valid_global and not force:
            changed = {pid for pid in known if previous['pages'].get(pid, {}).get('input_fingerprint') != inputs[pid]
                       or not e._artifact_matches(previous['pages'].get(pid), state / 'pages')}
        if strict_only:
            if not valid_global or previous['build'].get('qa_status') != 'PASS':
                raise ValueError('SURGERY_FAIL: accepted baseline or shared dependencies changed; full rebuild required')
            if changed - requested:
                raise ValueError('SURGERY_FAIL: untouched pages changed: ' + ', '.join(sorted(changed-requested)))
        render_ids = changed | requested
        if not valid_global or force:
            mode = 'surgical-invalidated-full' if requested else 'full'
        elif requested:
            mode = 'surgical-expanded' if changed-requested else 'surgical'
        else:
            mode = 'incremental' if changed else 'cached'
        pages_dir = stage / 'pages'; pages_dir.mkdir()
        meta = dict(cfg['meta'], _page_count=len(cfg['pages']), _config_dir=str(stage))
        manifest_pages = {}
        for index, page in enumerate(cfg['pages'], 1):
            pid = page['id']; path = pages_dir / f'{index:03d}-{pid}.pdf'
            if pid in render_ids:
                try:
                    e.render_page(meta, page, index, path)
                except (ValueError, RuntimeError) as exc:
                    raise type(exc)(f"page {index} ({pid}, {page['type']}): {exc}") from exc
            else:
                shutil.copyfile(state / 'pages' / previous['pages'][pid]['file'], path)
            manifest_pages[pid] = {'index': index, 'file': path.name, 'sha256': e.sha(path),
                                   'input_fingerprint': inputs[pid], 'type': page['type'], 'title': page['title']}
        source_sha = source_identity(cfg, stage)
        staged_pdf = tmp / 'result.pdf'
        writer = PdfWriter()
        for page in cfg['pages']:
            path = pages_dir / manifest_pages[page['id']]['file']
            reader = PdfReader(path)
            if len(reader.pages) != 1:
                raise RuntimeError(f'BUILD_FAIL: {path.name} is not exactly one page')
            writer.add_page(reader.pages[0])
        writer.add_metadata({'/Title': cfg['meta']['title'], '/Author': cfg['meta']['author'],
                             '/Producer': f'Nima Report Engine {ENGINE_VERSION}',
                             '/ReportKitSourceSHA256': source_sha,
                             '/ReportKitStatus': 'production' if run_qa else 'preview',
                             '/ReportKitLanguage': cfg['meta']['language'],
                             '/ReportKitMode': cfg['meta'].get('mode', 'report')})
        with staged_pdf.open('wb') as stream:
            writer.write(stream)
        writer.close()
        if any(p['type'] == 'closing' for p in cfg['pages']) and e._pdf_uri_count(staged_pdf, e.RESUME_URL) < 1:
            raise RuntimeError('LINK_FAIL: visible resume URL annotation missing')
        (stage / 'source.json').write_text(json.dumps(cfg, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        qa = None
        if run_qa:
            reusable = set(known) - render_ids if valid_global else set()
            qa = preflight_and_render(staged_pdf, stage / 'qa', expected_pages=len(cfg['pages']),
                                      previous_dir=state / 'qa', page_entries=list(manifest_pages.values()),
                                      reusable_ids=reusable, ordered_ids=[p['id'] for p in cfg['pages']])
            _density_check(staged_pdf, cfg)
            from .delivery import verify_delivery
            verify_delivery(staged_pdf, stage / 'source.json', expected_engine_version=ENGINE_VERSION)
        changed_hashes = [pid for pid in known if not previous or previous['pages'].get(pid, {}).get('sha256') != manifest_pages[pid]['sha256']]
        if strict_only and set(changed_hashes) - requested:
            raise RuntimeError('SURGERY_FAIL: unexpected page artifact change after merge')
        build_meta = {'engine_version': ENGINE_VERSION, 'mode': mode, 'global_fingerprint': global_hash,
                      'runtime_contract_sha256': canonical_hash(runtime), 'runtime': runtime,
                      'source_sha256': source_sha, 'final_pdf_sha256': e.sha(staged_pdf),
                      'page_count': len(cfg['pages']), 'qa_status': 'PASS' if run_qa else 'PREVIEW',
                      'rendered_ids': sorted(render_ids), 'reused_ids': sorted(known-render_ids),
                      'changed_ids': sorted(changed_hashes), 'qa_rendered_pages': qa['rendered_pages'] if qa else 0,
                      'duration_seconds': round(time.perf_counter()-start, 4)}
        (stage / 'manifest.json').write_text(json.dumps({'build': build_meta, 'pages': manifest_pages}, ensure_ascii=False, indent=2)+'\n')
        # PDF replacement is the commit point. Ordinary exceptions also restore
        # the previous editable bundle; an interrupted process fails hash checks.
        backup = tmp / 'previous'
        if state.exists(): state.rename(backup)
        try:
            stage.rename(state)
            os.replace(staged_pdf, out_pdf)
        except BaseException:
            if state.exists(): shutil.rmtree(state)
            if backup.exists(): backup.rename(state)
            raise
        return manifest_pages
