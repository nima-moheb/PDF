"""Validate the semantic report before spending time rendering it."""
from __future__ import annotations

import copy
import hashlib
import json
import math
from pathlib import Path

from jsonschema import Draft202012Validator, ValidationError

from . import engine as e
from .visual_v05 import clean_text, _variety_check

_VALIDATOR = Draft202012Validator(e.SCHEMA)
_PAGE_DEFS = {d['properties']['type']['const']: d for d in e.SCHEMA['$defs'].values()
              if isinstance(d, dict) and isinstance(d.get('properties', {}).get('type'), dict)}


def strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from strings(item)


def canonical_hash(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def language(cfg):
    explicit = cfg['meta'].get('language')
    if explicit:
        return explicit
    cover = cfg['pages'][0]
    return 'fa' if cover.get('direction') == 'rtl' or e.is_fa(cfg['meta']['title']) else 'en'


def load_config(path):
    def unique(pairs):
        out = {}
        for key, value in pairs:
            if key in out:
                raise ValueError(f"SCHEMA_FAIL: duplicate JSON key {key!r}")
            out[key] = value
        return out
    def nonfinite(value):
        raise ValueError(f"DATA_FAIL: non-finite JSON number {value}")
    return json.loads(Path(path).read_text(encoding='utf-8-sig'),
                      object_pairs_hook=unique, parse_constant=nonfinite)


def validate_config(cfg):
    errors = list(_VALIDATOR.iter_errors(cfg))
    if errors:
        # Avoid dumping the entire oneOf schema into a chat on a single typo.
        error = errors[0]
        if error.validator == 'oneOf' and isinstance(error.instance, dict):
            typ = error.instance.get('type')
            target = _PAGE_DEFS.get(typ)
            if target:
                local = Draft202012Validator({**target, '$defs': e.SCHEMA['$defs']})
                details = list(local.iter_errors(error.instance))
                if details:
                    d = details[0]
                    location = '/'.join(map(str, list(error.absolute_path) + list(d.absolute_path)))
                    raise ValidationError(f"SCHEMA_FAIL at {location}: {d.message}")
        location = '/'.join(map(str, error.absolute_path)) or 'root'
        raise ValidationError(f"SCHEMA_FAIL at {location}: {error.message}")
    e.semantic_validate(cfg)
    _variety_check(cfg)
    # Requirements may legitimately name text that is forbidden in the report.
    e.scrub({'meta': cfg['meta'], 'pages': cfg['pages']})
    for page in cfg['pages']:
        if page['type'] == 'chart_text' and not all(math.isfinite(n) for n in page['chart']['data']):
            raise ValueError(f"DATA_FAIL: {page['id']} contains non-finite chart data")
        if page['type'] == 'pricing':
            from .pricing import calculate
            calculate(page)
    req = cfg.get('requirements', {})
    ids = {p['id'] for p in cfg['pages']}
    for pid in req.get('required_page_ids', []):
        if pid not in ids:
            raise ValueError(f"REQUIREMENT_FAIL: missing required page {pid}")
    public = '\n'.join(strings({'meta': cfg['meta'], 'pages': cfg['pages']}))
    for text in req.get('required_text', []):
        if text not in public:
            raise ValueError(f"REQUIREMENT_FAIL: missing exact text {text!r}")
    for text in req.get('forbidden_text', []):
        if text.casefold() in public.casefold():
            raise ValueError(f"REQUIREMENT_FAIL: forbidden text {text!r}")
    for item in req.get('protected_values', []):
        page = next((p for p in cfg['pages'] if p['id'] == item['page_id']), None)
        if page is None or item['value'] not in set(strings(page)):
            raise ValueError(f"REQUIREMENT_FAIL: preserve {item['value']!r} on page {item['page_id']}")
    lang = language(cfg)
    direction = cfg['pages'][0].get('direction', 'auto')
    if direction != 'auto' and direction != ('rtl' if lang == 'fa' else 'ltr'):
        raise ValueError('LANGUAGE_FAIL: cover direction conflicts with meta.language')
    return cfg


def normalized_config(cfg):
    """Add only deterministic engine defaults; never rewrite business content."""
    cfg = copy.deepcopy(cfg)
    cfg['meta'].setdefault('language', language(cfg))
    if cfg['meta']['language'] == 'fa' and cfg['meta']['author'] == 'Nima Moheb':
        cfg['meta']['author'] = 'نیما محب'
    return cfg


def source_identity(cfg, config_dir):
    """Source identity survives relocation of an editable bundle."""
    cfg = normalized_config(cfg)
    for page in cfg['pages']:
        if page['type'] == 'image_text':
            asset = (Path(config_dir) / Path(page['image']).expanduser()).resolve()
            if not asset.is_file():
                raise ValueError(f"ASSET_FAIL: image page {page['id']} requires {asset}")
            page['image'] = {'sha256': hashlib.sha256(asset.read_bytes()).hexdigest()}
    return canonical_hash(cfg)
