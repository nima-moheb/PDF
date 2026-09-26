from __future__ import annotations

import hashlib
import os
from importlib.resources import files
from pathlib import Path

from . import engine as e
from .delivery import verify_delivery

_INSTALLED = False
_ORIG_BUILD = None


def _runtime_contract_hash_v061():
    h = hashlib.sha256()
    for path in (
        Path(e.__file__),
        Path(e.__file__).with_name("rtl.py"),
        Path(e.__file__).with_name("qa.py"),
        Path(e.__file__).with_name("visual_v05.py"),
        Path(e.__file__).with_name("visual_v06.py"),
        Path(e.__file__).with_name("delivery.py"),
        Path(__file__),
    ):
        h.update(path.read_bytes())
    h.update(files("reportkit").joinpath("data/report.schema.json").read_bytes())
    h.update(files("reportkit").joinpath("data/themes.json").read_bytes())
    return h.hexdigest()


def build_v061(config_path, out_pdf, only_ids=None, run_qa=True):
    result = _ORIG_BUILD(config_path, out_pdf, only_ids=only_ids, run_qa=run_qa)
    if run_qa:
        allow_test = os.environ.get("REPORTKIT_INTERNAL_TEST") == "1"
        verify_delivery(
            out_pdf,
            config_path,
            expected_engine_version=e.ENGINE_VERSION,
            allow_test_font_fallback=allow_test,
        )
    return result


def install():
    global _INSTALLED, _ORIG_BUILD
    if _INSTALLED:
        return
    _INSTALLED = True

    _ORIG_BUILD = e.build
    e.ENGINE_VERSION = "0.6.1"
    e._runtime_contract_hash = _runtime_contract_hash_v061
    e.build = build_v061
