import os
import re
import shutil
import tempfile
from urllib.parse import urlparse

from flask import Flask, request, send_file, render_template_string, jsonify
import yt_dlp

app = Flask(__name__)

ALLOWED_HOSTS = ("tiktok.com", "vm.tiktok.com", "vt.tiktok.com")

PAGE = """<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>تحميل فيديوهات تيك توك</title>
<style>
  :root { --bg:#0f1115; --card:#181b22; --text:#f2f2f2; --mut:#9aa0ab; --acc:#fe2c55; }
  * { box-sizing: border-box; }
  body { margin:0; min-height:100vh; display:grid; place-items:center; padding:16px;
         background:var(--bg); color:var(--text); font-family: system-ui, "Segoe UI", Tahoma, sans-serif; }
  .card { width:100%; max-width:480px; background:var(--card); border-radius:16px; padding:24px; }
  h1 { font-size:1.3rem; margin:0 0 6px; }
  p.sub { color:var(--mut); margin:0 0 18px; font-size:.9rem; }
  input { width:100%; padding:14px; border-radius:10px; border:1px solid #2a2f3a;
          background:#0f1115; color:var(--text); font-size:1rem; direction:ltr; }
  button { width:100%; margin-top:12px; padding:14px; border:0; border-radius:10px;
           background:var(--acc); color:#fff; font-size:1rem; font-weight:600; cursor:pointer; }
  button:disabled { opacity:.6; cursor:wait; }
  #msg { margin-top:14px; font-size:.9rem; color:var(--mut); min-height:1.2em; }
  #msg.err { color:#ff7a8a; }
  .note { margin-top:18px; font-size:.78rem; color:var(--mut); line-height:1.6; }
</style>
</head>
<body>
<div class="card">
  <h1>تحميل فيديو تيك توك</h1>
  <p class="sub">أعلى جودة لين 1080p، وأعلى فريمات متاحة للفيديو (120fps لو موجودة).</p>
  <input id="url" type="url" placeholder="الصق رابط الفيديو هنا" autocomplete="off">
  <button id="go">تحميل</button>
  <div id="msg"></div>
  <div class="note">حمّل فيديوهاتك أو بإذن أصحابها فقط. أغلب فيديوهات تيك توك تكون 30 أو 60 فريم، فالأداة تنزل أعلى جودة متاحة فعلياً.</div>
</div>
<script>
const url = document.getElementById('url');
const go = document.getElementById('go');
const msg = document.getElementById('msg');

go.addEventListener('click', async () => {
  const link = url.value.trim();
  if (!link) { msg.className = 'err'; msg.textContent = 'الصق الرابط أول.'; return; }
  go.disabled = true; msg.className = ''; msg.textContent = 'جاري التحميل...';
  try {
    const r = await fetch('/download?url=' + encodeURIComponent(link));
    if (!r.ok) {
      const j = await r.json().catch(() => ({}));
      throw new Error(j.error || 'صار خطأ');
    }
    const fps = r.headers.get('X-Video-FPS');
    const h = r.headers.get('X-Video-Height');
    const blob = await r.blob();
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'tiktok.mp4';
    document.body.appendChild(a); a.click(); a.remove();
    msg.textContent = 'تم التحميل' + (h ? ' — ' + h + 'p' : '') + (fps ? ' @ ' + fps + 'fps' : '');
  } catch (e) {
    msg.className = 'err'; msg.textContent = e.message;
  } finally {
    go.disabled = false;
  }
});
</script>
</body>
</html>
"""


def is_tiktok(url: str) -> bool:
    try:
        host = (urlparse(url).hostname or "").lower()
    except ValueError:
        return False
    return any(host == h or host.endswith("." + h) for h in ALLOWED_HOSTS)


@app.get("/")
def index():
    return render_template_string(PAGE)


@app.get("/download")
def download():
    url = request.args.get("url", "").strip()
    if not is_tiktok(url):
        return jsonify(error="الرابط لازم يكون من تيك توك"), 400

    tmp = tempfile.mkdtemp()
    opts = {
        "outtmpl": os.path.join(tmp, "%(id)s.%(ext)s"),
        # أعلى دقة لين 1080 ثم أعلى فريمات متاحة
        "format": "bv*[height<=1080]+ba/b[height<=1080]/b",
        "format_sort": ["res:1080", "fps", "codec:h264"],
        "merge_output_format": "mp4",
        "quiet": True,
        "noplaylist": True,
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            path = ydl.prepare_filename(info)
            if not os.path.exists(path):
                path = os.path.splitext(path)[0] + ".mp4"
        resp = send_file(path, as_attachment=True, download_name="tiktok.mp4")
        resp.headers["X-Video-FPS"] = str(int(info.get("fps") or 0) or "")
        resp.headers["X-Video-Height"] = str(info.get("height") or "")
        resp.headers["Access-Control-Expose-Headers"] = "X-Video-FPS, X-Video-Height"
        resp.call_on_close(lambda: shutil.rmtree(tmp, ignore_errors=True))
        return resp
    except Exception:
        shutil.rmtree(tmp, ignore_errors=True)
        return jsonify(error="ما قدرت أحمّل الفيديو، تأكد من الرابط"), 400


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
