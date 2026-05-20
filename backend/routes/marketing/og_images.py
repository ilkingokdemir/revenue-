"""
OG (Open Graph) image generator for marketing pages.
Renders a 1200×630 PNG that LinkedIn/Twitter/Slack/WhatsApp use for link previews.

Endpoints:
- GET /api/og/compare.png  → Feature-comparison score-card preview
"""
from fastapi import APIRouter, Response
from PIL import Image, ImageDraw, ImageFont
import io
import os


# Score config mirrors the client-side MATRIX in FeatureComparePage.js.
# Keep these in sync whenever the comparison rows change.
SCORES = [
    {"name": "MyHotelBox", "score": 70, "full": 35, "partial": 0, "none": 0, "is_us": True},
    {"name": "Mews",       "score": 50, "full": 18, "partial": 14, "none": 3},
    {"name": "Cloudbeds",  "score": 38, "full": 13, "partial": 12, "none": 10},
    {"name": "Eviivo",     "score": 23, "full": 6,  "partial": 11, "none": 18},
]

# Pick the heaviest available font — falls back gracefully.
_FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]
_FONT_REGULAR = [
    "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]


def _font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont:
    candidates = _FONT_CANDIDATES if bold else _FONT_REGULAR
    for p in candidates:
        if os.path.exists(p):
            return ImageFont.truetype(p, size=size)
    return ImageFont.load_default()


def _render_compare_og() -> bytes:
    W, H = 1200, 630
    BG = (10, 10, 15)
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img, "RGBA")

    # Radial-glow-ish stack (stacked alpha blobs approximate the page aesthetic)
    for cx, cy, r, rgba in [
        (340, 120, 380, (217, 70, 239, 70)),   # fuchsia
        (860, 220, 340, (99, 102, 241, 55)),   # indigo
    ]:
        for i in range(40, 0, -2):
            alpha = int(rgba[3] * (i / 40))
            d.ellipse([cx - r * i / 40, cy - r * i / 40, cx + r * i / 40, cy + r * i / 40],
                      fill=(rgba[0], rgba[1], rgba[2], alpha // 8))

    # Subtle grid
    grid_rgba = (255, 255, 255, 6)
    for x in range(0, W, 40):
        d.line([(x, 0), (x, H)], fill=grid_rgba)
    for y in range(0, H, 40):
        d.line([(0, y), (W, y)], fill=grid_rgba)

    # Kicker
    d.text((70, 70), "INDEPENDENT FEATURE AUDIT · Q2 2026",
           font=_font(18), fill=(217, 70, 239, 255))

    # Big headline
    d.text((70, 110), "Feature scorecard", font=_font(64), fill=(245, 245, 244))
    d.text((70, 190), "vs the top PMS platforms.", font=_font(48), fill=(168, 162, 158))

    # Cards
    card_top = 315
    card_h = 220
    card_w = 240
    gap = 30
    total_w = len(SCORES) * card_w + (len(SCORES) - 1) * gap
    start_x = (W - total_w) // 2

    for i, s in enumerate(SCORES):
        x = start_x + i * (card_w + gap)
        y = card_top
        # Card body
        is_us = s.get("is_us")
        fill = (30, 15, 40) if is_us else (20, 20, 28)
        outline = (217, 70, 239, 180) if is_us else (255, 255, 255, 24)
        # rounded rect
        d.rounded_rectangle([x, y, x + card_w, y + card_h], radius=22,
                            fill=fill, outline=outline[:3], width=2)
        # Leader pill
        if is_us:
            pill_w, pill_h = 100, 24
            px, py = x + 18, y - 12
            d.rounded_rectangle([px, py, px + pill_w, py + pill_h], radius=12,
                                fill=(217, 70, 239, 255))
            d.text((px + 14, py + 3), "LEADER", font=_font(13), fill=(255, 255, 255))

        # Name
        d.text((x + 22, y + 28), s["name"].upper(),
               font=_font(18), fill=(168, 162, 158))
        # Score (massive)
        score_font = _font(100)
        score_color = (244, 114, 182) if is_us else (231, 229, 228)
        d.text((x + 22, y + 54), str(s["score"]), font=score_font, fill=score_color)

        # Breakdown
        bd = f"{s['full']} full   {s['partial']} partial   {s['none']} none"
        d.text((x + 22, y + 172), bd, font=_font(15, bold=False), fill=(168, 162, 158))

    # Footer
    d.text((70, H - 70), "Score = 2×full + 1×partial · 0×none · myhotelbox.com/compare",
           font=_font(17, bold=False), fill=(120, 113, 108))

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def create_og_router():
    router = APIRouter(prefix="/og")

    @router.get("/compare.png")
    async def compare_og():
        """Public OG image for /compare. No auth — served to LinkedIn/Twitter crawlers."""
        data = _render_compare_og()
        return Response(
            content=data,
            media_type="image/png",
            headers={
                "Cache-Control": "public, max-age=3600",
            },
        )

    return router
