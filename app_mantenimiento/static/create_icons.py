"""Builds the installed app's icons from the Atlas Excellence logo.

Until Nov 2026 icon-192.png and icon-512.png were SVG text with a .png name
(a green "CQ" placeholder from the Communities Qualifier days). Browsers
cannot decode that as PNG, so the installed app and the iPhone home screen
had no real icon. These are real PNGs made from atlas-excellence-icon-logo.png.

The logo is navy and grey, so it sits on white: on navy it would vanish.

    icon-192.png, icon-512.png   manifest, purpose "any"
    icon-maskable-512.png        manifest, purpose "maskable": Android crops
                                 it to a circle or squircle, so the logo stays
                                 inside the central 80% safe zone
    apple-touch-icon.png         180x180, what iOS puts on the home screen;
                                 opaque, because iOS paints transparency black

Run from app_mantenimiento/static:  python3 create_icons.py   (needs Pillow)
"""
from PIL import Image

LOGO = 'atlas-excellence-icon-logo.png'
WHITE = (255, 255, 255, 255)


def icon(size, logo_share, filename):
    """The logo, scaled to logo_share of the side, centred on white."""
    logo = Image.open(LOGO).convert('RGBA')
    logo = logo.crop(logo.getbbox())            # trim its transparent margin
    side = round(size * logo_share)
    scale = side / max(logo.size)
    logo = logo.resize((max(1, round(logo.width * scale)), max(1, round(logo.height * scale))),
                       Image.LANCZOS)
    canvas = Image.new('RGBA', (size, size), WHITE)
    canvas.alpha_composite(logo, ((size - logo.width) // 2, (size - logo.height) // 2))
    canvas.convert('RGB').save(filename, 'PNG', optimize=True)
    print(f'Created {filename} ({size}x{size})')


icon(192, 0.80, 'icon-192.png')
icon(512, 0.80, 'icon-512.png')
# The safe zone is a circle of radius 40% of the side; a logo filling 56% of
# the side has its corners at about 39.6%, just inside it.
icon(512, 0.56, 'icon-maskable-512.png')
icon(180, 0.78, 'apple-touch-icon.png')
