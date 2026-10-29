"""Lõi xử lý: tách chủ thể, tạo nền mới, ghép ảnh và tạo ảnh so sánh."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

DEFAULT_MODEL = "isnet-general-use"

# Các font có đủ dấu tiếng Việt, thử lần lượt.
_FONT_CANDIDATES = [
    os.environ.get("TACHNEN_FONT", ""),
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
    "/usr/share/fonts/opentype/noto/NotoSans-Bold.ttf",
    "/Library/Fonts/Arial Unicode.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
    "C:/Windows/Fonts/segoeuib.ttf",
]


@lru_cache(maxsize=4)
def _session(model: str):
    from rembg import new_session  # import trễ để CLI --help chạy nhanh

    return new_session(model)


def _load_font(size: int) -> ImageFont.ImageFont:
    for path in _FONT_CANDIDATES:
        if path and Path(path).is_file():
            return ImageFont.truetype(path, size)
    try:
        return ImageFont.truetype("DejaVuSans-Bold.ttf", size)
    except OSError:
        return ImageFont.load_default(size=size)


def _hex(color: str) -> tuple[int, int, int]:
    c = color.strip().lstrip("#")
    if len(c) == 3:
        c = "".join(ch * 2 for ch in c)
    if len(c) != 6:
        raise ValueError(f"Mã màu không hợp lệ: {color!r} (ví dụ: #1e90ff)")
    return tuple(int(c[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def cutout(img: Image.Image, model: str = DEFAULT_MODEL, refine: bool = True) -> Image.Image:
    """Trả về ảnh RGBA chỉ còn chủ thể, nền trong suốt.

    refine=True bật alpha matting: viền tóc mịn hơn, bớt quầng màu nền cũ.
    """
    from rembg import remove

    img = ImageOps.exif_transpose(img).convert("RGB")
    out = remove(img, session=_session(model), alpha_matting=refine)
    return out.convert("RGBA")


def make_background(spec: str, original: Image.Image) -> Image.Image:
    """Tạo nền mới cùng kích thước ảnh gốc.

    spec:
      - "#ffffff"              : màu trơn
      - "blur" / "blur:25"     : làm mờ ảnh gốc (bán kính tuỳ chọn)
      - "gradient:#a,#b"       : chuyển màu dọc từ #a (trên) xuống #b (dưới)
    """
    w, h = original.size
    s = spec.strip().lower()
    if s.startswith("blur"):
        radius = float(s.split(":", 1)[1]) if ":" in s else max(w, h) / 40
        return original.convert("RGB").filter(ImageFilter.GaussianBlur(radius))
    if s.startswith("gradient"):
        parts = s.split(":", 1)[1] if ":" in s else "#ff9a8b,#6a82fb"
        top, bottom = (_hex(p) for p in parts.split(","))
        col = Image.new("RGB", (1, h))
        for y in range(h):
            t = y / max(h - 1, 1)
            col.putpixel((0, y), tuple(round(a + (b - a) * t) for a, b in zip(top, bottom)))
        return col.resize((w, h))
    return Image.new("RGB", (w, h), _hex(s))


def composite(subject: Image.Image, background: Image.Image) -> Image.Image:
    bg = background.convert("RGBA").resize(subject.size)
    return Image.alpha_composite(bg, subject).convert("RGB")


def _checkerboard(size: tuple[int, int], cell: int = 24) -> Image.Image:
    w, h = size
    board = Image.new("RGB", (w, h), (235, 235, 235))
    d = ImageDraw.Draw(board)
    for y in range(0, h, cell):
        for x in range((y // cell) % 2 * cell, w, cell * 2):
            d.rectangle([x, y, x + cell - 1, y + cell - 1], fill=(200, 200, 200))
    return board


def compare(original: Image.Image, subject: Image.Image, result: Image.Image,
            height: int = 900) -> Image.Image:
    """Ảnh so sánh 3 khung: Trước | Tách nền | Sau."""
    original = ImageOps.exif_transpose(original).convert("RGB")
    scale = height / original.height
    pw = round(original.width * scale)
    size = (pw, height)

    transparent_view = Image.alpha_composite(
        _checkerboard(subject.size).convert("RGBA"), subject
    ).convert("RGB")
    panels = [
        ("Trước", original.resize(size, Image.LANCZOS)),
        ("Tách nền", transparent_view.resize(size, Image.LANCZOS)),
        ("Sau", result.resize(size, Image.LANCZOS)),
    ]

    gap, label_h = 16, round(height * 0.09)
    canvas = Image.new("RGB", (pw * 3 + gap * 4, height + label_h + gap * 2), (24, 24, 28))
    draw = ImageDraw.Draw(canvas)
    font = _load_font(round(label_h * 0.55))
    for i, (label, panel) in enumerate(panels):
        x = gap + i * (pw + gap)
        canvas.paste(panel, (x, gap))
        cx, cy = x + pw / 2, gap + height + label_h / 2
        draw.text((cx, cy), label, font=font, fill=(255, 255, 255), anchor="mm")
    return canvas


def process(input_path: str | Path, out_dir: str | Path, background: str = "blur",
            model: str = DEFAULT_MODEL, refine: bool = True) -> dict[str, Path]:
    """Xử lý một ảnh, ghi 3 file kết quả và trả về đường dẫn."""
    input_path, out_dir = Path(input_path), Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    original = ImageOps.exif_transpose(Image.open(input_path)).convert("RGB")
    subject = cutout(original, model=model, refine=refine)
    result = composite(subject, make_background(background, original))
    stem = input_path.stem
    paths = {
        "cutout": out_dir / f"{stem}_tachnen.png",
        "result": out_dir / f"{stem}_nenmoi.jpg",
        "compare": out_dir / f"{stem}_sosanh.jpg",
    }
    subject.save(paths["cutout"])
    result.save(paths["result"], quality=92)
    compare(original, subject, result).save(paths["compare"], quality=90)
    return paths
