#!/usr/bin/env python3
"""C-PICK 참석·정산 앱 아이콘 생성 (PIL).
네이비 그라데이션 + 흰 카드 + 'C' + 라임 피클볼(체크) — 앱·홈화면용."""
import os
from PIL import Image, ImageDraw, ImageFilter, ImageFont

OUT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
S = 2048
FONT = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"


def lerp(a, b, t):
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


def gradient(size, c0, c1):
    img = Image.new("RGB", (size, size))
    px = img.load()
    for y in range(size):
        for x in range(0, size, 4):
            t = min(1.0, x / size * 0.4 + y / size * 0.6)
            c = lerp(c0, c1, t)
            for dx in range(4):
                if x + dx < size:
                    px[x + dx, y] = c
    return img


def build(size, padding=0.0):
    """padding: maskable 아이콘에서 잘리는 영역을 피하려고 안쪽으로 줄이는 비율"""
    k = size / 1024.0
    img = gradient(size, (18, 51, 95), (29, 75, 134)).convert("RGBA")
    d = ImageDraw.Draw(img)

    inner = 1.0 - padding
    def sc(x, y):
        return (512 + (x - 512) * inner) * k, (512 + (y - 512) * inner) * k

    # 은은한 라임 빛
    glow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    gx, gy = sc(300, 190)
    ImageDraw.Draw(glow).ellipse((gx - 330 * k, gy - 330 * k, gx + 330 * k, gy + 330 * k), fill=(215, 230, 74, 46))
    glow = glow.filter(ImageFilter.GaussianBlur(80 * k))
    img.alpha_composite(glow)

    # 흰 카드
    card = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    cd = ImageDraw.Draw(card)
    x0, y0 = sc(196, 236)
    x1, y1 = sc(828, 800)
    sh = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle((x0 + 10 * k, y0 + 22 * k, x1 + 10 * k, y1 + 22 * k),
                                        radius=int(96 * k), fill=(6, 18, 36, 120))
    card.alpha_composite(sh.filter(ImageFilter.GaussianBlur(26 * k)))
    cd.rounded_rectangle((x0, y0, x1, y1), radius=int(96 * k), fill=(255, 255, 255, 255))
    cd.rounded_rectangle((x0, y0, x1, y1), radius=int(96 * k), outline=(214, 226, 240, 255), width=int(10 * k))

    # 'C'
    font = ImageFont.truetype(FONT, int(330 * k * inner))
    txt = "C"
    bb = cd.textbbox((0, 0), txt, font=font)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    cx, cy = sc(512, 512)
    cd.text((cx - tw / 2 - bb[0], cy - th / 2 - bb[1] - 8 * k), txt, font=font, fill=(18, 51, 95, 255))
    img.alpha_composite(card)

    # 라임 피클볼 + 체크
    ball = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    bd = ImageDraw.Draw(ball)
    bx, by = sc(782, 762)
    r = 208 * k * inner
    bsh = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ImageDraw.Draw(bsh).ellipse((bx - r, by - r + 16 * k, bx + r, by + r + 16 * k), fill=(6, 18, 36, 130))
    ball.alpha_composite(bsh.filter(ImageFilter.GaussianBlur(20 * k)))
    bd.ellipse((bx - r, by - r, bx + r, by + r), fill=(215, 230, 74, 255), outline=(255, 255, 255, 255), width=int(16 * k))
    for hx, hy in [(-0.42, -0.30), (0.10, -0.46), (0.46, 0.02), (-0.34, 0.34), (0.16, 0.40)]:
        rr = 17 * k
        hxp, hyp = bx + hx * r, by + hy * r
        bd.ellipse((hxp - rr, hyp - rr, hxp + rr, hyp + rr), fill=(186, 203, 40, 255))
    # 체크
    bd.line((bx - r * 0.42, by + r * 0.04, bx - r * 0.08, by + r * 0.38, bx + r * 0.46, by - r * 0.32),
            fill=(24, 51, 12, 255), width=int(34 * k), joint="curve")
    img.alpha_composite(ball)
    return img


def main():
    big = build(S)
    variants = {
        "icon-1024.png": (1024, 0.0),
        "icon-512.png": (512, 0.0),
        "icon-192.png": (192, 0.0),
        "icon-maskable-512.png": (512, 0.16),
        "apple-touch-icon.png": (180, 0.06),
    }
    for name, (size, pad) in variants.items():
        im = big if size == S else build(int(S), pad)
        if size != S:
            im = build(S, pad)
        im = im.resize((size, size), Image.LANCZOS)
        if name.startswith("apple-touch"):
            im = im.convert("RGB")
        im.save(os.path.join(OUT, name), optimize=True)
        print("saved", name, size)
    ico = build(S, 0.08).resize((256, 256), Image.LANCZOS)
    ico.save(os.path.join(OUT, "favicon.ico"), sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print("saved favicon.ico")


if __name__ == "__main__":
    main()
