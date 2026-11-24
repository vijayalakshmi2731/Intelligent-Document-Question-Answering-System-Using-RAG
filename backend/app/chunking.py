"""Cleaning + chunking with page/section tracking."""
import re
from collections import Counter

_SENT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(\[])")


def clean_text(text: str) -> str:
    text = text.replace("\x00", " ").replace("­", "")
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)          # de-hyphenate line wraps
    text = re.sub(r"[ \t ]+", " ", text)
    text = re.sub(r"^\s*(page\s+)?\d+(\s+of\s+\d+)?\s*$", "", text, flags=re.I | re.M)  # bare page numbers
    text = re.sub(r"\n{3,}", "\n\n", text)
    # single newlines inside paragraphs -> spaces
    text = re.sub(r"(?<!\n)\n(?!\n)", " ", text)
    return text.strip()


def strip_repeated_lines(units):
    """Remove headers/footers repeating on most pages."""
    paged = [u for u in units if u["page"] is not None]
    if len(paged) < 4:
        return units
    counts = Counter()
    for u in paged:
        for ln in {l.strip() for l in u["text"].splitlines() if l.strip()}:
            counts[ln] += 1
    repeated = {l for l, c in counts.items() if c >= max(3, int(0.6 * len(paged))) and len(l) < 120}
    if not repeated:
        return units
    out = []
    for u in units:
        lines = [l for l in u["text"].splitlines() if l.strip() not in repeated]
        out.append({**u, "text": "\n".join(lines)})
    return out


def _split_long(piece: str, size: int):
    if len(piece) <= size:
        return [piece]
    sents = _SENT.split(piece)
    out, cur = [], ""
    for s in sents:
        while len(s) > size:                       # hard split pathological sentences
            out.append(s[:size]); s = s[size:]
        if len(cur) + len(s) + 1 > size and cur:
            out.append(cur); cur = s
        else:
            cur = f"{cur} {s}".strip()
    if cur:
        out.append(cur)
    return out


def chunk_units(units, chunk_size=800, overlap=150):
    chunk_size = max(200, int(chunk_size))
    overlap = max(0, min(int(overlap), chunk_size // 2))
    chunks = []
    for u in strip_repeated_lines(units):
        text = clean_text(u["text"])
        if not text:
            continue
        pieces = []
        for para in re.split(r"\n{2,}", text):
            pieces.extend(_split_long(para.strip(), chunk_size))
        cur = ""
        for p in pieces:
            if cur and len(cur) + len(p) + 1 > chunk_size:
                chunks.append({"page": u["page"], "section": u["section"], "text": cur})
                tail = cur[-overlap:] if overlap else ""
                if tail:                              # start overlap on a word boundary
                    tail = tail[tail.find(" ") + 1:] if " " in tail else tail
                cur = f"{tail} {p}".strip()
            else:
                cur = f"{cur} {p}".strip()
        if cur and len(cur) > 20:
            chunks.append({"page": u["page"], "section": u["section"], "text": cur})
    return chunks
