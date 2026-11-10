"""
Gera as artes (JPEG 1080x1350) de um post a partir de um spec JSON.

Uso:  python scripts/render.py queue/<pasta>/spec.json
Saída: queue/<pasta>/01.jpg, 02.jpg ... e atualiza "images" no post.json

Tipos de lâmina (campo "type"):
  cover      tag, title, subtitle, swipe(bool)
  point      n, title, body, note
  big        kicker, figure, statement, body
  checklist  title, items[], note
  cta        title, body, actions[] (o gancho "Siga @tributalizando" entra sozinho se faltar)
Marcação: **texto** = destaque dourado (em fundo verde) / verde (em fundo creme).
"""
import html
import json
import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
FONTS = ROOT / "brand" / "fonts"
LOGO = (ROOT / "brand" / "logo.svg").read_text()
HANDLE = "@tributalizando"

C = {
    "green": "#0E3B2E", "deep": "#082A20", "gold": "#E8B931", "cream": "#F6F1E6",
    "ink": "#13221C", "muted": "#5B6B63", "soft": "#DCE9DF", "line": "#D9D1BF",
}

CSS = f"""
@font-face {{ font-family: Inter; src: url('file://{FONTS}/Inter-Regular.otf'); font-weight: 400; }}
@font-face {{ font-family: Inter; src: url('file://{FONTS}/Inter-Medium.otf'); font-weight: 500; }}
@font-face {{ font-family: Inter; src: url('file://{FONTS}/Inter-SemiBold.otf'); font-weight: 600; }}
@font-face {{ font-family: Inter; src: url('file://{FONTS}/Inter-Bold.otf'); font-weight: 700; }}
@font-face {{ font-family: Display; src: url('file://{FONTS}/InterDisplay-Bold.otf'); font-weight: 700; }}
@font-face {{ font-family: Display; src: url('file://{FONTS}/InterDisplay-ExtraBold.otf'); font-weight: 800; }}
@font-face {{ font-family: Display; src: url('file://{FONTS}/InterDisplay-Black.otf'); font-weight: 900; }}
@font-face {{ font-family: Lora; src: url('file://{FONTS}/Lora-Italic-Variable.ttf'); font-style: italic; }}
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
html, body {{ width: 1080px; height: 1350px; }}
body {{ font-family: Inter; -webkit-font-smoothing: antialiased; }}
.slide {{ width: 1080px; height: 1350px; position: relative; overflow: hidden;
  padding: 96px 96px 0; display: flex; flex-direction: column; }}
.dark {{ background: {C['green']}; color: {C['cream']}; }}
.light {{ background: {C['cream']}; color: {C['ink']}; }}
.dark em {{ font-style: normal; color: {C['gold']}; }}
.light em {{ font-style: normal; color: {C['green']}; background: linear-gradient(transparent 62%, {C['gold']}88 62%); }}
.top {{ display: flex; align-items: center; justify-content: space-between; margin-bottom: 64px; }}
.brand {{ display: flex; align-items: center; gap: 18px; font-family: Display; font-weight: 800; font-size: 34px; letter-spacing: -0.5px; }}
.brand svg {{ width: 58px; height: 58px; }}
.dark .brand svg rect:first-child {{ fill: {C['gold']}; }}
.dark .brand svg rect:not(:first-child) {{ fill: {C['green']}; }}
.dark .brand svg circle:last-child {{ fill: {C['gold']}; }}
.dark .brand svg circle:first-of-type {{ fill: {C['green']}; }}
.brand .b2 {{ color: {C['gold']}; }}
.light .brand .b2 {{ color: #B98E12; }}
.pager {{ font-weight: 600; font-size: 26px; letter-spacing: 2px; opacity: .65; }}
.tag {{ align-self: flex-start; font-weight: 700; font-size: 26px; letter-spacing: 3px; text-transform: uppercase;
  padding: 14px 24px; border-radius: 999px; border: 2px solid currentColor; margin-bottom: 44px; }}
.dark .tag {{ color: {C['gold']}; }}
.light .tag {{ color: {C['green']}; }}
h1 {{ font-family: Display; font-weight: 900; font-size: 104px; line-height: 1.0; letter-spacing: -3px; }}
h2 {{ font-family: Display; font-weight: 800; font-size: 84px; line-height: 1.06; letter-spacing: -2px; margin-bottom: 40px; }}
.sub {{ font-size: 44px; line-height: 1.35; margin-top: 44px; opacity: .88; max-width: 860px; }}
.body {{ font-size: 46px; line-height: 1.4; }}
.body p + p {{ margin-top: 26px; }}
.body strong {{ font-weight: 700; }}
.num {{ font-family: Display; font-weight: 900; font-size: 190px; line-height: .8; color: {C['gold']}; margin-bottom: 36px; letter-spacing: -6px; }}
.light .num {{ color: #C99A14; }}
.kicker {{ font-weight: 700; font-size: 30px; letter-spacing: 3px; text-transform: uppercase; color: {C['gold']}; margin-bottom: 18px; }}
.light .kicker {{ color: {C['green']}; }}
.figure {{ font-family: Display; font-weight: 900; font-size: 190px; line-height: .95; letter-spacing: -6px; margin-bottom: 30px; }}
.dark .figure {{ color: {C['gold']}; }}
.light .figure {{ color: {C['green']}; }}
.statement {{ font-family: Display; font-weight: 800; font-size: 60px; line-height: 1.1; letter-spacing: -1.5px; margin-bottom: 40px; }}
.note {{ margin-top: auto; margin-bottom: 36px; padding-top: 26px; border-top: 2px solid; font-size: 28px; line-height: 1.4; display: flex; gap: 14px; }}
.dark .note {{ border-color: #ffffff2e; color: {C['soft']}; }}
.light .note {{ border-color: {C['line']}; color: {C['muted']}; }}
.note b {{ font-weight: 700; white-space: nowrap; }}
.items {{ list-style: none; }}
.items li {{ display: flex; gap: 26px; align-items: flex-start; font-size: 42px; line-height: 1.32; padding: 22px 0; border-bottom: 2px solid {C['line']}; }}
.items li:last-child {{ border-bottom: 0; }}
.box {{ flex: 0 0 44px; height: 44px; border-radius: 12px; background: {C['green']}; display: grid; place-items: center; margin-top: 2px; }}
.box svg {{ width: 26px; height: 26px; }}
.foot {{ height: 120px; margin: 0 -96px; padding: 0 96px; display: flex; align-items: center; justify-content: space-between;
  font-weight: 600; font-size: 28px; }}
.dark .foot {{ background: {C['deep']}; color: {C['soft']}; }}
.light .foot {{ background: {C['green']}; color: {C['cream']}; }}
.swipe {{ display: flex; align-items: center; gap: 14px; color: {C['gold']}; font-weight: 700; }}
.spacer {{ flex: 1; }}
.deco {{ position: absolute; right: -140px; top: 520px; width: 620px; height: 620px; border-radius: 50%;
  border: 70px solid {C['gold']}; opacity: .08; }}
.cta-list {{ margin-top: 40px; display: grid; gap: 22px; }}
.cta-list div {{ font-size: 44px; display: flex; gap: 22px; align-items: center; }}
.cta-list span {{ width: 64px; height: 64px; border-radius: 18px; background: {C['gold']}; color: {C['green']};
  display: grid; place-items: center; font-family: Display; font-weight: 900; font-size: 34px; flex: none; }}
.quote {{ font-family: Lora; font-style: italic; font-size: 46px; line-height: 1.4; opacity: .9; margin-top: 30px; }}
"""

CHECK = '<svg viewBox="0 0 24 24"><path d="M5 12.5l4.5 4.5L19 7.5" fill="none" stroke="#E8B931" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round"/></svg>'
ARROW = '<svg width="34" height="34" viewBox="0 0 24 24"><path d="M5 12h13M13 6l6 6-6 6" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/></svg>'


FOLLOW = "**Siga** @tributalizando: cripto e imposto sem juridiquês"


def with_follow(actions):
    """Toda lâmina final termina com o gancho para seguir o perfil."""
    acts = [list(a) for a in actions]
    if not any("siga" in str(v).lower() for _, v in acts):
        acts.append([str(len(acts) + 1), FOLLOW])
    return acts


def md(text):
    t = html.escape(text or "")
    t = re.sub(r"\*\*(.+?)\*\*", r"<em>\1</em>", t)
    t = re.sub(r"__(.+?)__", r"<strong>\1</strong>", t)
    return t


def paras(text):
    return "".join(f"<p>{md(p)}</p>" for p in (text or "").split("\n\n") if p.strip())


def brand():
    return f'<div class="brand">{LOGO}<span>tributa<span class="b2">lizando</span></span></div>'


def note(s):
    if not s.get("note"):
        return '<div class="spacer"></div>'
    return f'<div class="note"><b>Base:</b><span>{md(s["note"])}</span></div>'


def slide_html(s, i, n):
    t = s["type"]
    theme = s.get("theme") or ("dark" if t in ("cover", "cta", "big") else "light")
    pager = f'<div class="pager">{i:02d}/{n:02d}</div>' if n > 1 else ""
    top = f'<div class="top">{brand()}{pager}</div>'
    if t == "cover":
        inner = (f'<div class="tag">{md(s.get("tag", "Cripto & IR"))}</div>'
                 f'<h1>{md(s["title"])}</h1>'
                 + (f'<div class="sub">{md(s["subtitle"])}</div>' if s.get("subtitle") else "")
                 + '<div class="spacer"></div><div class="deco"></div>')
    elif t == "point":
        inner = (f'<div class="num">{md(str(s.get("n", "")))}</div>' if s.get("n") else "") + \
                f'<h2>{md(s["title"])}</h2><div class="body">{paras(s.get("body"))}</div>{note(s)}'
    elif t == "big":
        inner = (f'<div class="kicker">{md(s.get("kicker", ""))}</div>'
                 f'<div class="figure">{md(s["figure"])}</div>'
                 f'<div class="statement">{md(s["statement"])}</div>'
                 f'<div class="body">{paras(s.get("body"))}</div>{note(s)}')
    elif t == "checklist":
        lis = "".join(f'<li><div class="box">{CHECK}</div><div>{md(x)}</div></li>' for x in s["items"])
        inner = f'<h2>{md(s["title"])}</h2><ul class="items">{lis}</ul>{note(s)}'
    elif t == "cta":
        rows = "".join(f'<div><span>{k}</span><p>{md(v)}</p></div>' for k, v in with_follow(s.get("actions", [
            ("1", "**Salve** para consultar depois"),
            ("2", "**Envie** para quem opera cripto"),
            ("3", "**Comente** sua dúvida aqui"),
        ])))
        inner = (f'<h2>{md(s["title"])}</h2>'
                 + (f'<div class="quote">{md(s["body"])}</div>' if s.get("body") else "")
                 + f'<div class="cta-list">{rows}</div><div class="spacer"></div><div class="deco"></div>')
    else:
        raise ValueError(f"tipo desconhecido: {t}")
    right = f'<div class="swipe">arraste {ARROW}</div>' if (t == "cover" and n > 1) else "<div>Conteúdo informativo</div>"
    foot = f'<div class="foot"><div>{HANDLE}</div>{right}</div>'
    return f'<!doctype html><html><head><meta charset="utf-8"><style>{CSS}</style></head><body><div class="slide {theme}">{top}{inner}{foot}</div></body></html>'


def render(spec_path):
    spec_path = Path(spec_path).resolve()
    folder = spec_path.parent
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    slides = spec["slides"]
    names = []
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--allow-file-access-from-files"])
        page = browser.new_page(viewport={"width": 1080, "height": 1350}, device_scale_factor=1)
        for i, s in enumerate(slides, 1):
            tmp = folder / f"_s{i}.html"
            tmp.write_text(slide_html(s, i, len(slides)), encoding="utf-8")
            page.goto(tmp.as_uri())
            page.evaluate("document.fonts.ready")
            name = f"{i:02d}.jpg"
            page.screenshot(path=str(folder / name), type="jpeg", quality=92)
            tmp.unlink()
            names.append(name)
        browser.close()
    post_file = folder / "post.json"
    post = json.loads(post_file.read_text(encoding="utf-8")) if post_file.exists() else {}
    post.update({k: spec[k] for k in ("scheduled_at", "caption", "title", "sources", "format") if k in spec})
    post["images"] = names
    post.setdefault("status", "pending")
    post_file.write_text(json.dumps(post, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{folder.name}: {len(names)} arte(s)")


if __name__ == "__main__":
    for a in sys.argv[1:]:
        render(a)
