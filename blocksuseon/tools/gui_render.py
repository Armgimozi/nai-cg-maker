#!/usr/bin/env python3
"""GUI 스냅숏 JSON(tools/gui_snapshot.luau)을 PNG 로 그린다. Roblox 없이 화면 배치를 눈으로 본다.

    lune run tools/gui_snapshot status 1920 1080 && python3 tools/gui_render.py build/gui_status.json build/gui_status.png
    python3 tools/gui_render.py build/gui_status.json build/gui_status_small.png --scale 0.5
    python3 tools/gui_render.py build/gui_status.json build/over.png --bg shot.png --size 2000x1125

인자: <입력.json> [출력.png] (출력을 빼면 입력 이름의 .png)
  --scale F         다 그린 뒤 F 배로 줄이거나 키운다 (예: 2560×1440 을 2000×1125 로 0.78125)
  --size WxH        다 그린 뒤 이 크기로 (--scale 대신)
  --bg <그림>        바탕에 그림을 깐다 (게임 스크린숏 위에 겹쳐 보기). 기본은 옅은 하늘·풀빛과 바둑판
  --bg-alpha F      --bg 그림 위에 GUI 를 얼마나 진하게 (기본 1)
  --missing a.png,b.png  이 art/out 그림은 없는 셈 친다 (Roblox 검수 중인 글자판 흉내)
  --boxes           GuiObject 마다 얇은 테두리 (배치 확인용), --boxes-name 이름 은 그 이름만 붉게
  --no-core         Roblox 기본 UI 자리(위쪽 막대, 도구 칸, 점프)를 그리지 않는다
  --font <ttf>      Roblox 글꼴(TextLabel) 대신 쓸 글꼴. 기본은 시스템 한글 고딕(Noto CJK, 나눔고딕, 문천역정흑)
                    다음 art/fonts 의 나눔명조 조각, 없으면 PIL 기본 글꼴
  --report          배치 검사를 찍는다: 글끼리 겹침, 글이 버튼에 가림, 글이 창 밖으로 나감,
                    창이 화면(위쪽 막대 아래) 밖으로 나감, ClipsDescendants 에 잘린 글 (스크롤 목록 끝은 빼고)

그리는 것: 배경색·테두리(BorderSizePixel, UICorner 면 둥글게, UIStroke), 그림(Stretch, Slice 9 조각과 SliceScale,
Fit, Crop, Tile, ImageRectOffset/Size, ImageColor3 곱하기, ImageTransparency), 글자판 글자(같은 그림 자르기 +
색 곱하기, UIGradient 는 위→아래 따위 방향으로 색·투명도를 곱해 어림), TextLabel 글자(정렬, 줄바꿈, 테두리),
ScrollingFrame 스크롤 막대, ClipsDescendants·ScrollingFrame 자르기, 투명도, 그리는 차례(order).
Rotation 은 그 물체만 돌린다 (자손은 돌리지 않는다).
"""

from __future__ import annotations

import argparse
import functools
import glob
import json
import math
import os
import sys

from PIL import Image, ImageChops, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# 그림 ------------------------------------------------------------------------------


class Assets:
    def __init__(self, snapshot: dict, missing: set[str]):
        self.map: dict[str, str] = dict(snapshot.get("assets") or {})
        uploaded = os.path.join(ROOT, "art", "uploaded.json")
        if os.path.exists(uploaded):
            for file, info in json.load(open(uploaded, encoding="utf-8")).items():
                self.map.setdefault(f"rbxassetid://{info['assetId']}", f"art/out/{file}")
        self.missing = missing
        self.cache: dict[str, Image.Image | None] = {}
        self.unknown: set[str] = set()

    def get(self, image: dict) -> Image.Image | None:
        path = image.get("file") or self.map.get(image.get("id", ""))
        if not path:
            self.unknown.add(image.get("id", "?"))
            return None
        if os.path.basename(path) in self.missing:
            return None
        if path not in self.cache:
            full = path if os.path.isabs(path) else os.path.join(ROOT, path)
            self.cache[path] = Image.open(full).convert("RGBA") if os.path.exists(full) else None
            if self.cache[path] is None:
                self.unknown.add(path)
        return self.cache[path]


# 글꼴 ------------------------------------------------------------------------------

SYSTEM_FONTS = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansKR-Regular.ttf",
    "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]


class Fonts:
    """Roblox 글꼴 대신: 한글 되는 고딕 하나 + 글자가 없으면 art/fonts 조각들 차례로."""

    def __init__(self, override: str | None):
        paths = [override] if override else []
        paths += [p for p in SYSTEM_FONTS if os.path.exists(p)]
        paths += sorted(glob.glob(os.path.join(ROOT, "art", "fonts", "body_*.woff2")))
        self.paths = []
        for path in paths:
            try:
                ImageFont.truetype(path, 12)
                self.paths.append(path)
            except Exception:
                pass

    @functools.lru_cache(maxsize=256)
    def font(self, index: int, size: int):
        if index >= len(self.paths):
            return ImageFont.load_default()
        return ImageFont.truetype(self.paths[index], max(1, size))

    @functools.lru_cache(maxsize=4096)
    def has(self, index: int, ch: str) -> bool:
        if ch.isspace():
            return True
        font = self.font(index, 24)
        try:
            mask = font.getmask(ch)
            notdef = font.getmask("")
        except Exception:
            return False
        if mask.getbbox() is None:
            return False
        return bytes(mask) != bytes(notdef) or mask.size != notdef.size

    def pick(self, ch: str, size: int):
        for index in range(len(self.paths)):
            if self.has(index, ch):
                return self.font(index, size)
        return self.font(len(self.paths), size)

    def width(self, text: str, size: int) -> float:
        return sum(self.pick(ch, size).getlength(ch) for ch in text)


# 그리기 도우미 ---------------------------------------------------------------------


def rgba(color, alpha: float = 1.0):
    return (int(color[0]), int(color[1]), int(color[2]), max(0, min(255, int(round(alpha * 255)))))


def multiply_alpha(img: Image.Image, factor: float) -> Image.Image:
    if factor >= 0.999:
        return img
    r, g, b, a = img.split()
    a = a.point(lambda v: int(v * max(0.0, factor)))
    return Image.merge("RGBA", (r, g, b, a))


def tint(img: Image.Image, color) -> Image.Image:
    if tuple(color[:3]) == (255, 255, 255):
        return img
    r, g, b, a = img.split()
    solid = Image.new("RGB", img.size, tuple(int(c) for c in color[:3]))
    rgb = ImageChops.multiply(Image.merge("RGB", (r, g, b)), solid)
    return Image.merge("RGBA", (*rgb.split(), a))


def sample(seq, t: float, channels: int):
    """ColorSequence/NumberSequence 의 t 자리 값 (선형 보간). seq: [[시간, 값...], ...]"""
    if not seq:
        return [255] * channels
    if t <= seq[0][0]:
        return seq[0][1:]
    for a, b in zip(seq, seq[1:]):
        if a[0] <= t <= b[0]:
            span = max(b[0] - a[0], 1e-6)
            k = (t - a[0]) / span
            return [a[i] + (b[i] - a[i]) * k for i in range(1, channels + 1)]
    return seq[-1][1:]


def gradient_layers(size, gradient: dict):
    """UIGradient: 색(곱하기)과 투명도. Rotation 0 은 왼쪽→오른쪽, 90 은 위→아래 (시계 방향)."""
    w, h = size
    angle = math.radians(gradient.get("rotation", 0))
    dx, dy = math.cos(angle), math.sin(angle)
    offset = gradient.get("offset", [0, 0])
    # 가로 한 줄 또는 세로 한 줄로 만들어 늘리면 충분히 비슷하다 (대각선은 작은 격자로)
    steps = 64
    grid_w = steps if abs(dx) > 1e-3 else 1
    grid_h = steps if abs(dy) > 1e-3 else 1
    color = Image.new("RGB", (grid_w, grid_h))
    alpha = Image.new("L", (grid_w, grid_h))
    reach = abs(dx) * 0.5 + abs(dy) * 0.5
    for gy in range(grid_h):
        for gx in range(grid_w):
            px = (gx + 0.5) / grid_w - 0.5 - offset[0]
            py = (gy + 0.5) / grid_h - 0.5 - offset[1]
            t = (px * dx + py * dy) / max(reach * 2, 1e-6) + 0.5
            t = max(0.0, min(1.0, t))
            c = sample(gradient.get("color"), t, 3)
            tr = sample(gradient.get("transparency"), t, 1)[0]
            color.putpixel((gx, gy), tuple(int(round(v)) for v in c))
            alpha.putpixel((gx, gy), int(round((1 - tr) * 255)))
    return color.resize((w, h), Image.BILINEAR), alpha.resize((w, h), Image.BILINEAR)


def apply_gradient(img: Image.Image, gradient: dict) -> Image.Image:
    color, alpha = gradient_layers(img.size, gradient)
    r, g, b, a = img.split()
    rgb = ImageChops.multiply(Image.merge("RGB", (r, g, b)), color)
    a = ImageChops.multiply(a, alpha)
    return Image.merge("RGBA", (*rgb.split(), a))


def nine_slice(src: Image.Image, size, center, scale: float) -> Image.Image:
    """9 조각: center = 원본 픽셀의 가운데 칸 (x0, y0, x1, y1), 모서리는 원본 크기 × scale."""
    w, h = size
    sw, sh = src.size
    x0, y0, x1, y1 = center
    x0, y0 = max(0, min(sw, x0)), max(0, min(sh, y0))
    x1, y1 = max(x0, min(sw, x1)), max(y0, min(sh, y1))
    left, top, right, bottom = x0 * scale, y0 * scale, (sw - x1) * scale, (sh - y1) * scale
    # 모서리가 상자보다 크면 비율대로 줄인다
    if left + right > w and left + right > 0:
        k = w / (left + right)
        left, right = left * k, right * k
    if top + bottom > h and top + bottom > 0:
        k = h / (top + bottom)
        top, bottom = top * k, bottom * k
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    xs_src = [0, x0, x1, sw]
    ys_src = [0, y0, y1, sh]
    xs_dst = [0, round(left), round(w - right), w]
    ys_dst = [0, round(top), round(h - bottom), h]
    for i in range(3):
        for j in range(3):
            sx0, sx1 = xs_src[i], xs_src[i + 1]
            sy0, sy1 = ys_src[j], ys_src[j + 1]
            dx0, dx1 = xs_dst[i], xs_dst[i + 1]
            dy0, dy1 = ys_dst[j], ys_dst[j + 1]
            if sx1 <= sx0 or sy1 <= sy0 or dx1 <= dx0 or dy1 <= dy0:
                continue
            piece = src.crop((sx0, sy0, sx1, sy1)).resize((dx1 - dx0, dy1 - dy0), Image.LANCZOS)
            out.paste(piece, (dx0, dy0))
    return out


def draw_image(img: Image.Image, size, image: dict, scale: float) -> Image.Image:
    w, h = size
    src = img
    rect_size = image.get("rectSize") or [0, 0]
    if rect_size[0] > 0 and rect_size[1] > 0:
        ox, oy = image.get("rectOffset") or [0, 0]
        src = img.crop((ox, oy, ox + rect_size[0], oy + rect_size[1]))
    kind = image.get("scaleType", "Stretch")
    if kind == "Slice":
        center = image.get("sliceCenter") or [0, 0, 0, 0]
        if center[2] > center[0] or center[3] > center[1]:
            return nine_slice(src, (w, h), center, image.get("sliceScale", 1) * scale)
        return src.resize((w, h), Image.LANCZOS)
    if kind in ("Fit", "Crop"):
        sw, sh = src.size
        k = min(w / sw, h / sh) if kind == "Fit" else max(w / sw, h / sh)
        fitted = src.resize((max(1, round(sw * k)), max(1, round(sh * k))), Image.LANCZOS)
        out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        out.paste(fitted, ((w - fitted.width) // 2, (h - fitted.height) // 2))
        return out
    if kind == "Tile":
        ts = image.get("tileSize") or [1, 0, 1, 0]
        tw = max(1, round(ts[0] * w + ts[1] * scale))
        th = max(1, round(ts[2] * h + ts[3] * scale))
        tile = src.resize((tw, th), Image.LANCZOS)
        out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        for ty in range(0, h, th):
            for tx in range(0, w, tw):
                out.paste(tile, (tx, ty))
        return out
    return src.resize((w, h), Image.LANCZOS)


# 글자 -------------------------------------------------------------------------------


def wrap_lines(fonts: Fonts, text: str, size: int, width: float, wrapped: bool):
    lines = []
    for paragraph in text.split("\n"):
        if not wrapped:
            lines.append(paragraph)
            continue
        current = ""
        for word in paragraph.split(" "):
            candidate = word if current == "" else current + " " + word
            if current and fonts.width(candidate, size) > width:
                lines.append(current)
                current = word
            else:
                current = candidate
        lines.append(current)
    return lines


def draw_text(layer: Image.Image, fonts: Fonts, box, text: dict):
    """TextLabel 글자. box = 층 안의 (x, y, w, h)."""
    x, y, w, h = box
    size = max(1, int(round(text.get("size", 14))))
    content = text.get("text", "")
    wrapped = text.get("wrapped", False)
    if text.get("scaled"):
        size = max(1, int(h))
        while size > 4:
            lines = wrap_lines(fonts, content, size, w, wrapped)
            if max(fonts.width(line, size) for line in lines) <= w and len(lines) * size * 1.15 <= h:
                break
            size -= 1
    lines = wrap_lines(fonts, content, size, w, wrapped)
    line_h = size * 1.15
    total = line_h * len(lines)
    ya = text.get("yAlign", "Center")
    top = y + (h - total) / 2 if ya == "Center" else (y if ya == "Top" else y + h - total)
    draw = ImageDraw.Draw(layer)
    fill = rgba(text.get("color", [0, 0, 0]), 1 - text.get("transparency", 0))
    stroke_alpha = (1 - text.get("strokeTransparency", 1)) * (1 - text.get("transparency", 0))
    stroke = rgba(text.get("strokeColor", [0, 0, 0]), stroke_alpha)
    for index, line in enumerate(lines):
        lw = fonts.width(line, size)
        xa = text.get("xAlign", "Center")
        left = x + (w - lw) / 2 if xa == "Center" else (x if xa == "Left" else x + w - lw)
        pen = left
        base = top + index * line_h + (line_h - size) / 2
        for ch in line:
            font = fonts.pick(ch, size)
            if stroke_alpha > 0.02:
                draw.text((pen, base), ch, font=font, fill=fill, stroke_width=1, stroke_fill=stroke)
            else:
                draw.text((pen, base), ch, font=font, fill=fill)
            pen += font.getlength(ch)


# 마디 하나 그리기 --------------------------------------------------------------------


class Renderer:
    def __init__(self, snapshot: dict, assets: Assets, fonts: Fonts, options):
        self.snapshot = snapshot
        self.assets = assets
        self.fonts = fonts
        self.options = options
        screen = snapshot["screen"]
        self.width, self.height = int(screen["width"]), int(screen["height"])
        self.canvas = Image.new("RGBA", (self.width, self.height), (0, 0, 0, 0))
        self.missing_images = 0

    def composite(self, layer: Image.Image, x: int, y: int, clip):
        """layer 를 (x, y) 에 겹친다. clip = [x, y, w, h] 또는 None."""
        x0, y0, x1, y1 = x, y, x + layer.width, y + layer.height
        cx0, cy0, cx1, cy1 = 0, 0, self.width, self.height
        if clip:
            cx0, cy0 = max(cx0, math.floor(clip[0] + 0.5)), max(cy0, math.floor(clip[1] + 0.5))
            cx1 = min(cx1, math.floor(clip[0] + clip[2] + 0.5))
            cy1 = min(cy1, math.floor(clip[1] + clip[3] + 0.5))
        ix0, iy0, ix1, iy1 = max(x0, cx0), max(y0, cy0), min(x1, cx1), min(y1, cy1)
        if ix1 <= ix0 or iy1 <= iy0:
            return
        piece = layer.crop((ix0 - x, iy0 - y, ix1 - x, iy1 - y))
        self.canvas.alpha_composite(piece, (ix0, iy0))

    def node(self, node: dict):
        x, y, w, h = node["rect"]
        scale = node.get("scale", 1)
        ix0, iy0 = int(math.floor(x + 0.5)), int(math.floor(y + 0.5))
        ix1, iy1 = int(math.floor(x + w + 0.5)), int(math.floor(y + h + 0.5))
        dw, dh = ix1 - ix0, iy1 - iy0
        stroke = node.get("stroke")
        border = node.get("border") if not node.get("corner") else None
        margin = 0
        if stroke and stroke.get("transparency", 0) < 1 and node.get("class") not in ("TextLabel", "TextButton"):
            margin = max(margin, int(math.ceil(stroke["thickness"])))
        if border:
            margin = max(margin, int(border["size"]))
        if dw <= 0 and dh <= 0 and margin == 0:
            return
        lw, lh = max(dw, 0) + margin * 2, max(dh, 0) + margin * 2
        if lw <= 0 or lh <= 0:
            return
        layer = Image.new("RGBA", (lw, lh), (0, 0, 0, 0))
        draw = ImageDraw.Draw(layer)
        box = (margin, margin, margin + dw - 1, margin + dh - 1)
        radius = 0
        if node.get("corner"):
            radius = max(0, min(node["corner"]["radius"], min(dw, dh) / 2))
        drew = False

        bg = node.get("bg")
        if bg and dw > 0 and dh > 0:
            alpha = 1 - bg["transparency"]
            if border:
                size = border["size"]
                mode = border.get("mode", "Outline")
                grow = size if mode == "Outline" else (size / 2 if mode == "Middle" else 0)
                outer = (box[0] - grow, box[1] - grow, box[2] + grow, box[3] + grow)
                draw.rectangle(outer, fill=rgba(border["color"], alpha))
                inner_shrink = 0 if mode == "Outline" else (size / 2 if mode == "Middle" else size)
                draw.rectangle(
                    (box[0] + inner_shrink, box[1] + inner_shrink, box[2] - inner_shrink, box[3] - inner_shrink),
                    fill=rgba(bg["color"], alpha),
                )
            elif radius > 0:
                draw.rounded_rectangle(box, radius=radius, fill=rgba(bg["color"], alpha))
            else:
                draw.rectangle(box, fill=rgba(bg["color"], alpha))
            drew = True

        image = node.get("image")
        if image and dw > 0 and dh > 0:
            src = self.assets.get(image)
            if src is None:
                if not os.path.basename(image.get("file") or "") in self.assets.missing:
                    self.missing_images += 1
                    draw.rectangle(box, outline=(255, 0, 255, 160))
            else:
                art = draw_image(src, (dw, dh), image, scale)
                art = tint(art, image.get("color", [255, 255, 255]))
                art = multiply_alpha(art, 1 - image.get("transparency", 0))
                if radius > 0:
                    mask = Image.new("L", (dw, dh), 0)
                    ImageDraw.Draw(mask).rounded_rectangle((0, 0, dw - 1, dh - 1), radius=radius, fill=255)
                    art.putalpha(ImageChops.multiply(art.getchannel("A"), mask))
                layer.alpha_composite(art, (margin, margin))
                drew = True

        text = node.get("text")
        if text and dw > 0 and dh > 0:
            draw_text(layer, self.fonts, (margin, margin, dw, dh), text)
            drew = True

        if stroke and margin > 0 and dw > 0 and dh > 0:
            t = stroke["thickness"]
            alpha = 1 - stroke.get("transparency", 0)
            outer = (box[0] - t, box[1] - t, box[2] + t, box[3] + t)
            draw.rounded_rectangle(
                outer,
                radius=radius + t if radius > 0 else 0,
                outline=rgba(stroke["color"], alpha),
                width=max(1, int(round(t))),
            )
            drew = True

        if node.get("gradient") and drew:
            layer = apply_gradient(layer, node["gradient"])

        if self.options.boxes and dw > 0 and dh > 0:
            hot = self.options.boxes_name and node.get("name") == self.options.boxes_name
            ImageDraw.Draw(layer).rectangle(
                box, outline=(255, 60, 60, 230) if hot else (80, 220, 255, 90), width=2 if hot else 1
            )
            drew = True

        if not drew:
            return
        rotation = node.get("rotation", 0)
        ox, oy = ix0 - margin, iy0 - margin
        if rotation:
            cx, cy = ox + lw / 2, oy + lh / 2
            layer = layer.rotate(-rotation, resample=Image.BICUBIC, expand=True)
            ox, oy = int(round(cx - layer.width / 2)), int(round(cy - layer.height / 2))
        self.composite(layer, ox, oy, node.get("clip"))

    def scrollbar(self, node: dict):
        bar = node["scroll"]["bar"]
        x, y, w, h = bar["rect"]
        dw, dh = max(1, round(w)), max(1, round(h))
        layer = Image.new("RGBA", (dw, dh), (0, 0, 0, 0))
        ImageDraw.Draw(layer).rounded_rectangle(
            (0, 0, dw - 1, dh - 1), radius=dw / 2, fill=rgba(bar["color"], 1 - bar.get("transparency", 0))
        )
        self.composite(layer, round(x), round(y), node.get("clip"))

    def core(self, item: dict):
        x, y, w, h = item["rect"]
        layer = Image.new("RGBA", (int(w), int(h)), (0, 0, 0, 0))
        draw = ImageDraw.Draw(layer)
        if item["kind"] == "backpack":
            draw.rounded_rectangle(
                (0, 0, w - 1, h - 1), radius=item.get("round", 6), fill=(31, 31, 31, 150), outline=(255, 255, 255, 40)
            )
            small = self.fonts.pick("1", 12)
            draw.text((4, 2), item.get("key", ""), font=small, fill=(255, 255, 255, 200))
            label = item.get("label", "")
            size = 13 if w >= 60 else 11
            lw = self.fonts.width(label, size)
            pen = (w - lw) / 2
            for ch in label:
                font = self.fonts.pick(ch, size)
                draw.text((pen, h / 2 - size / 2), ch, font=font, fill=(255, 255, 255, 220))
                pen += font.getlength(ch)
        else:
            draw.rounded_rectangle(
                (0, 0, w - 1, h - 1), radius=item.get("round", 8), fill=(20, 20, 24, 140), outline=(255, 255, 255, 60)
            )
            label = item.get("label", "")
            size = 12
            lw = self.fonts.width(label, size)
            pen = (w - lw) / 2
            for ch in label:
                font = self.fonts.pick(ch, size)
                draw.text((pen, h / 2 - size / 2 - 1), ch, font=font, fill=(255, 255, 255, 170))
                pen += font.getlength(ch)
        self.composite(layer, int(x), int(y), None)


def flatten(snapshot: dict):
    """그리는 차례대로 (마디, 종류). ScrollingFrame 막대는 그 자손을 다 그린 뒤에."""
    items = []

    def walk(node) -> float:
        top = node.get("order", 0)
        for child in node.get("children") or []:
            top = max(top, walk(child))
        if node.get("class") != "ScreenGui":
            items.append((node.get("order", 0), node, "node"))
            if node.get("scroll", {}).get("bar"):
                items.append((top + 0.5, node, "bar"))
        return top

    for gui in snapshot.get("guis") or []:
        walk(gui)
    items.sort(key=lambda item: item[0])
    return items


# 배치 검사 (--report) ----------------------------------------------------------------


def inter(a, b):
    if a is None or b is None:
        return None
    x0, y0 = max(a[0], b[0]), max(a[1], b[1])
    x1, y1 = min(a[0] + a[2], b[0] + b[2]), min(a[1] + a[3], b[1] + b[3])
    if x1 <= x0 or y1 <= y0:
        return None
    return [x0, y0, x1 - x0, y1 - y0]


def area(r) -> float:
    return r[2] * r[3] if r else 0.0


def label_of(node) -> str:
    if node.get("bitmapText"):
        return f'"{node["bitmapText"]}"'
    if node.get("text"):
        return f'"{node["text"]["text"]}"'
    return node.get("class", "")


def short_path(path: str) -> str:
    parts = path.split("/")
    return "/".join(parts[1:]) if len(parts) > 1 else path


def text_ink(node, fonts: Fonts):
    """글이 실제로 차지하는 곳. BitmapText 틀은 스냅숏의 ink, TextLabel 은 글자 폭을 재어 정렬대로."""
    if node.get("ink"):
        return node["ink"]
    text = node.get("text")
    x, y, w, h = node["rect"]
    if not text or text.get("wrapped") or text.get("scaled"):
        return node["rect"]
    size = max(1, int(round(text.get("size", 14))))
    tw, th = min(w, fonts.width(text["text"], size)), min(h, size * 1.15)
    xa, ya = text.get("xAlign", "Center"), text.get("yAlign", "Center")
    left = x + (w - tw) / 2 if xa == "Center" else (x if xa == "Left" else x + w - tw)
    top = y + (h - th) / 2 if ya == "Center" else (y if ya == "Top" else y + h - th)
    return [left, top, tw, th]


def shows_text(node) -> bool:
    """다 투명한 글(흐려진 알림 따위)은 빼고 본다."""
    if node.get("text"):
        return node["text"].get("transparency", 0) < 0.98
    glyphs = [c for c in node.get("children") or [] if c.get("image")]
    return any(c["image"].get("transparency", 0) < 0.98 for c in glyphs) if glyphs else True


def report(snapshot: dict, fonts: Fonts, limit: int = 80) -> list[str]:
    """글끼리 겹침, 글과 버튼 겹침, 글이 창 밖으로 나감, 창이 화면 밖으로 나감, 자르기에 걸린 글."""
    issues: list[str] = []
    for gui in snapshot.get("guis") or []:
        screen = gui["rect"]
        for window in gui.get("children") or []:
            wr = window["rect"]
            if wr[2] > 0 and wr[3] > 0:
                inside = inter(wr, screen)
                if area(inside) < area(wr) - 1:
                    issues.append(
                        f"화면 밖: {short_path(window['path'])} {fmt(wr)} (화면 {fmt(screen)})"
                    )
            texts, buttons = [], []

            def walk(node, clip_by, button):
                is_text = bool(node.get("bitmapText") or node.get("text")) and shows_text(node)
                full = text_ink(node, fonts) if is_text else node["rect"]
                visible = inter(full, node.get("clip")) if node.get("clip") else full
                if is_text and visible:
                    texts.append((node, visible, clip_by, button))
                    if clip_by and clip_by != "ScrollingFrame" and area(visible) < area(full) * 0.98:
                        issues.append(f"잘림: {short_path(node['path'])} {label_of(node)}")
                    if area(inter(full, wr)) < area(full) - 1 and window is not node:
                        issues.append(f"창 밖 글: {short_path(node['path'])} {label_of(node)} {fmt(full)}")
                cls = node.get("class")
                own_button = button
                if cls in ("ImageButton", "TextButton") and (node.get("image") or node.get("bg") or node.get("text")):
                    rect = inter(node["rect"], node.get("clip")) if node.get("clip") else node["rect"]
                    if rect:
                        buttons.append((node, rect))
                    own_button = node["path"]
                child_clip = clip_by
                if node.get("clipsDescendants") or cls == "ScrollingFrame":
                    child_clip = cls
                for child in node.get("children") or []:
                    walk(child, child_clip, own_button)

            walk(window, None, None)
            for i in range(len(texts)):
                a, ra, _, ba = texts[i]
                for j in range(i + 1, len(texts)):
                    b, rb, _, bb = texts[j]
                    if a["path"].startswith(b["path"] + "/") or b["path"].startswith(a["path"] + "/"):
                        continue
                    hit = inter(ra, rb)
                    if covers(hit, ra, rb):
                        issues.append(
                            f"글 겹침: {short_path(a['path'])} {label_of(a)} ↔ {short_path(b['path'])} {label_of(b)}"
                            f" ({hit[2]:.0f}×{hit[3]:.0f})"
                        )
            for node, rect, _, inside_button in texts:
                for button, br in buttons:
                    if inside_button == button["path"] or node["path"].startswith(button["path"] + "/"):
                        continue
                    hit = inter(rect, br)
                    if covers(hit, rect, None):
                        issues.append(
                            f"글이 버튼에 가림: {short_path(node['path'])} {label_of(node)} ↔ {short_path(button['path'])}"
                            f" ({hit[2]:.0f}×{hit[3]:.0f})"
                        )
    seen, out = set(), []
    for issue in issues:
        if issue not in seen:
            seen.add(issue)
            out.append(issue)
    return out[:limit] + ([f"… 그 밖에 {len(out) - limit}건"] if len(out) > limit else [])


def covers(hit, a, b) -> bool:
    """겹친 곳이 글자 반쯤은 가릴 만한가 (글자 높이의 40% 이상 가로세로로 겹치거나, 글 넓이의 12% 이상)."""
    if not hit or area(hit) <= 6:
        return False
    glyph = min(r[3] for r in (a, b) if r)
    if hit[2] >= glyph * 0.4 and hit[3] >= glyph * 0.4:
        return True
    return area(hit) > 0.12 * min(area(r) for r in (a, b) if r)


def fmt(r) -> str:
    return f"[{r[0]:.0f},{r[1]:.0f} {r[2]:.0f}×{r[3]:.0f}]"


def scene_background(width: int, height: int) -> Image.Image:
    """옅은 하늘과 풀빛 + 바둑판 (판과 글자가 잘 보이게)."""
    top, horizon, bottom = (150, 178, 196), (176, 190, 170), (84, 112, 70)
    sky = Image.new("RGB", (1, height))
    for yy in range(height):
        t = yy / max(1, height - 1)
        if t < 0.45:
            k = t / 0.45
            c = [top[i] + (horizon[i] - top[i]) * k for i in range(3)]
        else:
            k = (t - 0.45) / 0.55
            c = [horizon[i] + (bottom[i] - horizon[i]) * k for i in range(3)]
        sky.putpixel((0, yy), tuple(int(v) for v in c))
    bg = sky.resize((width, height)).convert("RGBA")
    cell = 32
    checker = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(checker)
    for cy in range(0, height, cell):
        for cx in range((cy // cell) % 2 * cell, width, cell * 2):
            draw.rectangle((cx, cy, cx + cell - 1, cy + cell - 1), fill=(255, 255, 255, 14))
    bg.alpha_composite(checker)
    return bg


def main():
    parser = argparse.ArgumentParser(description="GUI 스냅숏 JSON 을 PNG 로 그린다 (tools/gui_snapshot.luau)")
    parser.add_argument("input")
    parser.add_argument("output", nargs="?")
    parser.add_argument("--scale", type=float)
    parser.add_argument("--size")
    parser.add_argument("--bg")
    parser.add_argument("--bg-alpha", type=float, default=1.0)
    parser.add_argument("--missing", default="")
    parser.add_argument("--boxes", action="store_true")
    parser.add_argument("--boxes-name")
    parser.add_argument("--no-core", action="store_true")
    parser.add_argument("--font")
    parser.add_argument("--report", action="store_true")
    options = parser.parse_args()

    snapshot = json.load(open(options.input, encoding="utf-8"))
    output = options.output or os.path.splitext(options.input)[0] + ".png"
    missing = {name.strip() for name in options.missing.split(",") if name.strip()}
    assets = Assets(snapshot, missing)
    fonts = Fonts(options.font)
    renderer = Renderer(snapshot, assets, fonts, options)

    for _, node, kind in flatten(snapshot):
        if kind == "bar":
            renderer.scrollbar(node)
        else:
            renderer.node(node)
    if not options.no_core:
        for item in snapshot.get("core") or []:
            renderer.core(item)

    width, height = renderer.width, renderer.height
    if options.bg:
        background = Image.open(options.bg).convert("RGBA").resize((width, height), Image.LANCZOS)
    else:
        background = scene_background(width, height)
    gui = renderer.canvas
    if options.bg_alpha < 1:
        gui = multiply_alpha(gui, options.bg_alpha)
    background.alpha_composite(gui)
    result = background.convert("RGB")

    if options.size:
        tw, th = (int(v) for v in options.size.lower().split("x"))
        result = result.resize((tw, th), Image.LANCZOS)
    elif options.scale and abs(options.scale - 1) > 1e-6:
        result = result.resize(
            (max(1, round(width * options.scale)), max(1, round(height * options.scale))), Image.LANCZOS
        )
    os.makedirs(os.path.dirname(os.path.abspath(output)), exist_ok=True)
    result.save(output)
    note = f", 못 찾은 그림 {renderer.missing_images}개" if renderer.missing_images else ""
    print(f"{output}: {result.width}×{result.height}{note}")
    if assets.unknown:
        print("  그림 파일을 모르는 id:", ", ".join(sorted(assets.unknown))[:400], file=sys.stderr)
    if options.report:
        issues = report(snapshot, fonts)
        print(f"배치 검사: {len(issues)}건" if issues else "배치 검사: 문제 없음")
        for issue in issues:
            print("  " + issue)


if __name__ == "__main__":
    main()
