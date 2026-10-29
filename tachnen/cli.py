"""Giao diện dòng lệnh: tachnen anh.jpg [anh2.jpg ...] --nen blur"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from .core import DEFAULT_MODEL, process

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


def _collect(inputs: list[str]) -> list[Path]:
    files: list[Path] = []
    for item in inputs:
        p = Path(item)
        if p.is_dir():
            files += sorted(f for f in p.iterdir() if f.suffix.lower() in IMAGE_EXT)
        elif p.is_file():
            files.append(p)
        else:
            print(f"[bỏ qua] không tìm thấy: {item}", file=sys.stderr)
    return files


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="tachnen",
        description="Tách nền ảnh offline: PNG trong suốt + ảnh nền mới + ảnh so sánh.",
    )
    ap.add_argument("inputs", nargs="*", help="file ảnh hoặc thư mục ảnh")
    ap.add_argument("-o", "--out", default="ketqua", help="thư mục kết quả (mặc định: ketqua)")
    ap.add_argument("-n", "--nen", default="blur",
                    help='nền mới: "#ffffff", "blur", "blur:30", "gradient:#ff9a8b,#6a82fb"')
    ap.add_argument("-m", "--model", default=DEFAULT_MODEL,
                    help=f"model tách nền (mặc định: {DEFAULT_MODEL}; ví dụ: u2net, u2net_human_seg)")
    ap.add_argument("--nhanh", action="store_true", help="bỏ bước làm mịn viền (nhanh hơn, viền thô hơn)")
    ap.add_argument("--web", action="store_true", help="mở giao diện web tại http://127.0.0.1:7860")
    ap.add_argument("--port", type=int, default=7860)
    args = ap.parse_args(argv)

    if args.web:
        from .web import run
        run(port=args.port)
        return 0

    files = _collect(args.inputs)
    if not files:
        ap.print_help()
        return 1
    for f in files:
        t0 = time.time()
        paths = process(f, args.out, background=args.nen, model=args.model, refine=not args.nhanh)
        print(f"✔ {f.name} ({time.time() - t0:.1f}s)")
        for key, label in (("cutout", "PNG trong suốt"), ("result", "Nền mới"), ("compare", "So sánh")):
            print(f"   {label:15}: {paths[key]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
