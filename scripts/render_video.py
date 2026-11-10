"""
Gera um Reels animado (MP4 1080x1920, 30 fps, H.264 + AAC) a partir de um spec JSON.

Uso:  python scripts/render_video.py queue/<pasta>/spec.json
Saída: queue/<pasta>/video.mp4, queue/<pasta>/cover.jpg e atualiza post.json
       ("video", "cover", "images": ["cover.jpg"], "format": "reels").

Spec: mesmos campos dos posts (title, scheduled_at, caption, sources) + "scenes":
  hook       tag, title, subtitle
  point      n, title, body (linhas separadas por \\n)
  big        kicker, figure (o 1º número conta de 0 até o valor), statement, body,
             compare (opcional: [[rótulo, valor exibido, número], ...] vira barras; a última fica dourada)
  checklist  title, items[]
  cta        title, body
  Campo opcional "dur" (segundos) em cada cena; sem ele a duração sai do tamanho do texto.
  Campo opcional "note" (base legal) em point/big/checklist.
  Campo opcional "speech" (fala da narração) em cada cena.
Marcação: **texto** = destaque dourado.
A trilha é sintetizada aqui mesmo (sem direitos de terceiros).

Narração (voz sintética): no spec, "narration": "sintetica" e "speech" nas cenas.
  Cada fala é gerada por TTS local, entra 0,35 s depois do corte da cena e a trilha baixa
  (ducking) enquanto a voz fala. Se a fala for maior que a cena, a cena estica para caber.
  Motor: Piper (voz neural) se houver modelo .onnx em brand/voices/ ou em TRIBUTA_PIPER_VOICE;
  senão espeak-ng com voz MBROLA brasileira (TRIBUTA_ESPEAK_VOICE, padrão mb-br3; sem MBROLA, pt-br).
  Dependências do fallback: apt-get install espeak-ng mbrola mbrola-br3
  "paga" e "propria" ainda não estão implementadas: caem na sintética, com aviso.
  O post.json recebe "narration": [{"shows", "text"}] e "narration_engine".
"""
import html
import json
import math
import re
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

import numpy as np
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
FONTS = ROOT / "brand" / "fonts"
LOGO = (ROOT / "brand" / "logo.svg").read_text()
FPS = 30
W, H = 1080, 1920

CSS = f"""
@font-face {{ font-family: Inter; src: url('file://{FONTS}/Inter-Regular.otf'); font-weight: 400; }}
@font-face {{ font-family: Inter; src: url('file://{FONTS}/Inter-SemiBold.otf'); font-weight: 600; }}
@font-face {{ font-family: Inter; src: url('file://{FONTS}/Inter-Bold.otf'); font-weight: 700; }}
@font-face {{ font-family: Display; src: url('file://{FONTS}/InterDisplay-ExtraBold.otf'); font-weight: 800; }}
@font-face {{ font-family: Display; src: url('file://{FONTS}/InterDisplay-Black.otf'); font-weight: 900; }}
@font-face {{ font-family: Lora; src: url('file://{FONTS}/Lora-Italic-Variable.ttf'); font-style: italic; }}
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
html, body {{ width: {W}px; height: {H}px; overflow: hidden; background: #0E3B2E; }}
body {{ font-family: Inter; -webkit-font-smoothing: antialiased; color: #F6F1E6; }}
.scene {{ position: absolute; inset: 0; padding: 330px 150px 0 90px; display: flex; flex-direction: column; opacity: 0; }}
.scene.dark {{ background: #0E3B2E; color: #F6F1E6; }}
.scene.light {{ background: #F6F1E6; color: #13221C; }}
em {{ font-style: normal; }}
.dark em {{ color: #E8B931; }}
.light em {{ color: #0E3B2E; font-weight: 700; padding: .02em .16em; margin: 0 -.06em; border-radius: .16em;
  background: #E8B931;
  -webkit-box-decoration-break: clone; box-decoration-break: clone; }}
.light h1 em, .light h2 em {{ font-weight: inherit; padding: 0 .14em; margin: 0 -.14em; border-radius: .1em; }}
.light .w:has(em) {{ position: relative; z-index: 0; }}
.a {{ opacity: 0; will-change: transform, opacity; }}
.tag {{ align-self: flex-start; font-weight: 700; font-size: 34px; letter-spacing: 4px; text-transform: uppercase;
  padding: 16px 28px; border-radius: 999px; border: 3px solid currentColor; margin-bottom: 56px; }}
.dark .tag {{ color: #E8B931; }} .light .tag {{ color: #0E3B2E; }}
h1 {{ font-family: Display; font-weight: 900; font-size: 120px; line-height: 1.0; letter-spacing: -3.5px; }}
h1 .w, h2 .w {{ display: inline-block; }}
h2 {{ font-family: Display; font-weight: 800; font-size: 96px; line-height: 1.04; letter-spacing: -2.5px; margin-bottom: 56px; }}
.sub {{ font-size: 50px; line-height: 1.35; margin-top: 56px; opacity: .9; }}
.body p {{ font-size: 54px; line-height: 1.36; }}
.body p + p {{ margin-top: 34px; }}
.num {{ font-family: Display; font-weight: 900; font-size: 230px; line-height: .8; color: #E8B931; margin-bottom: 44px; letter-spacing: -8px; }}
.light .num {{ color: #C99A14; }}
.kicker {{ font-weight: 700; font-size: 38px; letter-spacing: 4px; text-transform: uppercase; color: #E8B931; margin-bottom: 26px; }}
.figure {{ font-family: Display; font-weight: 900; font-size: 210px; line-height: .95; letter-spacing: -7px; color: #E8B931; margin-bottom: 40px; white-space: nowrap; }}
.statement {{ font-family: Display; font-weight: 800; font-size: 76px; line-height: 1.08; letter-spacing: -2px; margin-bottom: 44px; }}
.items {{ list-style: none; }}
.items li {{ display: flex; gap: 30px; align-items: flex-start; font-size: 50px; line-height: 1.28; padding: 26px 0; border-bottom: 3px solid #D9D1BF; }}
.items li:last-child {{ border-bottom: 0; }}
.box {{ flex: 0 0 56px; height: 56px; border-radius: 14px; background: #0E3B2E; display: grid; place-items: center; margin-top: 2px; }}
.box svg {{ width: 34px; height: 34px; }}
.note {{ position: absolute; left: 90px; right: 150px; bottom: 470px; padding-top: 24px; border-top: 3px solid; font-size: 32px; line-height: 1.35; }}
.dark .note {{ border-color: #ffffff2e; color: #DCE9DF; }} .light .note {{ border-color: #D9D1BF; color: #5B6B63; }}
.note b {{ font-weight: 700; }}
.quote {{ font-family: Lora; font-style: italic; font-size: 54px; line-height: 1.4; opacity: .92; margin-bottom: 50px; }}
.cta-list {{ display: grid; gap: 30px; }}
.cta-list > div {{ font-size: 54px; display: flex; gap: 28px; align-items: center; }}
.cta-list span {{ width: 84px; height: 84px; border-radius: 22px; background: #E8B931; color: #0E3B2E; display: grid; place-items: center;
  font-family: Display; font-weight: 900; font-size: 44px; flex: none; }}
.cmp {{ display: grid; gap: 30px; margin-top: 10px; }}
.cmp .lab {{ display: flex; justify-content: space-between; font-size: 40px; font-weight: 600; margin-bottom: 12px; opacity: .92; }}
.cmp .lab b {{ font-family: Display; font-weight: 900; font-size: 46px; }}
.cmp .track {{ height: 44px; border-radius: 12px; background: #F6F1E61f; overflow: hidden; }}
.cmp .fill {{ height: 100%; width: 0; border-radius: 12px; background: #F6F1E6a6; }}
.cmp .row:last-child .fill {{ background: #E8B931; }} .cmp .row:last-child .lab b {{ color: #E8B931; }}
#chrome {{ position: absolute; inset: 0; pointer-events: none; }}
.brand {{ position: absolute; left: 90px; top: 200px; display: flex; align-items: center; gap: 20px; font-family: Display; font-weight: 800; font-size: 42px; letter-spacing: -.5px; }}
.brand svg {{ width: 72px; height: 72px; }}
.brand .b2 {{ color: #E8B931; }}
.bars {{ position: absolute; left: 90px; right: 150px; top: 120px; display: flex; gap: 10px; }}
.bars div {{ flex: 1; height: 8px; border-radius: 4px; background: #F6F1E640; overflow: hidden; }}
.bars i {{ display: block; height: 100%; width: 0; background: #E8B931; }}
.handle {{ position: absolute; left: 90px; bottom: 400px; font-weight: 700; font-size: 34px; letter-spacing: .5px; }}
#ring {{ position: absolute; width: 760px; height: 760px; border-radius: 50%; border: 90px solid #E8B931; opacity: .07; }}
"""
CHECK = '<svg viewBox="0 0 24 24"><path d="M5 12.5l4.5 4.5L19 7.5" fill="none" stroke="#E8B931" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round"/></svg>'

JS = """
const ease = x => 1 - Math.pow(1 - Math.min(1, Math.max(0, x)), 3);
let S = [];
function setup(scenes) { S = scenes; }
function fmt(v, dec) { return dec ? v.toFixed(1).replace('.', ',') : Math.round(v).toLocaleString('pt-BR'); }
function setTime(t) {
  const total = S[S.length - 1].end;
  document.querySelectorAll('.bars i').forEach((b, i) => {
    const s = S[i]; b.style.width = (Math.min(1, Math.max(0, (t - s.start) / (s.end - s.start))) * 100) + '%';
  });
  const ring = document.getElementById('ring');
  ring.style.left = (520 + 120 * Math.sin(t / 3.1)) + 'px'; ring.style.top = (900 + 90 * Math.cos(t / 2.7)) + 'px';
  let lightOn = false;
  S.forEach((s, i) => {
    const el = document.getElementById('s' + i);
    const local = t - s.start, d = s.end - s.start, last = i === S.length - 1;
    let o = 0, y = 0;
    if (local >= 0 && (local < d || last)) {
      o = ease(local / 0.35);
      if (!last && local > d - 0.35) { const k = ease((local - (d - 0.35)) / 0.35); o = 1 - k; y = -60 * k; }
    }
    el.style.opacity = o; el.style.transform = `translateY(${y}px)`;
    if (o > 0.5 && el.classList.contains('light')) lightOn = true;
    el.querySelectorAll('.a').forEach(a => {
      const p = ease((local - parseFloat(a.dataset.in)) / 0.5);
      a.style.opacity = p; a.style.transform = `translateY(${(1 - p) * 50}px)`;
    });
    el.querySelectorAll('.fill').forEach(f => {
      const p = ease((local - parseFloat(f.dataset.in)) / 0.9);
      f.style.width = (parseFloat(f.dataset.w) * p) + '%';
    });
    el.querySelectorAll('[data-count]').forEach(c => {
      const target = parseFloat(c.dataset.count), dec = c.dataset.dec === '1';
      const p = ease((local - parseFloat(c.dataset.in)) / 1.1);
      c.textContent = fmt(target * p, dec);
    });
  });
  document.getElementById('chrome').style.color = lightOn ? '#13221C' : '#F6F1E6';
  document.querySelectorAll('.bars div').forEach(b => b.style.background = lightOn ? '#13221C26' : '#F6F1E640');
}
"""


def md(text):
    t = html.escape(text or "")
    return re.sub(r"\*\*(.+?)\*\*", r"<em>\1</em>", t)


def words(text, start, step=0.07):
    """Quebra o título em palavras animadas uma a uma (mantém os destaques)."""
    out, t = [], start
    for part in re.split(r"(\*\*.+?\*\*)", text or ""):
        if not part:
            continue
        hl = part.startswith("**")
        ws = (part[2:-2] if hl else part).split()
        if not hl and ws and out and not part[0].isspace():  # pontuação colada ao destaque ("**11,3%**:")
            out[-1] = out[-1][:-len("</span>")] + html.escape(ws.pop(0)) + "</span>"
        for w in ws:
            inner = f"<em>{html.escape(w)}</em>" if hl else html.escape(w)
            out.append(f'<span class="w a" data-in="{t:.2f}">{inner}</span>')
            t += step
    return " ".join(out), t


def count_words(s):
    txt = " ".join(str(v) for k, v in s.items() if k not in ("type", "dur", "n", "speech") and isinstance(v, str))
    txt += " ".join(s.get("items", []))
    return len(re.sub(r"\*", "", txt).split())


def scene_html(s, i):
    t = s["type"]
    theme = s.get("theme") or ("light" if t in ("point", "checklist") else "dark")
    parts, at = [], 0.25
    if t == "hook":
        if s.get("tag"):
            parts.append(f'<div class="tag a" data-in="{at:.2f}">{md(s["tag"])}</div>'); at += 0.2
        w, at = words(s["title"], at); parts.append(f"<h1>{w}</h1>")
        if s.get("subtitle"):
            parts.append(f'<div class="sub a" data-in="{at + 0.2:.2f}">{md(s["subtitle"])}</div>')
    elif t == "point":
        if s.get("n"):
            parts.append(f'<div class="num a" data-in="{at:.2f}">{md(str(s["n"]))}</div>'); at += 0.2
        w, at = words(s["title"], at); parts.append(f"<h2>{w}</h2>")
        ps = "".join(f'<p class="a" data-in="{at + 0.25 + k * 0.45:.2f}">{md(line)}</p>'
                     for k, line in enumerate(x for x in s.get("body", "").split("\n") if x.strip()))
        parts.append(f'<div class="body">{ps}</div>')
    elif t == "big":
        parts.append(f'<div class="kicker a" data-in="{at:.2f}">{md(s.get("kicker", ""))}</div>')
        fig = html.escape(s["figure"])
        m = re.search(r"\d+(?:[.,]\d+)?", s["figure"])
        if m:
            raw = m.group(0)
            dec = "," in raw
            val = float(raw.replace(".", "").replace(",", ".")) if dec else float(raw.replace(".", ""))
            fig = (html.escape(s["figure"][:m.start()]) + f'<span data-count="{val}" data-dec="{1 if dec else 0}" data-in="{at + 0.15:.2f}">0</span>'
                   + html.escape(s["figure"][m.end():]))
        parts.append(f'<div class="figure a" data-in="{at + 0.1:.2f}">{fig}</div>')
        parts.append(f'<div class="statement a" data-in="{at + 1.2:.2f}">{md(s["statement"])}</div>')
        if s.get("body"):
            parts.append(f'<div class="body"><p class="a" data-in="{at + 1.8:.2f}">{md(s["body"])}</p></div>')
        if s.get("compare"):  # barras comparativas: [[rótulo, valor exibido, número], ...]
            top = max(float(c[2]) for c in s["compare"])
            rows = "".join(f'<div class="row a" data-in="{at + 1.8 + k * 0.4:.2f}"><div class="lab"><span>{md(c[0])}</span><b>{html.escape(c[1])}</b></div>'
                           f'<div class="track"><div class="fill" data-in="{at + 2.0 + k * 0.4:.2f}" data-w="{float(c[2]) / top * 100:.1f}"></div></div></div>'
                           for k, c in enumerate(s["compare"]))
            parts.append(f'<div class="cmp">{rows}</div>')
    elif t == "checklist":
        w, at = words(s["title"], at); parts.append(f"<h2>{w}</h2>")
        lis = "".join(f'<li class="a" data-in="{at + 0.3 + k * 0.45:.2f}"><div class="box">{CHECK}</div><div>{md(x)}</div></li>'
                      for k, x in enumerate(s["items"]))
        parts.append(f'<ul class="items">{lis}</ul>')
    elif t == "cta":
        w, at = words(s["title"], at); parts.append(f"<h2>{w}</h2>")
        if s.get("body"):
            parts.append(f'<div class="quote a" data-in="{at + 0.2:.2f}">{md(s["body"])}</div>'); at += 0.3
        acts = [list(a) for a in s.get("actions", [["1", "**Salve** para consultar depois"], ["2", "**Envie** para quem opera cripto"], ["3", "**Siga** @tributalizando"]])]
        if not any("siga" in str(v).lower() for _, v in acts):  # gancho para seguir sempre no fim
            acts.append([str(len(acts) + 1), "**Siga** @tributalizando"])
        parts.append('<div class="cta-list">' + "".join(
            f'<div class="a" data-in="{at + 0.3 + k * 0.3:.2f}"><span>{n}</span><div>{md(v)}</div></div>' for k, (n, v) in enumerate(acts)) + "</div>")
    else:
        raise ValueError(f"tipo de cena desconhecido: {t}")
    if s.get("note"):
        parts.append(f'<div class="note a" data-in="{at + 0.6:.2f}"><b>Base:</b> {md(s["note"])}</div>')
    return f'<section class="scene {theme}" id="s{i}">{"".join(parts)}</section>'


VOICE_IN = 0.35   # a fala começa este tanto depois do corte
VOICE_TAIL = 0.6  # respiro depois da fala antes do próximo corte
SR = 44100


def timeline(scenes, voice_lens=None):
    out, t = [], 0.0
    for k, s in enumerate(scenes):
        d = s.get("dur") or max(3.5, min(8.0, 2.0 + count_words(s) * 0.33))
        if s["type"] == "cta":
            d = max(d, 4.5)
        if voice_lens and voice_lens[k]:
            d = max(d, VOICE_IN + voice_lens[k] + VOICE_TAIL)
        out.append({"start": round(t, 3), "end": round(t + d, 3)})
        t += d
    return out


def speakable(text):
    """Ajustes mínimos para a voz: tira marcação e lê símbolos como se fala."""
    t = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    t = re.sub(r"(\d),(\d)", r"\1 vírgula \2", t)
    t = t.replace("%", " por cento").replace("R$", "").replace("@", "")
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _piper_model():
    import os
    env = os.environ.get("TRIBUTA_PIPER_VOICE")
    if env and Path(env).exists():
        return Path(env)
    found = sorted((ROOT / "brand" / "voices").glob("*.onnx")) if (ROOT / "brand" / "voices").exists() else []
    return found[0] if found else None


def _read_wav(path):
    with wave.open(str(path), "rb") as w:
        sr, ch, sw = w.getframerate(), w.getnchannels(), w.getsampwidth()
        raw = w.readframes(w.getnframes())
    a = np.frombuffer(raw, dtype=np.int16).astype(np.float64) / 32768
    if ch > 1:
        a = a.reshape(-1, ch).mean(axis=1)
    if sr != SR:  # reamostra por interpolação linear
        n = int(len(a) * SR / sr)
        a = np.interp(np.linspace(0, len(a) - 1, n), np.arange(len(a)), a)
    return a


def _trim(a, thr=0.01):
    idx = np.where(np.abs(a) > thr)[0]
    return a[max(0, idx[0] - 400): idx[-1] + 800] if len(idx) else a[:0]


def tts(texts, tmp):
    """Gera a fala de cada cena. Devolve (lista de arrays float a 44,1 kHz ou None, nome do motor)."""
    import os
    import shutil
    model = _piper_model()
    out, engine = [], None
    voice = None
    if model:
        try:
            from piper import PiperVoice
            voice = PiperVoice.load(str(model))
            engine = f"piper:{model.stem}"
        except Exception as e:  # sem piper instalado: cai no espeak
            print(f"aviso: Piper indisponível ({e}); usando espeak-ng")
    if voice is None:
        if not shutil.which("espeak-ng"):
            raise RuntimeError("narração pedida, mas não há motor de voz: instale espeak-ng (e mbrola-br3) ou um modelo Piper")
        ev = os.environ.get("TRIBUTA_ESPEAK_VOICE", "mb-br3")
        if ev.startswith("mb-") and not Path(f"/usr/share/mbrola/{ev[3:]}").exists():
            ev = "pt-br"
        engine = f"espeak-ng:{ev}"
    for k, text in enumerate(texts):
        if not text or not text.strip():
            out.append(None)
            continue
        f = Path(tmp) / f"voz{k:02d}.wav"
        if voice is not None:
            with wave.open(str(f), "wb") as w:
                voice.synthesize_wav(speakable(text), w)
        else:
            subprocess.run(["espeak-ng", "-v", ev, "-s", "160", "-g", "4", "-w", str(f), speakable(text)], check=True)
        out.append(_trim(_read_wav(f)))
    return out, engine


def soundtrack(path, total, cuts, voices=None):
    """Trilha leve sintetizada: pad Am–F–C–G, batida suave e 'whoosh' nas trocas de cena.
    voices: [(início em s, array da fala)] — mixa a narração por cima, com a trilha baixando sob a voz."""
    sr = SR
    n = int(total * sr)
    t = np.arange(n) / sr
    bpm, beat = 92, 60 / 92
    bar = beat * 4
    chords = [[220.0, 261.63, 329.63], [174.61, 220.0, 261.63], [261.63, 329.63, 392.0], [196.0, 246.94, 293.66]]
    mix = np.zeros(n)
    for k in range(int(total / bar) + 1):
        a, b = int(k * bar * sr), min(n, int((k + 1) * bar * sr))
        if a >= n:
            break
        tt = t[a:b] - k * bar
        env = np.minimum(1, tt / 0.6) * np.minimum(1, (bar - tt) / 0.6)
        for f in chords[k % 4]:
            mix[a:b] += env * (np.sin(2 * np.pi * f * tt) + 0.25 * np.sin(2 * np.pi * 2 * f * tt + 0.3)) * 0.05
            mix[a:b] += env * np.sin(2 * np.pi * f / 2 * tt) * 0.03
    rng = np.random.default_rng(7)
    for k in range(int(total / beat) + 1):
        a = int(k * beat * sr)
        if a >= n:
            break
        if k % 2 == 0:
            ln = min(n - a, int(0.28 * sr)); tt = np.arange(ln) / sr
            freq = 50 + 70 * np.exp(-tt * 30)
            mix[a:a + ln] += np.sin(2 * np.pi * np.cumsum(freq) / sr) * np.exp(-tt * 14) * 0.22
        h = int((k + 0.5) * beat * sr)
        if h < n:
            ln = min(n - h, int(0.05 * sr))
            noise = rng.standard_normal(ln); noise = np.diff(np.concatenate([[0], noise]))
            mix[h:h + ln] += noise * np.exp(-np.arange(ln) / sr * 80) * 0.025
    for c in cuts:
        a = int(max(0, c - 0.3) * sr); ln = min(n - a, int(0.45 * sr))
        if ln <= 0:
            continue
        tt = np.arange(ln) / ln
        noise = np.convolve(rng.standard_normal(ln), np.ones(12) / 12, mode="same")
        mix[a:a + ln] += noise * np.sin(np.pi * tt) ** 2 * 0.08
    fade = np.minimum(1, t / 0.6) * np.minimum(1, (total - t) / 1.2)
    mix *= fade
    mix = mix / (np.max(np.abs(mix)) + 1e-9) * 0.55
    if voices:
        vo = np.zeros(n)
        duck = np.zeros(n)
        for start, a in voices:
            i = int(start * sr); ln = min(len(a), n - i)
            if ln <= 0:
                continue
            vo[i:i + ln] += a[:ln] / (np.max(np.abs(a)) + 1e-9) * 0.9
            duck[max(0, i - int(0.2 * sr)): i + ln + int(0.3 * sr)] = 1
        k = int(0.25 * sr)  # suaviza a entrada/saída do ducking
        duck = np.convolve(duck, np.ones(k) / k, mode="same")
        mix = mix * (1 - 0.72 * duck) + vo
        mix = mix / max(1.0, np.max(np.abs(mix)) / 0.95)
    pcm = (mix * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr); w.writeframes(pcm.tobytes())


def render(spec_path):
    spec_path = Path(spec_path).resolve()
    folder = spec_path.parent
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    scenes = spec["scenes"]
    mode = spec.get("narration", "nenhuma")
    if isinstance(mode, list):  # narração já no formato do post.json: [{shows, text}]
        for s, nar in zip(scenes, mode):
            s["speech"] = nar.get("text", "")
        mode = "sintetica"
    voices, engine = None, None
    if mode and mode != "nenhuma" and any((s.get("speech") or "").strip() for s in scenes):
        if mode != "sintetica":
            print(f"aviso: narração '{mode}' ainda não implementada; usando voz sintética")
        with tempfile.TemporaryDirectory() as vt:
            voices, engine = tts([s.get("speech", "") for s in scenes], vt)
    elif mode and mode != "nenhuma":
        print("aviso: narração pedida, mas nenhuma cena tem 'speech'; vídeo sai sem voz")
    tl = timeline(scenes, [len(v) / SR if v is not None else 0 for v in voices] if voices else None)
    total = tl[-1]["end"]
    doc = build_doc(scenes)
    placed = [(tl[k]["start"] + VOICE_IN, v) for k, v in enumerate(voices) if v is not None] if voices else None
    _render_files(spec, folder, tl, total, doc, placed, engine)


def build_doc(scenes):
    bars = "".join("<div><i></i></div>" for _ in scenes)
    return (f'<!doctype html><html><head><meta charset="utf-8"><style>{CSS}</style></head><body>'
           f'<div id="ring"></div>{"".join(scene_html(s, i) for i, s in enumerate(scenes))}'
           f'<div id="chrome"><div class="bars">{bars}</div>'
           f'<div class="brand">{LOGO}<span>tributa<span class="b2">lizando</span></span></div>'
           f'<div class="handle">@tributalizando</div></div>'
           f'<script>{JS}</script></body></html>')


def preview(spec_path, times, out_dir):
    """Salva quadros (JPEG) nos instantes pedidos, para conferir as cenas sem gerar o vídeo."""
    spec = json.loads(Path(spec_path).read_text(encoding="utf-8"))
    tl = timeline(spec["scenes"])
    out_dir = Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        f = Path(tmp) / "reel.html"; f.write_text(build_doc(spec["scenes"]), encoding="utf-8")
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--allow-file-access-from-files"])
            page = browser.new_page(viewport={"width": W, "height": H}, device_scale_factor=1)
            page.goto(f.as_uri()); page.evaluate("document.fonts.ready"); page.evaluate(f"setup({json.dumps(tl)})")
            if not times:  # fim de cada cena, com tudo já animado
                times = [s["end"] - 0.45 for s in tl]
            for k, t in enumerate(times):
                page.evaluate(f"setTime({t})"); page.screenshot(path=str(out_dir / f"frame{k:02d}.jpg"), type="jpeg", quality=88)
            browser.close()


def _render_files(spec, folder, tl, total, doc, voices=None, engine=None):
    scenes = spec["scenes"]
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        page_file = tmp / "reel.html"
        page_file.write_text(doc, encoding="utf-8")
        audio = tmp / "audio.wav"
        soundtrack(audio, total, [s["start"] for s in tl[1:]], voices)
        out = folder / "video.mp4"
        ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", str(FPS), "-c:v", "mjpeg", "-i", "-",
                               "-i", str(audio), "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
                               "-profile:v", "high", "-r", str(FPS), "-c:a", "aac", "-b:a", "128k", "-ar", "44100",
                               "-shortest", "-movflags", "+faststart", str(out)], stdin=subprocess.PIPE)
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--allow-file-access-from-files"])
            page = browser.new_page(viewport={"width": W, "height": H}, device_scale_factor=1)
            page.goto(page_file.as_uri())
            page.evaluate("document.fonts.ready")
            page.evaluate(f"setup({json.dumps(tl)})")
            frames = int(math.ceil(total * FPS))
            for f in range(frames):
                page.evaluate(f"setTime({f / FPS})")
                ff.stdin.write(page.screenshot(type="jpeg", quality=92))
            cover_t = min(tl[0]["end"] - 0.5, 2.6)
            page.evaluate(f"setTime({cover_t})")
            page.screenshot(path=str(folder / "cover.jpg"), type="jpeg", quality=92)
            browser.close()
        ff.stdin.close()
        if ff.wait() != 0:
            raise RuntimeError("ffmpeg falhou")
    post_file = folder / "post.json"
    post = json.loads(post_file.read_text(encoding="utf-8")) if post_file.exists() else {}
    post.update({k: spec[k] for k in ("scheduled_at", "caption", "title", "sources") if k in spec})
    post.update({"format": "reels", "video": "video.mp4", "cover": "cover.jpg", "images": ["cover.jpg"], "duration": round(total, 1)})
    if voices:
        post["narration"] = [{"shows": re.sub(r"\*\*", "", s.get("title") or s.get("figure") or s.get("statement") or ""),
                              "text": s.get("speech", "")} for s in scenes]
        post["narration_engine"] = engine
    else:
        post.pop("narration", None); post.pop("narration_engine", None)
    post.setdefault("status", "pending")
    post_file.write_text(json.dumps(post, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{folder.name}: Reels de {total:.1f}s" + (f", narração {engine}" if voices else ", sem narração"))


if __name__ == "__main__":
    if sys.argv[1:2] == ["--preview"]:  # python3 scripts/render_video.py --preview spec.json pasta_saida [t1 t2 ...]
        preview(sys.argv[2], [float(x) for x in sys.argv[4:]], sys.argv[3])
        sys.exit()
    for a in sys.argv[1:]:
        render(a)
