import re
import unicodedata
from functools import lru_cache

LTR_TOKEN = r"(?:https?://\S+|www\.\S+|[\w.+-]+@[\w.-]+|[A-Za-z0-9][A-Za-z0-9_./:%+@#?=&-]*|[0-9۰-۹٠-٩][0-9۰-۹٠-٩.,:%+-]*)"
LTR_RE = re.compile(rf"{LTR_TOKEN}(?:\s+{LTR_TOKEN})*")

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
            if name.endswith(suffix):
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
        prev = chars[i-1] if i > 0 else ""
        nxt = chars[i+1] if i + 1 < len(chars) else ""
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

def visual_rtl(text: str) -> str:
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
        if kind == "ltr":
            vis.append(chunk)
        else:
            shaped = shape_token(chunk)
            vis.append(shaped[::-1])
    return "".join(vis)


def visual_runs(text: str):
    """Return visual left-to-right runs as (kind, text). RTL runs are shaped and reversed; LTR runs preserved."""
    parts=[]; pos=0
    for m in LTR_RE.finditer(text):
        if m.start()>pos: parts.append(("rtl", text[pos:m.start()]))
        parts.append(("ltr", m.group(0)))
        pos=m.end()
    if pos<len(text): parts.append(("rtl", text[pos:]))
    out=[]
    for kind,chunk in reversed(parts):
        if not chunk: continue
        out.append((kind, chunk if kind=="ltr" else shape_token(chunk)[::-1]))
    return out
