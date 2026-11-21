import base64
import io
import os
import re

from docx import Document
from docx.enum.section import WD_ORIENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Mm, Pt, RGBColor

from models import DocumentSpec, safe_hex, tint

FONT = {"Helvetica": "Arial", "Times": "Times New Roman", "Courier": "Courier New", "NotoSans": "Noto Sans"}
ALIGN = {"left": WD_ALIGN_PARAGRAPH.LEFT, "center": WD_ALIGN_PARAGRAPH.CENTER,
         "right": WD_ALIGN_PARAGRAPH.RIGHT, "justify": WD_ALIGN_PARAGRAPH.JUSTIFY}
TONES = {"info": "#2f6fed", "success": "#1f8a4c", "warning": "#c77d0a", "danger": "#c0392b"}
rgb = lambda h: RGBColor.from_string(h.lstrip("#").upper())


def _load_image_bytes(url: str) -> bytes | None:
    if not url:
        return None
    if url.startswith("data:"):
        _, _, encoded = url.partition(",")
        if encoded:
            try:
                return base64.b64decode(encoded)
            except Exception:
                return None
        return None
    if url.startswith("http://") or url.startswith("https://"):
        import urllib.request
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "DocForge/1.0"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.read()
        except Exception:
            return None
    if os.path.exists(url):
        try:
            with open(url, "rb") as f:
                return f.read()
        except Exception:
            return None
    return None


def shade(cell, hex_color):
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear"); shd.set(qn("w:color"), "auto"); shd.set(qn("w:fill"), hex_color.lstrip("#"))
    cell._tc.get_or_add_tcPr().append(shd)


def runs(p, text, color=None, bold=False):
    for part in re.split(r"(\*\*.+?\*\*)", text):
        strong = part.startswith("**") and part.endswith("**") and len(part) > 4
        r = p.add_run(part[2:-2] if strong else part.replace("*", ""))
        r.bold = strong or bold
        if color:
            r.font.color.rgb = rgb(color)


def build_docx(spec: DocumentSpec) -> bytes:
    th, pg = spec.theme, spec.page
    primary = safe_hex(th.primary, "#1f3a5f")
    muted = safe_hex(th.muted, "#6b7685")
    doc = Document()
    sec = doc.sections[0]
    w, h = (210, 297) if pg.size == "A4" else (215.9, 279.4)
    if pg.orientation == "landscape":
        w, h, sec.orientation = h, w, WD_ORIENT.LANDSCAPE
    sec.page_width, sec.page_height = Mm(w), Mm(h)
    margin_mm = min(max(pg.margin_mm, 12), 40)
    sec.left_margin = sec.right_margin = sec.top_margin = sec.bottom_margin = Mm(margin_mm)
    max_w_mm = max(w - 2 * margin_mm, 50)

    normal = doc.styles["Normal"]
    normal.font.name = FONT.get(th.font, "Arial")
    normal.font.size = Pt(th.base_size)
    normal.font.color.rgb = rgb(safe_hex(th.text, "#1c2430"))
    normal.paragraph_format.space_after = Pt(6)
    normal.paragraph_format.line_spacing = th.line_height

    def _add_image_block(b):
        raw = _load_image_bytes(b.url)
        if not raw:
            return
        try:
            p = doc.add_paragraph()
            p.alignment = ALIGN.get(b.align, WD_ALIGN_PARAGRAPH.CENTER)
            target_mm = b.width_mm if b.width_mm and b.width_mm > 0 else (70 if b.align == "center" else 45)
            target_mm = min(target_mm, max_w_mm)
            p.add_run().add_picture(io.BytesIO(raw), width=Mm(target_mm))
            p.paragraph_format.space_after = Pt(4)
            if b.caption:
                cp = doc.add_paragraph()
                cp.alignment = ALIGN.get(b.align, WD_ALIGN_PARAGRAPH.CENTER)
                runs(cp, b.caption, muted)
                cp.paragraph_format.space_after = Pt(6)
        except Exception:
            pass

    leading_images = []
    remaining_blocks = []
    is_leading = True
    for b in spec.blocks:
        if is_leading and b.type == "image":
            leading_images.append(b)
        else:
            is_leading = False
            remaining_blocks.append(b)

    for b in leading_images:
        _add_image_block(b)

    t = doc.add_paragraph(); runs(t, spec.title, primary, True)
    for r in t.runs:
        r.font.size = Pt(th.base_size * 2.4)
    for line, size in ((spec.subtitle, 1.2), (spec.author, 0.9)):
        if line:
            p = doc.add_paragraph(); runs(p, line, muted)
            for r in p.runs:
                r.font.size = Pt(th.base_size * size)

    for b in remaining_blocks:
        if b.type == "image":
            _add_image_block(b)
        elif b.type == "heading":
            lvl = min(max(b.level, 1), 3)
            p = doc.add_paragraph(); runs(p, b.text, primary if lvl < 3 else None, True)
            for r in p.runs:
                r.font.size = Pt(th.base_size * (1.7, 1.35, 1.12)[lvl - 1] * th.heading_scale)
            p.paragraph_format.space_before = Pt(12); p.paragraph_format.keep_with_next = True
        elif b.type in ("paragraph", "quote"):
            p = doc.add_paragraph(); runs(p, b.text)
            p.alignment = ALIGN[b.align]
            if b.type == "quote":
                p.paragraph_format.left_indent = Mm(8)
                for r in p.runs:
                    r.italic = True
        elif b.type in ("bullets", "numbered"):
            for i in b.items:
                runs(doc.add_paragraph(style="List Bullet" if b.type == "bullets" else "List Number"), i)
        elif b.type == "table" and (b.header or b.rows):
            n = max([len(b.header)] + [len(r) for r in b.rows])
            tbl = doc.add_table(rows=0, cols=n); tbl.style = "Table Grid"
            for ri, row in enumerate(([b.header] if b.header else []) + b.rows):
                cells = tbl.add_row().cells
                for ci in range(n):
                    head = bool(b.header) and ri == 0
                    runs(cells[ci].paragraphs[0], row[ci] if ci < len(row) else "", "#FFFFFF" if head else None, head)
                    if head:
                        shade(cells[ci], primary)
            doc.add_paragraph()
        elif b.type == "callout":
            cell = doc.add_table(rows=1, cols=1).rows[0].cells[0]
            shade(cell, tint(TONES[b.tone], 0.12)); runs(cell.paragraphs[0], b.text)
            doc.add_paragraph()
        elif b.type == "divider":
            runs(doc.add_paragraph(), "─" * 40, tint(muted, 0.5))
        elif b.type == "spacer":
            doc.add_paragraph().paragraph_format.space_after = Pt(6 * min(max(b.level, 1), 6))
        elif b.type == "pagebreak":
            doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)

    if th.footer_text:
        sec.footer.paragraphs[0].text = th.footer_text
    if th.header_text:
        sec.header.paragraphs[0].text = th.header_text
    buf = io.BytesIO(); doc.save(buf)
    return buf.getvalue()
