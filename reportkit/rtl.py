from __future__ import annotations

import ctypes
import ctypes.util
import re
import unicodedata
from functools import lru_cache

LTR_TOKEN = r"(?:https?://\S+|www\.\S+|[\w.+-]+@[\w.-]+|[A-Za-z0-9][A-Za-z0-9_./:%+@#?=&-]*|[0-9۰-۹٠-٩][0-9۰-۹٠-٩.,:%+-]*)"
LTR_RE = re.compile(rf"{LTR_TOKEN}(?:\s+{LTR_TOKEN})*")


@lru_cache(maxsize=1)
def _fribidi():
    name = ctypes.util.find_library("fribidi")
    if not name:
        return None
    try:
        lib = ctypes.CDLL(name)
        lib.fribidi_log2vis.argtypes = [
            ctypes.POINTER(ctypes.c_uint32),
            ctypes.c_int,
            ctypes.POINTER(ctypes.c_uint32),
            ctypes.POINTER(ctypes.c_uint32),
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_void_p,
        ]
        lib.fribidi_log2vis.restype = ctypes.c_int
        return lib
    except Exception:
        return None


@lru_cache(maxsize=1)
def _forms():
    forms = {}
    for cp in list(range(0xFB50, 0xFE00)) + list(range(0xFE70, 0xFF00)):
        ch = chr(cp)
        name = unicodedata.name(ch, "")
        if not name.startswith("ARABIC LETTER ") or not name.endswith(" FORM"):
            continue
        for kind in ("ISOLATED", "FINAL", "INITIAL", "MEDIAL"):
            suffix = f" {kind} FORM"
            if not name.endswith(suffix):
                continue
            base_name = name[:-len(suffix)]
            for bcp in range(0x0600, 0x08FF):
                b = chr(bcp)
                if unicodedata.name(b, "") == base_name:
                    forms.setdefault(b, {})[kind.lower()] = ch
                    break
    return forms


def _arabic_char(ch):
    return ch in _forms()


def _can_prev(ch):
    f = _forms().get(ch, {})
    return "final" in f or "medial" in f


def _can_next(ch):
    f = _forms().get(ch, {})
    return "initial" in f or "medial" in f


def shape_token(token: str) -> str:
    f = _forms()
    out = []
    chars = list(token)
    for i, ch in enumerate(chars):
        if ch not in f:
            out.append(ch)
            continue
        prev = chars[i - 1] if i > 0 else ""
        nxt = chars[i + 1] if i + 1 < len(chars) else ""
        join_prev = bool(prev) and prev != "\u200c" and _arabic_char(prev) and _can_next(prev) and _can_prev(ch)
        join_next = bool(nxt) and nxt != "\u200c" and _arabic_char(nxt) and _can_next(ch) and _can_prev(nxt)
        forms = f[ch]
        if join_prev and join_next and "medial" in forms:
            out.append(forms["medial"])
        elif join_prev and "final" in forms:
            out.append(forms["final"])
        elif join_next and "initial" in forms:
            out.append(forms["initial"])
        else:
            out.append(forms.get("isolated", ch))
    return "".join(out).replace("\u200c", "")


def _fallback_visual(text: str) -> str:
    parts = []
    pos = 0
    for m in LTR_RE.finditer(text):
        if m.start() > pos:
            parts.append(("rtl", text[pos:m.start()]))
        parts.append(("ltr", m.group(0)))
        pos = m.end()
    if pos < len(text):
        parts.append(("rtl", text[pos:]))
    vis = []
    for kind, chunk in reversed(parts):
        vis.append(chunk if kind == "ltr" else shape_token(chunk)[::-1])
    return "".join(vis)


def _protect_ltr_tokens(text: str):
    tokens = []

    def repl(match):
        idx = len(tokens)
        if idx >= 0x1900:
            raise ValueError("RTL_FAIL: too many protected LTR tokens")
        tokens.append(match.group(0))
        return chr(0xE000 + idx)

    return LTR_RE.sub(repl, text), tokens


def _restore_ltr_tokens(text: str, tokens):
    for idx, token in enumerate(tokens):
        text = text.replace(chr(0xE000 + idx), token)
    return text


def visual_rtl(text: str) -> str:
    """Return visual-order Arabic/Persian text.

    Complete LTR tokens are protected before bidi processing so punctuation inside
    percentages, versions, URLs, emails, and English phrases cannot be reordered.
    FriBidi performs paragraph reordering + Arabic shaping when available; the
    deterministic pure-Python path remains the portability fallback.
    """
    protected, tokens = _protect_ltr_tokens(text)
    lib = _fribidi()
    if lib and protected:
        src = (ctypes.c_uint32 * len(protected))(*map(ord, protected))
        dst = (ctypes.c_uint32 * len(protected))()
        base_dir = ctypes.c_uint32(0)  # auto-detect paragraph direction
        ok = lib.fribidi_log2vis(src, len(protected), ctypes.byref(base_dir), dst, None, None, None)
        if ok:
            return _restore_ltr_tokens("".join(chr(cp) for cp in dst), tokens)
    return _fallback_visual(text)


def _is_latinish(ch: str) -> bool:
    o = ord(ch)
    if ch.isspace():
        return False
    return (
        "LATIN" in unicodedata.name(ch, "")
        or ch.isdigit()
        or 0x0660 <= o <= 0x0669
        or 0x06F0 <= o <= 0x06F9
        or ch in "./:%+@#?=&-_()[]{}<>\\|,;!$€£¥'\""
    )


def visual_runs(text: str):
    """Return visual left-to-right runs as ``(kind, text)``.

    The full string is first reordered by FriBidi/fallback, then split only for font
    selection. This avoids the previous ad-hoc run reversal for mixed Persian/Latin.
    """
    visual = visual_rtl(text)
    if not visual:
        return []
    runs = []
    buf = []
    kind = None
    for ch in visual:
        ck = "ltr" if _is_latinish(ch) else "rtl"
        if ch.isspace() and kind is not None:
            ck = kind
        if kind is None:
            kind = ck
        if ck != kind and buf:
            runs.append((kind, "".join(buf)))
            buf = []
            kind = ck
        buf.append(ch)
    if buf:
        runs.append((kind or "rtl", "".join(buf)))
    return runs
