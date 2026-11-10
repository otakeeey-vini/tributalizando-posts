"""
Publica no Instagram os posts aprovados cujo horário já chegou.

Cada post fica em queue/<pasta>/post.json, por exemplo:
{
  "scheduled_at": "2026-11-12T08:00:00-03:00",
  "caption": "Legenda completa com hashtags",
  "images": ["01.jpg", "02.jpg"],      # 1 imagem = post simples; 2 a 10 = carrossel
  "status": "approved"                 # pending | approved | published | error | discarded
}

Segredos lidos do ambiente (configurados no GitHub, nunca no código):
  IG_ACCESS_TOKEN, IG_USER_ID
"""
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib import error, parse, request

ROOT = Path(__file__).resolve().parent.parent
QUEUE = ROOT / "queue"
TOKEN = "".join(os.environ.get("IG_ACCESS_TOKEN", "").split()).strip('"\'')
IG_USER_ID = os.environ.get("IG_USER_ID", "").strip()
REPO = os.environ.get("GITHUB_REPOSITORY", "otakeeey-vini/tributalizando-posts")
BRANCH = os.environ.get("GITHUB_REF_NAME", "main")
API_HOSTS = ["https://graph.facebook.com", "https://graph.instagram.com"]


def call(method, path, params=None, host=None):
    params = dict(params or {})
    params["access_token"] = TOKEN
    hosts = [host] if host else API_HOSTS
    errs = []
    for h in hosts:
        url = f"{h}/{path}"
        data = None
        if method == "GET":
            url += "?" + parse.urlencode(params)
        else:
            data = parse.urlencode(params).encode()
        try:
            with request.urlopen(request.Request(url, data=data, method=method), timeout=60) as r:
                return json.loads(r.read().decode()), h
        except error.HTTPError as e:
            errs.append(f"{h}: {e.code} {e.read().decode(errors='replace')}")
    raise RuntimeError(" | ".join(errs))


def wait_ready(container_id, host):
    for _ in range(30):
        res, _ = call("GET", container_id, {"fields": "status_code"}, host)
        status = res.get("status_code")
        if status in (None, "FINISHED"):
            return
        if status in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"container {container_id} com status {status}")
        time.sleep(5)
    raise RuntimeError(f"container {container_id} não ficou pronto a tempo")


def image_url(folder, name):
    rel = f"queue/{folder}/{name}"
    return f"https://raw.githubusercontent.com/{REPO}/{BRANCH}/{parse.quote(rel)}"


def publish(folder, post):
    images = post["images"]
    caption = post.get("caption", "")
    if len(images) == 1:
        res, host = call("POST", f"{IG_USER_ID}/media",
                         {"image_url": image_url(folder, images[0]), "caption": caption})
        container = res["id"]
    else:
        host = None
        children = []
        for name in images[:10]:
            res, host = call("POST", f"{IG_USER_ID}/media",
                             {"image_url": image_url(folder, name), "is_carousel_item": "true"}, host)
            children.append(res["id"])
        for c in children:
            wait_ready(c, host)
        res, host = call("POST", f"{IG_USER_ID}/media",
                         {"media_type": "CAROUSEL", "children": ",".join(children), "caption": caption}, host)
        container = res["id"]
    wait_ready(container, host)
    res, _ = call("POST", f"{IG_USER_ID}/media_publish", {"creation_id": container}, host)
    return res["id"]


def check():
    print(f"Token: {len(TOKEN)} caracteres, começa com {TOKEN[:3]!r}; IG_USER_ID com {len(IG_USER_ID)} dígitos")
    res, host = call("GET", IG_USER_ID, {"fields": "id,username"})
    print(f"Token OK em {host}: conectado como @{res.get('username')} ({res.get('id')})")


def main():
    if not TOKEN or not IG_USER_ID:
        msg = "Faltam os segredos IG_ACCESS_TOKEN e/ou IG_USER_ID."
        if "--check" in sys.argv:
            sys.exit(msg)
        print(msg + " Nada a fazer.")
        return
    if "--check" in sys.argv:
        check()
        return
    now = datetime.now(timezone.utc)
    changed = 0
    for post_file in sorted(QUEUE.glob("*/post.json")):
        folder = post_file.parent.name
        post = json.loads(post_file.read_text(encoding="utf-8"))
        if post.get("status") != "approved":
            continue
        when = datetime.fromisoformat(post["scheduled_at"])
        if when > now:
            continue
        try:
            media_id = publish(folder, post)
            post.update(status="published", media_id=media_id,
                        published_at=datetime.now(timezone.utc).isoformat())
            print(f"Publicado: {folder} -> {media_id}")
        except Exception as e:  # noqa: BLE001
            post.update(status="error", error=str(e)[:1000])
            print(f"ERRO em {folder}: {e}")
        post_file.write_text(json.dumps(post, ensure_ascii=False, indent=2), encoding="utf-8")
        changed += 1
    print(f"{changed} post(s) processado(s).")


if __name__ == "__main__":
    main()
