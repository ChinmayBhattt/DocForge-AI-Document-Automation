import base64
import io
import os
import re

from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4, LETTER, landscape, portrait
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (HRFlowable, Image as RLImage, KeepTogether, ListFlowable, ListItem, PageBreak,
                                Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle)

from models import DocumentSpec, safe_hex, tint

FONTS = {
    "Helvetica": ("Helvetica", "Helvetica-Bold", "Helvetica-Oblique"),
    "Times": ("Times-Roman", "Times-Bold", "Times-Italic"),
    "Courier": ("Courier", "Courier-Bold", "Courier-Oblique"),
}
ALIGN = {"left": TA_LEFT, "center": TA_CENTER, "right": TA_RIGHT, "justify": TA_JUSTIFY}
TONES = {"info": "#2f6fed", "success": "#1f8a4c", "warning": "#c77d0a", "danger": "#c0392b"}


def _register_noto() -> None:
    """Drop NotoSans-Regular/Bold/Italic.ttf into backend/fonts for full Unicode (e.g. the rupee sign)."""
    d = os.path.join(os.path.dirname(__file__), "fonts")
    files = {k: os.path.join(d, f"NotoSans-{k}.ttf") for k in ("Regular", "Bold", "Italic")}
    if all(os.path.exists(p) for p in files.values()):
        for k, p in files.items():
            pdfmetrics.registerFont(TTFont(f"NotoSans-{k}", p))
        pdfmetrics.registerFontFamily("NotoSans", normal="NotoSans-Regular", bold="NotoSans-Bold",
                                      italic="NotoSans-Italic", boldItalic="NotoSans-Bold")
        FONTS["NotoSans"] = ("NotoSans-Regular", "NotoSans-Bold", "NotoSans-Italic")


_register_noto()


def fmt(t: str) -> str:
    t = t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<i>\1</i>", t)
    return t.replace("\n", "<br/>")


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


def build_pdf(spec: DocumentSpec) -> bytes:
    th, pg = spec.theme, spec.page
    reg, bold, ital = FONTS.get(th.font, FONTS["Helvetica"])
    primary, accent = safe_hex(th.primary, "#1f3a5f"), safe_hex(th.accent, "#2f6fed")
    text_c, muted = safe_hex(th.text, "#1c2430"), safe_hex(th.muted, "#6b7685")
    border_c = safe_hex(th.border_color, primary)
    C = colors.HexColor

    base = min(max(th.base_size, 8), 14)
    lead = base * min(max(th.line_height, 1.2), 1.8)
    scale = min(max(th.heading_scale, 0.8), 1.4)
    margin = min(max(pg.margin_mm, 12), 40) * mm
    size = A4 if pg.size == "A4" else LETTER
    size = landscape(size) if pg.orientation == "landscape" else portrait(size)
    avail = size[0] - 2 * margin

    body = ParagraphStyle("body", fontName=reg, fontSize=base, leading=lead, textColor=C(text_c),
                          spaceAfter=base * 0.75)
    styles = {a: ParagraphStyle(f"b-{a}", parent=body, alignment=v) for a, v in ALIGN.items()}
    heads = {
        n: ParagraphStyle(f"h{n}", parent=body, fontName=bold, fontSize=base * s * scale,
                          leading=base * s * scale * 1.2, textColor=C(primary if n < 3 else text_c),
                          spaceBefore=base * (1.4 if n == 1 else 1.0), spaceAfter=base * 0.5, keepWithNext=1)
        for n, s in ((1, 1.7), (2, 1.35), (3, 1.12))
    }

    def _make_image_flowable(b):
        raw = _load_image_bytes(b.url)
        if not raw:
            return None
        try:
            pil_im = PILImage.open(io.BytesIO(raw))
            orig_w, orig_h = pil_im.size
            if orig_w == 0 or orig_h == 0:
                return None
            aspect = orig_h / orig_w
            if b.width_mm and b.width_mm > 0:
                target_w = min(b.width_mm * mm, avail)
            else:
                target_w = min((70 if b.align == "center" else 45) * mm, avail)
            target_h = target_w * aspect
            max_h = (size[1] - 2 * margin) * 0.6
            if target_h > max_h:
                target_h = max_h
                target_w = target_h / aspect
            rl_img = RLImage(io.BytesIO(raw), width=target_w, height=target_h)
            rl_img.hAlign = {"left": "LEFT", "center": "CENTER", "right": "RIGHT"}.get(b.align, "CENTER")
            elements = [rl_img]
            if b.caption:
                cap_style = ParagraphStyle("cap", parent=body, fontSize=base * 0.85,
                                           textColor=C(muted), alignment=ALIGN.get(b.align, TA_CENTER),
                                           spaceBefore=3, spaceAfter=base * 0.4)
                elements.append(Paragraph(fmt(b.caption), cap_style))
            else:
                elements.append(Spacer(1, base * 0.5))
            return KeepTogether(elements)
        except Exception:
            return None

    leading_images = []
    remaining_blocks = []
    is_leading = True
    for b in spec.blocks:
        if is_leading and b.type == "image":
            leading_images.append(b)
        else:
            is_leading = False
            remaining_blocks.append(b)

    story = []
    for b in leading_images:
        flow = _make_image_flowable(b)
        if flow:
            story.append(flow)

    story.append(Paragraph(fmt(spec.title), ParagraphStyle(
        "title", parent=body, fontName=bold, fontSize=base * 2.5 * scale, leading=base * 2.9 * scale,
        textColor=C(primary), spaceAfter=base * 0.4)))
    if spec.subtitle:
        story.append(Paragraph(fmt(spec.subtitle), ParagraphStyle(
            "sub", parent=body, fontSize=base * 1.2, leading=base * 1.6, textColor=C(muted))))
    if spec.author:
        story.append(Paragraph(fmt(spec.author), ParagraphStyle("by", parent=body, fontSize=base * 0.9, textColor=C(muted))))
    story.append(HRFlowable(width="100%", thickness=2, color=C(accent), spaceBefore=4, spaceAfter=base * 1.2))

    def boxed(flow, bg=None, line=None):
        t = Table([[flow]], colWidths=[avail])
        cmds = [("LEFTPADDING", (0, 0), (-1, -1), 12), ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                ("TOPPADDING", (0, 0), (-1, -1), 9), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]
        if bg:
            cmds.append(("BACKGROUND", (0, 0), (-1, -1), C(bg)))
        if line:
            cmds.append(("LINEBEFORE", (0, 0), (0, -1), 3, C(line)))
        t.setStyle(TableStyle(cmds))
        return [t, Spacer(1, base * 0.8)]

    for b in remaining_blocks:
        st = styles[b.align]
        if b.type == "image":
            flow = _make_image_flowable(b)
            if flow:
                story.append(flow)
        elif b.type == "heading":
            lvl = min(max(b.level, 1), 3)
            h = Paragraph(fmt(b.text), heads[lvl])
            story.append(KeepTogether([h, HRFlowable(width="100%", thickness=0.6, color=C(tint(primary, 0.35)),
                                                     spaceAfter=base * 0.5)]) if lvl == 1 else h)
        elif b.type == "paragraph":
            story.append(Paragraph(fmt(b.text), st))
        elif b.type in ("bullets", "numbered"):
            items = [ListItem(Paragraph(fmt(i), ParagraphStyle("li", parent=st, spaceAfter=base * 0.25))) for i in b.items]
            kw = dict(bulletType="bullet", start="•") if b.type == "bullets" else dict(bulletType="1", bulletFormat="%s.")
            story += [ListFlowable(items, leftIndent=16, bulletFontName=bold if b.type == "numbered" else reg,
                                   bulletColor=C(accent), bulletFontSize=base, **kw), Spacer(1, base * 0.7)]
        elif b.type == "table" and (b.header or b.rows):
            ncols = max([len(b.header)] + [len(r) for r in b.rows])
            pad = lambda r: (list(r) + [""] * ncols)[:ncols]
            cell = ParagraphStyle("cell", parent=body, fontSize=base * 0.92, leading=base * 1.25, spaceAfter=0)
            hcell = ParagraphStyle("hcell", parent=cell, fontName=bold, textColor=colors.white)
            data = ([[Paragraph(fmt(c), hcell) for c in pad(b.header)]] if b.header else []) + \
                   [[Paragraph(fmt(c), cell) for c in pad(r)] for r in b.rows]
            allrows = ([pad(b.header)] if b.header else []) + [pad(r) for r in b.rows]
            w = [min(max(max(len(r[i]) for r in allrows), 6), 40) for i in range(ncols)]
            t = Table(data, colWidths=[avail * x / sum(w) for x in w], repeatRows=1 if b.header else 0)
            cmds = [("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6), ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("LINEBELOW", (0, 0), (-1, -1), 0.4, C(tint(primary, 0.25)))]
            if b.header:
                cmds.append(("BACKGROUND", (0, 0), (-1, 0), C(primary)))
            start = 1 if b.header else 0
            cmds += [("BACKGROUND", (0, i), (-1, i), C(tint(primary, 0.07))) for i in range(start + 1, len(data), 2)]
            t.setStyle(TableStyle(cmds))
            story += [t, Spacer(1, base * 1.0)]
        elif b.type == "callout":
            tone = TONES[b.tone]
            story += boxed(Paragraph(fmt(b.text), st), bg=tint(tone, 0.1), line=tone)
        elif b.type == "quote":
            q = ParagraphStyle("q", parent=st, fontName=ital, fontSize=base * 1.1, textColor=C(muted))
            story += boxed(Paragraph(fmt(b.text), q), line=accent)
        elif b.type == "divider":
            story.append(HRFlowable(width="100%", thickness=0.6, color=C(tint(muted, 0.5)), spaceBefore=base * 0.5,
                                    spaceAfter=base * 0.9))
        elif b.type == "spacer":
            story.append(Spacer(1, base * 0.8 * min(max(b.level, 1), 6)))
        elif b.type == "pagebreak":
            story.append(PageBreak())

    def decorate(c, doc):
        w, h = doc.pagesize
        c.saveState()
        if th.border:
            inset = margin * 0.35
            c.setStrokeColor(C(border_c))
            c.setLineWidth(min(max(th.border_width, 0.25), 4))
            c.rect(inset, inset, w - 2 * inset, h - 2 * inset)
        c.setFont(reg, 8)
        c.setFillColor(C(muted))
        if th.header_text:
            c.drawString(margin, h - margin * 0.6, th.header_text)
        if th.footer_text:
            c.drawString(margin, margin * 0.55, th.footer_text)
        if th.page_numbers:
            c.drawRightString(w - margin, margin * 0.55, f"Page {doc.page}")
        c.restoreState()

    buf = io.BytesIO()
    SimpleDocTemplate(buf, pagesize=size, leftMargin=margin, rightMargin=margin, topMargin=margin,
                      bottomMargin=margin, title=spec.title, author=spec.author or "DocForge").build(
        story, onFirstPage=decorate, onLaterPages=decorate)
    return buf.getvalue()
