"""Giao diện web nhỏ (Flask) chạy hoàn toàn trên máy."""

from __future__ import annotations

import base64
import io
import time

from flask import Flask, render_template_string, request
from PIL import Image, ImageOps

from .core import DEFAULT_MODEL, compare, composite, cutout, make_background

PAGE = """<!doctype html>
<html lang="vi"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>tachnen – tách nền ảnh offline</title>
<style>
 body{font-family:system-ui,sans-serif;background:#18181c;color:#eee;margin:0;padding:24px;max-width:1100px;margin:auto}
 h1{margin:0 0 4px} p.sub{color:#aaa;margin-top:0}
 form{background:#24242a;padding:16px;border-radius:12px;display:flex;flex-wrap:wrap;gap:12px;align-items:center}
 select,input,button{font-size:15px;padding:8px;border-radius:8px;border:1px solid #444;background:#111;color:#eee}
 button{background:#2f80ed;border:none;font-weight:600;cursor:pointer}
 .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:16px;margin-top:20px}
 .card{background:#24242a;border-radius:12px;padding:12px}
 .card img{width:100%;border-radius:8px}
 .checker{background:repeating-conic-gradient(#ccc 0 25%,#eee 0 50%) 0 0/24px 24px;border-radius:8px}
 a{color:#6fb1ff} .err{color:#ff7b7b}
</style></head><body>
<h1>✂️ tachnen</h1>
<p class="sub">Tách nền ảnh ngay trên máy bạn – miễn phí, không cần mạng, không upload đi đâu.</p>
<form method="post" enctype="multipart/form-data">
 <input type="file" name="anh" accept="image/*" required>
 <label>Nền mới
  <select name="kieu">
   <option value="blur">Làm mờ ảnh gốc</option>
   <option value="color">Màu trơn</option>
   <option value="gradient">Chuyển màu</option>
  </select></label>
 <input type="color" name="mau1" value="#ff9a8b" title="Màu 1">
 <input type="color" name="mau2" value="#6a82fb" title="Màu 2 (chuyển màu)">
 <label><input type="checkbox" name="min" checked> Mịn viền tóc</label>
 <button type="submit">Tách nền</button>
</form>
{% if error %}<p class="err">{{ error }}</p>{% endif %}
{% if res %}
<p>Xong trong {{ res.seconds }} giây.</p>
<div class="grid">
 <div class="card"><b>PNG trong suốt</b><div class="checker"><img src="data:image/png;base64,{{ res.cutout }}"></div>
  <a download="tachnen.png" href="data:image/png;base64,{{ res.cutout }}">⬇ Tải PNG</a></div>
 <div class="card"><b>Nền mới</b><img src="data:image/jpeg;base64,{{ res.result }}">
  <a download="nenmoi.jpg" href="data:image/jpeg;base64,{{ res.result }}">⬇ Tải ảnh</a></div>
</div>
<div class="card" style="margin-top:16px"><b>Trước / Sau</b><img src="data:image/jpeg;base64,{{ res.compare }}">
 <a download="sosanh.jpg" href="data:image/jpeg;base64,{{ res.compare }}">⬇ Tải ảnh so sánh</a></div>
{% endif %}
</body></html>"""


def _b64(img: Image.Image, fmt: str) -> str:
    buf = io.BytesIO()
    img.save(buf, format=fmt, **({"quality": 90} if fmt == "JPEG" else {}))
    return base64.b64encode(buf.getvalue()).decode()


def create_app(model: str = DEFAULT_MODEL) -> Flask:
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024

    @app.route("/", methods=["GET", "POST"])
    def index():
        if request.method == "GET":
            return render_template_string(PAGE, res=None, error=None)
        try:
            original = ImageOps.exif_transpose(Image.open(request.files["anh"].stream)).convert("RGB")
        except Exception:
            return render_template_string(PAGE, res=None, error="Không đọc được file ảnh.")
        kieu = request.form.get("kieu", "blur")
        c1, c2 = request.form.get("mau1", "#ff9a8b"), request.form.get("mau2", "#6a82fb")
        spec = {"blur": "blur", "color": c1, "gradient": f"gradient:{c1},{c2}"}.get(kieu, "blur")
        t0 = time.time()
        subject = cutout(original, model=model, refine=bool(request.form.get("min")))
        result = composite(subject, make_background(spec, original))
        cmp_img = compare(original, subject, result, height=700)
        res = {
            "seconds": f"{time.time() - t0:.1f}",
            "cutout": _b64(subject, "PNG"),
            "result": _b64(result, "JPEG"),
            "compare": _b64(cmp_img, "JPEG"),
        }
        return render_template_string(PAGE, res=res, error=None)

    return app


def run(host: str = "127.0.0.1", port: int = 7860) -> None:
    print(f"Mở trình duyệt: http://{host}:{port}")
    create_app().run(host=host, port=port)
