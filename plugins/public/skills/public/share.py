#!/usr/bin/env python3
"""
share.py — pubblica / revoca / elenca le cartelle di `public/` di QUESTO brain.

Driver `share-cli` (installazioni ABChat). L'URL pubblico NON è deducibile dal
nome del brain o della cartella: è un token opaco generato dall'app e vivo solo
finché la pubblicazione non scade. Quindi l'unico modo corretto di dare un link
a qualcuno è chiederlo qui e copiarlo. Mai comporlo a mano.

Autenticazione (prova-da-filesystem, nessun segreto in chiaro):
  1. scriviamo `storage/.share-request.json` con un nonce e l'azione
  2. POST {base}/api/share/cli con {brain, nonce}
  3. l'app confronta il nonce col file: solo chi può scrivere dentro questo
     brain può averlo creato → la richiesta è autenticata. File one-shot.

Uso:
    python3 share.py list
    python3 share.py publish [cartella] [--days N] [--password PW]
    python3 share.py revoke  <cartella>

`cartella` è relativa a `public/`. Vuota = pubblica tutto `public/`.

Esce con codice 1 e messaggio su stderr in caso di errore: mai inventare un
URL quando la chiamata fallisce, meglio dire all'utente che non è pubblicato.
"""

import argparse
import base64
import json
import os
import re
import secrets
import sys
import urllib.error
import urllib.request
from pathlib import Path

BRAIN_ROOT = Path(__file__).resolve().parents[3]
ENV_PATH = BRAIN_ROOT / ".env"
REQUEST_FILE = BRAIN_ROOT / "storage" / ".share-request.json"
DEFAULT_BASE_URL = "https://abchat.it"
TIMEOUT = 20


def read_env(key: str) -> str:
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if line.startswith(f"{key}="):
                return line.split("=", 1)[1].strip().strip("\"'")
    return os.getenv(key, "")


def brain_slug() -> str:
    slug = read_env("WORKSPACE_SLUG") or read_env("BRAIN_SLUG")
    if not slug:
        sys.exit("WORKSPACE_SLUG non trovato in .env — impossibile identificare il brain.")
    return slug


def base_url() -> str:
    """Base dell'installazione: SHARE_BASE_URL in .env, poi boot/domain.md, poi default."""
    explicit = read_env("SHARE_BASE_URL")
    if explicit:
        return explicit.rstrip("/")
    domain_file = BRAIN_ROOT / "boot" / "domain.md"
    if domain_file.exists():
        m = re.search(
            r"^share_base_url:\s*(\S+)",
            domain_file.read_text(encoding="utf-8", errors="replace"),
            re.MULTILINE,
        )
        if m:
            return m.group(1).rstrip("/")
    return DEFAULT_BASE_URL


def call(action: str, **payload) -> dict:
    nonce = base64.urlsafe_b64encode(secrets.token_bytes(24)).decode().rstrip("=")
    REQUEST_FILE.parent.mkdir(parents=True, exist_ok=True)
    REQUEST_FILE.write_text(
        json.dumps({"nonce": nonce, "action": action, **payload}), encoding="utf-8"
    )

    body = json.dumps({"brain": brain_slug(), "nonce": nonce}).encode()
    req = urllib.request.Request(
        f"{base_url()}/api/share/cli",
        data=body,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            # Cloudflare risponde 1010 al default di urllib ("Python-urllib/x.y").
            "User-Agent": "abchat-brain-share/1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")[:300]
        sys.exit(f"L'app ha rifiutato la richiesta ({e.code}): {detail}")
    except Exception as e:  # rete giù, DNS, timeout
        sys.exit(f"Impossibile raggiungere {base_url()}: {e}")
    finally:
        REQUEST_FILE.unlink(missing_ok=True)


def print_list(rows: list) -> None:
    if not rows:
        print("Nessuna cartella pubblicata. Niente di questo brain è raggiungibile dall'esterno.")
        return
    for r in rows:
        folder = r.get("folder") or "(tutta public/)"
        print(f"{folder}\n  {r.get('url')}\n  scade il {r.get('expires_human')}"
              f"{'  [password]' if r.get('password_set') else ''}")


def main() -> None:
    p = argparse.ArgumentParser(description="Pubblica/revoca/elenca le cartelle public/ del brain.")
    p.add_argument("action", choices=["list", "publish", "revoke"])
    p.add_argument("folder", nargs="?", default="", help="cartella relativa a public/ (vuoto = tutta public/)")
    p.add_argument("--days", type=int, default=30, help="durata in giorni (1-90, default 30)")
    p.add_argument("--password", default="", help="protegge la pagina con password")
    a = p.parse_args()

    if a.action == "list":
        print_list(call("list").get("published", []))
        return

    if a.action == "revoke":
        if not a.folder:
            sys.exit("revoke richiede la cartella.")
        res = call("revoke", folder=a.folder)
        if res.get("error"):
            sys.exit(f"Revoca non riuscita: {res['error']}")
        print(f"Revocata: {a.folder} — il link non risponde più.")
        return

    res = call("publish", folder=a.folder, days=a.days, password=a.password)
    if res.get("error"):
        sys.exit(f"Pubblicazione non riuscita: {res['error']}")
    print(f"{res['url']}\nscade il {res['expires_human']} ({res['days']} giorni)"
          f"{'  [password impostata]' if res.get('password_set') else ''}")


if __name__ == "__main__":
    main()
