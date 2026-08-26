"""
Photo Stamp Service

Adds a caption strip to a photo on its way out of Atlas Excellence, so that a
picture pasted into an email still says which community it belongs to, when it
was taken, and who took it.

Two decisions worth keeping:

  * The strip is *appended below* the photo, never drawn on top of it. These are
    photos of defects — a handrail, a stain, a cracked tile — and an overlay
    would sit exactly where the evidence is. A taller image is a cheap price for
    never hiding the thing being documented.

  * Nothing here touches stored bytes. The original in S3 is the record; this
    runs on a copy at download time. After the filename collision that lost
    three of Marissa's photos for good, with bucket versioning still off, no
    irreversible transform belongs anywhere near the upload path.
"""

import io
import logging
import os

logger = logging.getLogger(__name__)

# Ubuntu ships DejaVu with fonts-dejavu-core; reportlab pulls Pillow in, but
# neither guarantees a TrueType file exists. Checked in order, first hit wins.
_FONT_CANDIDATES = (
    '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
    '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
    '/usr/share/fonts/dejavu/DejaVuSans.ttf',
    '/Library/Fonts/Arial.ttf',
    '/System/Library/Fonts/Supplemental/Arial.ttf',
)

_BAR_BG = (17, 24, 39)        # near-black, so it reads as a label and not as photo
_BAR_FG = (255, 255, 255)
_BAR_DIM = (167, 178, 195)

# The wordmark is navy on transparent, which would vanish against the strip.
# Its own alpha channel is the shape, so painting that shape white gives a
# clean reversed mark without needing a second logo file to keep in step.
_LOGO_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          '..', 'static', 'arlas-excellence-logo.png')
_logo_cache = {}


def _white_logo():
    """The wordmark in white, loaded once. None if the file isn't there."""
    if 'mark' in _logo_cache:
        return _logo_cache['mark']
    mark = None
    try:
        from PIL import Image
        src = Image.open(_LOGO_FILE).convert('RGBA')
        alpha = src.getchannel('A')
        mark = Image.new('RGBA', src.size, (255, 255, 255, 0))
        mark.putalpha(alpha)
    except Exception as e:
        logger.warning(f'No logo for the photo strip ({e}); captioning without it')
    _logo_cache['mark'] = mark
    return mark


def _load_font(size):
    """A font at the requested size, degrading rather than failing."""
    from PIL import ImageFont
    for path in _FONT_CANDIDATES:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    # No TrueType on the box. The bitmap default is small and ugly, but a
    # readable-ish stamp beats a download that 500s.
    try:
        return ImageFont.load_default(size=size)   # Pillow >= 10.1
    except TypeError:
        return ImageFont.load_default()


def _text_width(draw, text, font):
    try:
        box = draw.textbbox((0, 0), text, font=font)
        return box[2] - box[0]
    except Exception:
        return len(text) * max(6, getattr(font, 'size', 12) // 2)


def _fit(draw, text, font_for, max_width, start, floor=10):
    """Largest size at or below `start` that keeps `text` inside `max_width`."""
    size = start
    while size > floor:
        font = font_for(size)
        if _text_width(draw, text, font) <= max_width:
            return font
        size -= 1
    return font_for(floor)


def _elide(draw, text, font, max_width):
    """Trim `text` until it fits, ending in an ellipsis.

    Shrinking the type has a floor, and past it a long community name simply
    ran on under the logo. Cutting it is the honest failure: the reader can see
    something was trimmed, rather than reading a name that overlaps a mark.
    """
    if not text or _text_width(draw, text, font) <= max_width:
        return text
    cut = text
    while cut and _text_width(draw, cut + '…', font) > max_width:
        cut = cut[:-1]
    return (cut.rstrip() + '…') if cut.strip() else ''


def stamp(image_bytes, primary, secondary=''):
    """Return `image_bytes` with a caption strip appended underneath.

    primary   -- the community, carried large; the thing you need at a glance
    secondary -- date and who took it, carried smaller underneath

    Returns (bytes, extension). On any failure the original bytes come back
    unchanged: a photo without its caption is a smaller problem than a photo
    the person cannot download at all.
    """
    try:
        from PIL import Image, ImageDraw, ImageOps

        img = Image.open(io.BytesIO(image_bytes))
        # Phone photos carry their rotation in EXIF rather than in the pixels.
        # Re-encoding without applying it hands the person a sideways picture.
        img = ImageOps.exif_transpose(img)
        if img.mode not in ('RGB', 'L'):
            img = img.convert('RGB')
        elif img.mode == 'L':
            img = img.convert('RGB')

        w, h = img.size
        if w < 80:                       # too small to caption legibly
            return image_bytes, _ext_of(img)

        # Scale with the image so the strip looks the same on a phone photo and
        # on a downscaled one, with limits so it never dominates a small image.
        pad = max(8, round(w * 0.022))
        big = min(max(13, round(w * 0.034)), 46)
        small = max(11, round(big * 0.72))

        scratch = ImageDraw.Draw(img)

        # Work out the strip height from the text first, then let the logo be
        # sized to fit inside it — the caption is the point, the mark is not.
        probe_big = _load_font(big)
        line_h = getattr(probe_big, 'size', big)
        sub_h = small if secondary else 0
        bar = pad + line_h + (round(pad * 0.45) + sub_h if secondary else 0) + pad

        logo, logo_box = _white_logo(), (0, 0)
        if logo is not None:
            lh = max(1, bar - round(pad * 1.6))
            lw = max(1, round(logo.width * lh / logo.height))
            # A mark wider than a third of the photo stops being a signature
            # and starts competing with the caption.
            if lw > w // 3:
                lw = w // 3
                lh = max(1, round(logo.height * lw / logo.width))
            if lw >= 40:
                logo = logo.resize((lw, lh), Image.LANCZOS)
                logo_box = (lw, lh)
            else:
                logo = None            # too small to read; better left off

        gap = pad if logo is not None else 0
        avail = w - pad * 2 - logo_box[0] - gap
        if avail < w * 0.35:           # the caption must not be squeezed out
            logo, logo_box, gap = None, (0, 0), 0
            avail = w - pad * 2

        f_big = _fit(scratch, primary, lambda s: _load_font(s), avail, big)
        f_small = _fit(scratch, secondary, lambda s: _load_font(s), avail, small) \
            if secondary else None

        out = Image.new('RGB', (w, h + bar), _BAR_BG)
        out.paste(img, (0, 0))
        draw = ImageDraw.Draw(out)

        y = h + pad
        draw.text((pad, y), _elide(draw, primary, f_big, avail),
                  font=f_big, fill=_BAR_FG)
        if f_small:
            draw.text((pad, y + line_h + round(pad * 0.45)),
                      _elide(draw, secondary, f_small, avail),
                      font=f_small, fill=_BAR_DIM)

        if logo is not None:
            out.paste(logo,
                      (w - pad - logo_box[0], h + (bar - logo_box[1]) // 2),
                      logo)

        buf = io.BytesIO()
        out.save(buf, format='JPEG', quality=88, optimize=True)
        return buf.getvalue(), 'jpg'
    except Exception as e:
        logger.error(f'Could not stamp photo, serving it unstamped: {e}')
        return image_bytes, ''


def _ext_of(img):
    fmt = (getattr(img, 'format', '') or '').lower()
    return {'jpeg': 'jpg'}.get(fmt, fmt or '')
