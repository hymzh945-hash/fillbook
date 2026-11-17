"""Local web UI: drop a fills export, get the audit summary."""

from __future__ import annotations

import base64
import json
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import analytics, data, licensing, trades as matching
from .version import __version__

PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>FillBook</title><style>
:root{--bg:#0b0f18;--panel:#121a29;--line:#22304a;--fg:#e8eef8;--muted:#8b9ab1;--accent:#38bdf8}
body{margin:0;background:var(--bg);color:var(--fg);font:14px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
.wrap{max-width:820px;margin:0 auto;padding:44px 24px}
h1{font-size:26px;margin:0 0 4px} .sub{color:var(--muted);font-size:13px}
.tier{font-size:11px;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);margin-bottom:18px}
.drop{border:1.5px dashed var(--line);border-radius:14px;padding:32px;text-align:center;background:var(--panel)}
.drop.on{border-color:var(--accent)}
input[type=file]{display:none} label{color:var(--accent);cursor:pointer;font-weight:600}
button{background:var(--accent);color:#05121c;font-weight:650;border:none;border-radius:9px;
padding:10px 20px;cursor:pointer;font-size:13px;margin-top:14px}
pre{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:14px;
overflow:auto;font-size:12.5px;margin-top:16px;white-space:pre-wrap}
.lock{border:1px dashed var(--line);border-radius:12px;padding:14px;margin-top:14px;font-size:13px}
.lock a{color:var(--accent)}
</style></head><body><div class="wrap">
<h1>FillBook</h1><div class="sub">Drop your fills export — OKX, Binance or any CSV with side/qty/price.</div>
<div class="tier">tier: __TIER__ · v__VERSION__</div>
<div class="drop" id="drop"><input type="file" id="file" accept=".csv,.json,.jsonl">
<div>Drop a file here or <label for="file">browse</label></div>
<div class="sub" id="fname">no file selected</div></div>
<button id="go">Audit</button>
__LOCK__
<pre id="out">results appear here</pre></div><script>
const drop=document.getElementById('drop'),file=document.getElementById('file'),out=document.getElementById('out');
let payload=null;
function read(f){const r=new FileReader();r.onload=()=>{payload=r.result.split(',')[1]||r.result;
document.getElementById('fname').textContent=f.name;};r.readAsDataURL(f);}
file.onchange=e=>{if(e.target.files[0])read(e.target.files[0])};
['dragover','dragleave','drop'].forEach(ev=>drop.addEventListener(ev,e=>{e.preventDefault();
drop.classList.toggle('on',ev==='dragover');if(ev==='drop'&&e.dataTransfer.files[0])read(e.dataTransfer.files[0]);}));
document.getElementById('go').onclick=async()=>{if(!payload){out.textContent='pick a file first';return;}
out.textContent='matching fills…';
const res=await fetch('/api/audit',{method:'POST',headers:{'Content-Type':'application/json'},
body:JSON.stringify({data:payload})});
const j=await res.json();out.textContent=j.ok?j.report:'error: '+j.error;};
</script></body></html>"""


def _page() -> str:
    pro = licensing.is_pro()
    lock = "" if pro else ('<div class="lock">Free tier: PnL, hit rate, profit factor, expectancy. '
                           'Pro adds the findings engine, hour/symbol/direction buckets, R-multiples '
                           'and the HTML report. <a href="https://fillbook.gumroad.com">Get Pro</a></div>')
    return (PAGE.replace("__TIER__", "pro" if pro else "free")
            .replace("__VERSION__", __version__).replace("__LOCK__", lock))


def _run(body: dict) -> dict:
    pro = licensing.is_pro()
    raw = body.get("data", "")
    blob = base64.b64decode(raw.split(",")[-1])
    tmp = Path(tempfile.mkdtemp()) / "fills.csv"
    tmp.write_bytes(blob)

    fills = data.load_fills(tmp)
    closed = matching.match(fills)
    stats = analytics.summary(closed)
    verdict = analytics.score(stats)

    lines = [f"{len(fills)} fills → {stats['trades']} round trips", "",
             f"net PnL        {stats['net']:>12,.2f}",
             f"gross / fees   {stats['gross']:>12,.2f} / {stats['fees']:,.2f}",
             f"win rate       {stats['win_rate'] * 100:>11.1f}%",
             f"profit factor  {stats['profit_factor']:>12.2f}",
             f"expectancy     {stats['expectancy']:>12,.2f} per trade",
             f"score          {verdict['score']:>12.0f}/100  {verdict['verdict']}"]
    if pro:
        lines.append("")
        lines.append(analytics.buckets(closed, "direction").to_string(index=False))
        for item in analytics.insights(closed, stats, pro=True):
            lines.append(f"[{item['tone']}] {item['title']} — {item['detail']}")
    else:
        lines.append("")
        lines.append("(findings engine and buckets are Pro)")
    return {"ok": True, "report": "\n".join(lines)}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _send(self, code: int, body: str, ctype: str = "text/html; charset=utf-8"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body.encode())))
        self.end_headers()
        self.wfile.write(body.encode())

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self._send(200, _page())
        else:
            self._send(404, "not found", "text/plain")

    def do_POST(self):
        if self.path != "/api/audit":
            self._send(404, "not found", "text/plain")
            return
        length = int(self.headers.get("Content-Length", 0))
        try:
            payload = _run(json.loads(self.rfile.read(length) or b"{}"))
            status = 200
        except Exception as exc:
            payload = {"ok": False, "error": str(exc)}
            status = 400
        self._send(status, json.dumps(payload), "application/json")


def serve(host: str = "127.0.0.1", port: int = 8766) -> None:
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"FillBook UI on http://{host}:{port}  (Ctrl-C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        server.server_close()
