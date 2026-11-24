"""Text extraction. Returns a list of units: {page, section, text}."""
import csv, io, re
from html.parser import HTMLParser
from pathlib import Path


class ExtractionError(Exception):
    pass


def extract_pdf(path: Path):
    from pypdf import PdfReader
    try:
        reader = PdfReader(str(path))
        if reader.is_encrypted:
            reader.decrypt("")
        units = []
        for i, page in enumerate(reader.pages, 1):
            units.append({"page": i, "section": "", "text": page.extract_text() or ""})
        return units
    except Exception as e:
        raise ExtractionError(f"Unreadable PDF: {e}")


def extract_docx(path: Path):
    import docx
    try:
        d = docx.Document(str(path))
    except Exception as e:
        raise ExtractionError(f"Unreadable DOCX: {e}")
    units, section, buf = [], "", []

    def flush():
        if buf:
            units.append({"page": None, "section": section, "text": "\n".join(buf)})
            buf.clear()

    for p in d.paragraphs:
        txt = p.text.strip()
        if not txt:
            continue
        if (p.style.name or "").lower().startswith(("heading", "title")):
            flush()
            section = txt
        else:
            buf.append(txt)
    for t in d.tables:
        for row in t.rows:
            buf.append(" | ".join(c.text.strip() for c in row.cells))
    flush()
    return units


class _HTMLText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts, self.skip = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.skip += 1
        if tag in ("p", "br", "div", "li", "h1", "h2", "h3", "tr"):
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self.skip:
            self.skip -= 1

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def _decode(raw: bytes) -> str:
    for enc in ("utf-8-sig", "utf-16", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeError:
            continue
    return raw.decode("utf-8", "ignore")


def extract_text_like(path: Path, ext: str):
    text = _decode(path.read_bytes())
    if ext in (".html", ".htm"):
        p = _HTMLText()
        p.feed(text)
        text = "".join(p.parts)
    elif ext == ".csv":
        rows = csv.reader(io.StringIO(text))
        text = "\n".join(", ".join(r) for r in rows)
    units, section, buf = [], "", []
    for line in text.splitlines():
        m = re.match(r"^#{1,6}\s+(.*)", line) if ext == ".md" else None
        if m:
            if buf:
                units.append({"page": None, "section": section, "text": "\n".join(buf)})
                buf = []
            section = m.group(1).strip()
        else:
            buf.append(line)
    if buf:
        units.append({"page": None, "section": section, "text": "\n".join(buf)})
    return units


def extract(path: Path, ext: str):
    ext = ext.lower()
    if ext == ".pdf":
        units = extract_pdf(path)
    elif ext == ".docx":
        units = extract_docx(path)
    else:
        units = extract_text_like(path, ext)
    if not any(u["text"].strip() for u in units):
        raise ExtractionError("Document is empty or contains no extractable text (scanned image?)")
    return units
