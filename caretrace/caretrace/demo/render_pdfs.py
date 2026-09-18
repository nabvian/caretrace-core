"""Render the synthetic demo corpus to real PDFs.

The point of rendering actual PDFs (rather than feeding text straight to the
engine) is that the demo case then travels the identical ingestion path as a
user upload: pypdf text extraction -> extractor -> normalizer -> audit. If the
demo works, upload works.
"""
from __future__ import annotations

from pathlib import Path

from reportlab.lib.pagesizes import LETTER
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from .case_ct_demo_001 import DOCUMENTS

PDF_DIR = Path(__file__).with_name("pdfs")

LEFT = 18 * mm
TOP = 18 * mm
LEADING = 11.2
FONT = "Courier"
FONT_BOLD = "Courier-Bold"
SIZE = 8.6


def _draw_page(c: canvas.Canvas, text: str, title: str, footer: str) -> None:
    width, height = LETTER

    # Title rule
    c.setFont(FONT_BOLD, 10.5)
    c.drawString(LEFT, height - TOP, title)
    c.setStrokeColorRGB(0.15, 0.18, 0.22)
    c.setLineWidth(0.9)
    c.line(LEFT, height - TOP - 4.5, width - LEFT, height - TOP - 4.5)

    y = height - TOP - 20
    c.setFont(FONT, SIZE)
    c.setFillColorRGB(0.08, 0.10, 0.13)
    for line in text.splitlines():
        if y < 26 * mm:
            break
        c.drawString(LEFT, y, line[:96])
        y -= LEADING

    # Footer
    c.setFont(FONT, 6.6)
    c.setFillColorRGB(0.45, 0.48, 0.52)
    c.drawString(LEFT, 14 * mm, footer)
    c.setFillColorRGB(0.08, 0.10, 0.13)


def _rasterise(text: str, title: str, footer: str) -> "ImageReader":
    """Render a page to a bitmap — a document with no text layer, i.e. a scan.

    Used for the corpus document that is meant to arrive as a scan. Extracting
    from it requires OCR, which the MVP does not ship, so the page must yield
    no text and be reported as extraction-incomplete.
    """
    from io import BytesIO

    from PIL import Image, ImageDraw, ImageFont
    from reportlab.lib.utils import ImageReader

    scale = 2  # ~144 dpi
    w, h = int(LETTER[0] * scale), int(LETTER[1] * scale)
    img = Image.new("L", (w, h), 246)   # slightly grey, like a real scan
    draw = ImageDraw.Draw(img)

    def _font(size: int):
        for name in ("DejaVuSansMono.ttf", "Courier New.ttf", "cour.ttf"):
            try:
                return ImageFont.truetype(name, size)
            except OSError:
                continue
        return ImageFont.load_default()

    fnt, fnt_b, fnt_s = _font(15), _font(19), _font(12)
    x, y = int(LEFT * scale), int(TOP * scale)
    draw.text((x, y), title, font=fnt_b, fill=40)
    y += 26
    draw.line([(x, y), (w - x, y)], fill=70, width=2)
    y += 22
    for line in text.splitlines():
        draw.text((x, y), line[:96], font=fnt, fill=35)
        y += int(LEADING * scale * 0.92)
    draw.text((x, h - int(14 * mm * scale)), footer, font=fnt_s, fill=130)

    # A faint skew and border, so it reads visually as a scanned page.
    img = img.rotate(-0.35, resample=Image.BICUBIC, fillcolor=246)
    ImageDraw.Draw(img).rectangle([2, 2, w - 3, h - 3], outline=205, width=3)

    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return ImageReader(buf)


def render_all(out_dir: Path | str = PDF_DIR) -> list[Path]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for doc in DOCUMENTS:
        path = out_dir / doc["filename"]
        c = canvas.Canvas(str(path), pagesize=LETTER)
        c.setTitle(doc["filename"])
        c.setAuthor("CARETRACE synthetic demo corpus")
        c.setSubject("Synthetic demonstration document - not a real medical record")
        n = len(doc["pages"])
        scanned = doc.get("scanned", False)
        for i, page_text in enumerate(doc["pages"], start=1):
            footer = (f"SYNTHETIC DEMONSTRATION DOCUMENT - CT-DEMO-001 - "
                      f"{doc['filename']} - page {i} of {n}")
            if scanned:
                c.drawImage(_rasterise(page_text, doc["title"], footer),
                            0, 0, width=LETTER[0], height=LETTER[1])
            else:
                _draw_page(c, page_text, doc["title"], footer)
            c.showPage()
        c.save()
        written.append(path)
    return written


if __name__ == "__main__":
    paths = render_all()
    for p in paths:
        print(p.name, p.stat().st_size)
