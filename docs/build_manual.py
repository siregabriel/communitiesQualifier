#!/usr/bin/env python3
"""
Build the Atlas Excellence manual as a PDF.

    python3 docs/build_manual.py [output.pdf]

The wording lives in manual_content.py; this file is only layout. Re-run it
after editing the content — the PDF is generated, never hand-edited, so it can
always be rebuilt from the text.
"""
import os
import sys
from datetime import date

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (BaseDocTemplate, Frame, KeepTogether, ListFlowable,
                                ListItem, NextPageTemplate, PageBreak, PageTemplate,
                                Paragraph, Spacer, Table, TableStyle)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from manual_content import COVER, PRODUCT, SECTIONS, VERSION  # noqa: E402

NAVY = colors.HexColor('#00285c')
AZURE = colors.HexColor('#1f6fe5')
INK = colors.HexColor('#0f1e36')
MUTED = colors.HexColor('#64748b')
LINE = colors.HexColor('#d9dfe8')
WASH = colors.HexColor('#f5f8fc')
AMBER_BG = colors.HexColor('#fdf6e3')
AMBER_EDGE = colors.HexColor('#d99a0b')

STAMP = date.today().strftime('%B %Y')


def styles():
    s = getSampleStyleSheet()
    base = dict(fontName='Helvetica', textColor=INK, leading=15.5)
    return {
        'title': ParagraphStyle('t', **{**base, 'fontName': 'Helvetica-Bold',
                                        'fontSize': 34, 'leading': 40,
                                        'textColor': NAVY, 'alignment': TA_CENTER}),
        'subtitle': ParagraphStyle('st', **{**base, 'fontSize': 14, 'leading': 20,
                                            'textColor': MUTED, 'alignment': TA_CENTER}),
        'blurb': ParagraphStyle('bl', **{**base, 'fontSize': 11, 'leading': 16,
                                         'textColor': MUTED, 'alignment': TA_CENTER}),
        'h1': ParagraphStyle('h1', **{**base, 'fontName': 'Helvetica-Bold',
                                      'fontSize': 21, 'leading': 26,
                                      'textColor': NAVY, 'spaceAfter': 4}),
        'h2': ParagraphStyle('h2', **{**base, 'fontName': 'Helvetica-Bold',
                                      'fontSize': 13.5, 'leading': 18,
                                      'textColor': AZURE,
                                      'spaceBefore': 14, 'spaceAfter': 4}),
        'p': ParagraphStyle('p', **{**base, 'fontSize': 10.5, 'spaceAfter': 9}),
        'li': ParagraphStyle('li', **{**base, 'fontSize': 10.5, 'spaceAfter': 5}),
        'note': ParagraphStyle('n', **{**base, 'fontSize': 10, 'leading': 14.5,
                                       'textColor': colors.HexColor('#6b5a2e')}),
        'th': ParagraphStyle('th', **{**base, 'fontName': 'Helvetica-Bold',
                                      'fontSize': 9.5, 'leading': 13,
                                      'textColor': colors.white}),
        'td': ParagraphStyle('td', **{**base, 'fontSize': 9.5, 'leading': 13}),
        'tdb': ParagraphStyle('tdb', **{**base, 'fontName': 'Helvetica-Bold',
                                        'fontSize': 9.5, 'leading': 13,
                                        'textColor': NAVY}),
    }


S = styles()


def chrome(canvas, doc):
    """Footer on every page but the cover."""
    canvas.saveState()
    canvas.setStrokeColor(LINE)
    canvas.setLineWidth(0.6)
    canvas.line(inch, 0.72 * inch, LETTER[0] - inch, 0.72 * inch)
    canvas.setFont('Helvetica', 8)
    canvas.setFillColor(MUTED)
    canvas.drawString(inch, 0.54 * inch, f'{PRODUCT} · {STAMP}')
    canvas.drawRightString(LETTER[0] - inch, 0.54 * inch, str(canvas.getPageNumber() - 1))
    canvas.restoreState()


def cover_art(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(NAVY)
    canvas.rect(0, LETTER[1] - 2.1 * inch, LETTER[0], 2.1 * inch, stroke=0, fill=1)
    canvas.setFillColor(AZURE)
    canvas.rect(0, LETTER[1] - 2.22 * inch, LETTER[0], 0.12 * inch, stroke=0, fill=1)
    canvas.setFont('Helvetica', 9)
    canvas.setFillColor(MUTED)
    canvas.drawCentredString(LETTER[0] / 2, 0.8 * inch,
                             f'Version {VERSION} · {STAMP} · Atlas Senior Living')
    canvas.restoreState()


def table(rows):
    """First row is the header. First column is emphasised when there are 3+."""
    wide = len(rows[0]) >= 3
    body = []
    for i, row in enumerate(rows):
        if i == 0:
            body.append([Paragraph(c, S['th']) for c in row])
        else:
            body.append([Paragraph(c, S['tdb'] if (j == 0 and wide) else S['td'])
                         for j, c in enumerate(row)])

    avail = LETTER[0] - 2 * inch
    n = len(rows[0])
    if n == 2:
        widths = [avail * 0.34, avail * 0.66]
    elif n == 3:
        widths = [avail * 0.22, avail * 0.42, avail * 0.36]
    else:
        widths = [avail * 0.28] + [avail * 0.72 / (n - 1)] * (n - 1)

    t = Table(body, colWidths=widths, repeatRows=1, hAlign='LEFT')
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), NAVY),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 7),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
        ('LEFTPADDING', (0, 0), (-1, -1), 9),
        ('RIGHTPADDING', (0, 0), (-1, -1), 9),
        ('LINEBELOW', (0, 0), (-1, -2), 0.5, LINE),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, WASH]),
        ('BOX', (0, 0), (-1, -1), 0.6, LINE),
    ]))
    return t


def note(text):
    t = Table([[Paragraph(text, S['note'])]],
              colWidths=[LETTER[0] - 2 * inch], hAlign='LEFT')
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), AMBER_BG),
        ('LINEBEFORE', (0, 0), (0, -1), 3, AMBER_EDGE),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ('LEFTPADDING', (0, 0), (-1, -1), 13),
        ('RIGHTPADDING', (0, 0), (-1, -1), 13),
    ]))
    return t


def listing(items, numbered):
    return ListFlowable(
        [ListItem(Paragraph(i, S['li']), leftIndent=18) for i in items],
        bulletType='1' if numbered else 'bullet',
        bulletFontName='Helvetica', bulletFontSize=9.5,
        bulletColor=AZURE if not numbered else INK,
        leftIndent=16, spaceAfter=9,
    )


def rule():
    t = Table([['']], colWidths=[1.6 * inch], rowHeights=[3], hAlign='LEFT')
    t.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), AZURE)]))
    return t


def build(out_path):
    doc = BaseDocTemplate(
        out_path, pagesize=LETTER,
        leftMargin=inch, rightMargin=inch, topMargin=inch, bottomMargin=inch,
        title=f'{PRODUCT} — User Guide', author='Atlas Senior Living',
        subject='How to run visits, follow them through, and administer the app',
    )
    frame = Frame(inch, inch, LETTER[0] - 2 * inch, LETTER[1] - 2 * inch, id='body')
    doc.addPageTemplates([
        PageTemplate(id='cover', frames=[frame], onPage=cover_art),
        PageTemplate(id='body', frames=[frame], onPage=chrome),
    ])

    story = [
        Spacer(1, 1.5 * inch),
        Paragraph(COVER['title'], S['title']),
        Spacer(1, 10),
        Paragraph(COVER['subtitle'], S['subtitle']),
        Spacer(1, 26),
        Paragraph(COVER['blurb'], S['blurb']),
        NextPageTemplate('body'),
        PageBreak(),
    ]

    for kind, value in SECTIONS:
        if kind == 'h1':
            if len(story) > 8:
                story.append(PageBreak())
            story += [Paragraph(value, S['h1']), Spacer(1, 5), rule(), Spacer(1, 14)]
        elif kind == 'h2':
            story.append(Paragraph(value, S['h2']))
        elif kind == 'p':
            story.append(Paragraph(value, S['p']))
        elif kind == 'bullets':
            story.append(listing(value, numbered=False))
        elif kind == 'steps':
            story.append(listing(value, numbered=True))
        elif kind == 'table':
            story += [Spacer(1, 3), table(value), Spacer(1, 13)]
        elif kind == 'note':
            story += [Spacer(1, 3), KeepTogether(note(value)), Spacer(1, 13)]
        elif kind == 'spacer':
            story.append(Spacer(1, value))

    doc.build(story)
    return out_path


if __name__ == '__main__':
    target = sys.argv[1] if len(sys.argv) > 1 else 'Atlas-Excellence-User-Guide.pdf'
    path = build(target)
    size = os.path.getsize(path)
    print(f'Built {path} ({size:,} bytes)')
