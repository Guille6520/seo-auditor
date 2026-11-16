"""Graba el vídeo de demostración (docs/demo.mp4 y docs/demo.gif).

Ejecuta de verdad el auditor contra el sitio de demo/sitio.py (versión 'antes' y
'despues'), y graba con un navegador sin cabeza una terminal simulada que muestra
los comandos y su salida real, seguida de los informes HTML generados.

Requisitos solo para grabar (no son dependencias del auditor):
    pip install playwright imageio-ffmpeg && python -m playwright install chromium
    python demo/grabar_video.py
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

import imageio_ffmpeg
from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).parent))
import sitio  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SIZE = {"width": 1280, "height": 720}

TERMINAL = """<!doctype html><html lang="es"><head><meta charset="utf-8"><style>
html,body{margin:0;height:100%;background:#0d1117;color:#e6edf3;font:19px/1.5 Consolas,'Courier New',monospace}
#bar{background:#161b22;padding:10px 18px;color:#8b949e;font:15px/1 'Segoe UI',sans-serif;border-bottom:1px solid #30363d}
#t{padding:18px 26px;height:calc(100% - 76px);overflow:hidden;white-space:pre-wrap;word-break:break-word;box-sizing:border-box}
.cap{color:#58a6ff;font:600 24px/1.6 'Segoe UI',sans-serif;display:block;margin:6px 0 10px}
.p{color:#3fb950}.o{color:#c9d1d9}.cur{background:#e6edf3;color:#0d1117}
</style></head><body><div id="bar">seo-auditor &mdash; demostración</div><div id="t"></div><script>
const steps=__STEPS__;const t=document.getElementById('t');
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const down=()=>{t.scrollTop=t.scrollHeight};
(async()=>{for(const s of steps){
 if(s.k==='cap'){const e=document.createElement('span');e.className='cap';e.textContent=s.t;t.appendChild(e);await sleep(1400)}
 if(s.k==='cmd'){const p=document.createElement('span');p.className='p';p.textContent='> ';t.appendChild(p);
  const e=document.createElement('span');t.appendChild(e);
  for(const ch of s.t){e.textContent+=ch;down();await sleep(28)}
  t.appendChild(document.createTextNode('\\n'));await sleep(700)}
 if(s.k==='out'){for(const line of s.t.split('\\n')){const e=document.createElement('span');e.className='o';
  e.textContent=line+'\\n';t.appendChild(e);down();await sleep(s.d||90)}await sleep(s.w||1800)}
}window.done=true})();
</script></body></html>"""

BANNER = """(text) => { const d = document.createElement('div'); d.textContent = text;
d.style.cssText = 'position:fixed;left:0;right:0;bottom:0;z-index:99999;background:#0d1117;color:#fff;' +
'font:600 22px/1 Segoe UI,sans-serif;padding:16px 26px;text-align:center'; document.body.appendChild(d); }"""


def run_cli(args: list[str], cwd: Path) -> str:
    """Ejecuta `seo-auditor` de verdad y devuelve su salida."""
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    proc = subprocess.run([sys.executable, "-m", "seo_auditor.cli", *args], cwd=cwd, env=env,
                          capture_output=True, text=True, encoding="utf-8")
    return (proc.stdout + proc.stderr).strip()


def audit_version(version: str, work: Path) -> str:
    """Levanta el sitio de demo en la versión dada, lo audita y lo apaga."""
    server = sitio.make_server(version)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        return run_cli(["audit", sitio.BASE, "--allow-private", "--delay", "0",
                        "--out", f"informes/{version}"], work)
    finally:
        server.shutdown()
        server.server_close()


def terminal_page(work: Path, name: str, steps: list[dict]) -> str:
    """Escribe una página de terminal simulada con los pasos dados y devuelve su URL."""
    path = work / name
    path.write_text(TERMINAL.replace("__STEPS__", json.dumps(steps)), encoding="utf-8")
    return path.as_uri()


def show_report(page, path: Path, banner: str) -> None:
    """Abre un informe HTML y lo recorre despacio."""
    page.goto(path.as_uri())
    page.evaluate(BANNER, banner)
    page.wait_for_timeout(2600)
    for _ in range(26):
        page.mouse.wheel(0, 70)
        page.wait_for_timeout(170)
    page.wait_for_timeout(1500)


def main() -> None:
    work = Path(tempfile.mkdtemp(prefix="seo-demo-"))
    out_before = audit_version("antes", work)
    out_after = audit_version("despues", work)
    out_compare = run_cli(["compare", "informes/antes/informe.json", "informes/despues/informe.json"], work)
    nota = {v: json.loads((work / "informes" / v / "informe.json").read_text(encoding="utf-8"))["nota"]
            for v in ("antes", "despues")}
    cmd = f"seo-auditor audit {sitio.BASE} --allow-private --out informes/"

    part1 = terminal_page(work, "t1.html", [
        {"k": "cap", "t": "1. Auditamos un sitio de ejemplo con fallos"},
        {"k": "cmd", "t": cmd + "antes"},
        {"k": "out", "t": out_before, "w": 2200},
    ])
    part2 = terminal_page(work, "t2.html", [
        {"k": "cap", "t": "2. Corregimos los fallos y volvemos a auditar"},
        {"k": "cmd", "t": cmd + "despues"},
        {"k": "out", "t": out_after, "w": 1500},
        {"k": "cap", "t": "3. Comparamos antes y después"},
        {"k": "cmd", "t": "seo-auditor compare informes/antes/informe.json informes/despues/informe.json"},
        {"k": "out", "t": out_compare, "d": 110, "w": 3500},
    ])

    video_dir = work / "video"
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(viewport=SIZE, record_video_dir=str(video_dir),
                                      record_video_size=SIZE, color_scheme="light")
        page = context.new_page()
        page.goto(part1)
        page.wait_for_function("window.done === true", timeout=120_000)
        show_report(page, work / "informes" / "antes" / "informe.html",
                    f"Informe HTML del sitio con fallos: {nota['antes']}/100")
        page.goto(part2)
        page.wait_for_function("window.done === true", timeout=120_000)
        show_report(page, work / "informes" / "despues" / "informe.html",
                    f"Informe HTML tras las correcciones: {nota['despues']}/100")
        context.close()
        browser.close()

    webm = next(video_dir.glob("*.webm"))
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    docs = ROOT / "docs"
    mp4, gif = docs / "demo.mp4", docs / "demo.gif"
    subprocess.run([ffmpeg, "-y", "-loglevel", "error", "-i", str(webm), "-c:v", "libx264", "-crf", "26",
                    "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(mp4)], check=True)
    subprocess.run([ffmpeg, "-y", "-loglevel", "error", "-i", str(webm), "-vf",
                    "fps=6,scale=800:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=64[p];[b][p]paletteuse=dither=none",
                    str(gif)], check=True)
    # Ejemplos de informe para enlazar desde el README.
    examples = docs / "ejemplo"
    examples.mkdir(exist_ok=True)
    for version in ("antes", "despues"):
        for ext in ("html", "md", "json"):
            shutil.copy(work / "informes" / version / f"informe.{ext}", examples / f"informe-{version}.{ext}")
    (examples / "comparacion.md").write_text(out_compare + "\n", encoding="utf-8")
    print(f"Vídeo: {mp4} ({mp4.stat().st_size // 1024} KB)  GIF: {gif} ({gif.stat().st_size // 1024} KB)")
    print(f"Notas: antes {nota['antes']}, después {nota['despues']}")


if __name__ == "__main__":
    main()
