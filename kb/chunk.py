"""Structure-aware chunking.

Chunking quality decides whether retrieval works. Splitting every N
characters cuts procedures in half. We split on document structure first
(markdown headings, then blank-line paragraphs) and only fall back to a
hard split for oversized blocks. Each chunk carries its heading trail so
a retrieved fragment still says which section it came from.
"""
import re

MAX_CHARS = 1200
OVERLAP = 150


def chunk_text(text: str, source: str):
    blocks, heading = [], ""
    buf = []
    for line in text.splitlines():
        m = re.match(r"^(#{1,6})\s+(.*)", line)
        if m:
            if buf:
                blocks.append((heading, "\n".join(buf).strip()))
                buf = []
            heading = m.group(2).strip()
        else:
            buf.append(line)
    if buf:
        blocks.append((heading, "\n".join(buf).strip()))

    chunks = []
    for heading, body in blocks:
        if not body:
            continue
        for piece in _pack(body):
            chunks.append({
                "text": (f"[{heading}]\n{piece}" if heading else piece),
                "source": source,
                "section": heading,
            })
    return chunks


def _pack(body: str):
    paras = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
    out, cur = [], ""
    for p in paras:
        if len(cur) + len(p) + 2 <= MAX_CHARS:
            cur = f"{cur}\n\n{p}" if cur else p
        else:
            if cur:
                out.append(cur)
            if len(p) <= MAX_CHARS:
                cur = p
            else:
                for i in range(0, len(p), MAX_CHARS - OVERLAP):
                    out.append(p[i : i + MAX_CHARS])
                cur = ""
    if cur:
        out.append(cur)
    return out
