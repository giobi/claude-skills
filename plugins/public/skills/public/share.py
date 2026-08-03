#!/usr/bin/env python3
"""
share.py — pubblica / revoca / elenca le cartelle di `public/` di QUESTO brain,
su qualunque installazione della flotta.

Ogni install ha host e meccanismi suoi: l'endpoint non si scrive a mano qui, si
RICAVA (config → env → INSTANCE_HOST del container). Un default hardcoded sarebbe
la stessa classe di bug che questa skill esiste per chiudere: un URL plausibile e
sbagliato dato all'utente come buono.

Meccanismo "a token": la cartella si pubblica e riceve un URL opaco che scade
(`{install}/share/{token}/…`). Il token lo genera l'app, non è deducibile.
Autenticazione prova-da-filesystem: scriviamo un nonce in
`storage/.share-request.json`, poi POST all'API con {brain, nonce}; solo chi può
scrivere dentro questo brain può averlo creato. File one-shot.

Uso:
    python3 share.py list
    python3 share.py publish [cartella] [--days N] [--password PW]
    python3 share.py revoke  <cartella>
    python3 share.py doctor          # cosa è vivo su QUESTA installazione
    ... [--json]                     # output grezzo per gli script

`cartella` è relativa a `public/`. Vuota = tutto `public/`.
Esce con codice 1 e messaggio su stderr se qualcosa non va: mai stampare un URL
quando la chiamata è fallita.
"""

import argparse
import json
import os
import re
import secrets
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]      # .claude/skills/public/share.py → brain root
ENV_PATH = ROOT / ".env"
LOCAL_YAML = ROOT / "boot" / "local.yaml"       # ← l'infrastruttura si dichiara QUI
CONFIG_PATH = ROOT / "wiki" / "skills" / "public.md"
REQUEST_FILE = ROOT / "storage" / ".share-request.json"
UA = "abchat-brain-share/1.0"                   # Cloudflare dà 1010 al default di urllib
TIMEOUT = 30


# ---------------------------------------------------------------- sorgenti

def read_env(key: str) -> str:
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if line.startswith(f"{key}="):
                return line.split("=", 1)[1].strip().strip("\"'")
    return os.getenv(key, "")


def config() -> dict:
    """Frontmatter di wiki/skills/public.md (senza dipendere da PyYAML)."""
    if not CONFIG_PATH.exists():
        return {}
    text = CONFIG_PATH.read_text(encoding="utf-8", errors="replace")
    if not text.startswith("---"):
        return {}
    block = text.split("---", 2)[1]
    try:
        import yaml
        return yaml.safe_load(block) or {}
    except Exception:
        out = {}
        for line in block.splitlines():
            m = re.match(r"^([a-z_]+):\s*(.+?)\s*$", line)
            if m:
                out[m.group(1)] = m.group(2).strip("\"'")
        return out


def infra() -> dict:
    """
    Sezione `public:` di `boot/local.yaml` — la **dichiarazione** di come una
    pagina diventa pubblica su questa installazione.

    Perché qui e non altrove: nel brain protocol l'infrastruttura la decidono
    `boot/local.yaml` (macchina/ambiente) e `boot/domain.md` (contratto), non il
    config di una skill e non l'ambiente del container. `wiki/skills/public.md`
    tiene solo opzioni di skill (template, giorni di default). Dedurre l'host
    dall'env era la stessa classe di errore che questa skill esiste per chiudere:
    un dato infrastrutturale ricavato per indizi invece che letto dove è scritto.
    """
    if not LOCAL_YAML.exists():
        return {}
    try:
        import yaml
        data = yaml.safe_load(LOCAL_YAML.read_text(encoding="utf-8", errors="replace")) or {}
    except Exception:
        return {}
    pub = data.get("public")
    return pub if isinstance(pub, dict) else {}


def instance_host() -> str:
    """Host dell'installazione: dichiarato in local.yaml, env solo come ripiego."""
    declared = str(infra().get("base_url") or "").strip()
    if declared:
        return urllib.parse.urlsplit(declared if "//" in declared else f"https://{declared}").netloc
    return os.getenv("INSTANCE_HOST", "").strip()


def share_api_candidates() -> list:
    """
    Endpoint /api/share/cli da provare, in ordine. Ritorna [(url, verifica_tls)].

    Gli install della flotta non si raggiungono allo stesso modo e **non basta un
    solo candidato**:
      - avocado: INSTANCE_HOST (avocado.abchat.it) fa 301 sull'host canonico → ok
      - grbrain: INSTANCE_HOST (grbrain.com) risponde diretto → ok
      - emibrain: è on-prem, l'host pubblico NON è raggiungibile dal container
        (timeout); ci si arriva solo al nginx interno `{INSTANCE_ID}-nginx`, con
        certificato che ovviamente non combacia col nome del container.

    Per quell'ultimo salto la verifica TLS è disattivata: è un hop
    container→container sulla rete docker dell'install, e l'alternativa è che la
    pubblicazione non funzioni affatto lì.

    ⚠️ L'app compone l'URL restituito con l'host della RICHIESTA, non con APP_URL:
    bussare a `emi-nginx` fa tornare `https://emi-nginx/share/…`, un nome di
    container inservibile come link. Per questo al candidato interno mandiamo un
    header `Host:` canonico, e comunque validiamo l'URL che torna (vedi
    `canonical_host()` e `check_url()`).
    """
    out = []
    inf = infra()
    # 1. dichiarati in boot/local.yaml — la fonte di verità
    for key, verify in (("share_api", True), ("share_api_internal", False)):
        v = str(inf.get(key) or "").strip()
        if v and v.lower() not in ("null", "none", "~"):
            out.append((v, verify))
    # 2. ripieghi per i brain il cui local.yaml non dichiara ancora la sezione
    if not out:
        explicit = str(config().get("share_api") or "").strip() or os.getenv("SHARE_API_URL", "").strip()
        if explicit:
            out.append((explicit, True))
        host = instance_host()
        if host:
            out.append((f"https://{host}/api/share/cli", True))
        iid = os.getenv("INSTANCE_ID", "").strip()
        if iid:
            out.append((f"https://{iid}-nginx/api/share/cli", False))
    if not out:
        sys.exit(
            "Non riesco a ricavare l'endpoint delle pubblicazioni.\n"
            "Dichiaralo in boot/local.yaml:\n\n"
            "public:\n"
            "  mode: share-token\n"
            "  base_url: https://<host pubblico dell'install>\n"
            "  share_api: https://<host pubblico dell'install>/api/share/cli\n"
        )
    seen, uniq = set(), []
    for url, verify in out:
        if url not in seen:
            seen.add(url)
            uniq.append((url, verify))
    return uniq


def slug_candidates() -> list:
    """
    Lo slug con cui l'app conosce questo brain. Varia per install: su alcuni è in
    .env, su altri il manifest porta l'UID invece dello slug. Li proviamo in ordine.
    """
    out = []
    manifest_slug = None
    manifest = ROOT / "manifest.json"
    if manifest.exists():
        try:
            manifest_slug = json.loads(manifest.read_text()).get("slug")
        except Exception:
            pass

    for v in (str(infra().get("brain_slug") or "").strip(),     # dichiarato in local.yaml, vince
              str(config().get("brain_slug") or "").strip(),    # legacy: config di skill
              read_env("WORKSPACE_SLUG"),
              read_env("BRAIN_SLUG"),
              manifest_slug,
              # nome della cartella del brain — ma dentro il container il mount
              # si chiama sempre "data", che non è mai uno slug: inutile provarlo.
              ROOT.name if ROOT.name != "data" else ""):
        if v and v not in out:
            out.append(v)
    if not out:
        sys.exit("Non riesco a determinare lo slug del brain (né config, né .env, né manifest.json).")
    return out


# ---------------------------------------------------------------- chiamata

def canonical_host() -> str:
    """
    L'host con cui gli UTENTI raggiungono questo install — quello che deve
    comparire nei link. Dichiarato come `public.base_url` in boot/local.yaml.
    L'env dei container non è affidabile: su emibrain 19 su 25 dicono ancora
    `v2.emibrain.it`, un vhost morto. Per questo `instance_host()` legge prima
    local.yaml e solo dopo ripiega sull'env.
    """
    return instance_host()


def check_url(url: str) -> str:
    """
    Segnala gli URL inservibili invece di spacciarli per buoni: se il link punta
    al nginx interno dell'install, non è raggiungibile da nessun utente.
    Ritorna stringa vuota se l'URL va bene, altrimenti il motivo.
    """
    host = urllib.parse.urlsplit(url).netloc
    iid = os.getenv("INSTANCE_ID", "").strip()
    if iid and host.startswith(f"{iid}-"):
        return (f"l'app ha restituito un link sull'host interno `{host}`, che nessuno "
                f"può aprire. Metti `public_base_url: https://<host pubblico>` in "
                f"wiki/skills/public.md.")
    return ""


class Unreachable(Exception):
    """L'endpoint non risponde (rete/DNS/TLS): si passa al candidato successivo."""


def post(url: str, payload: dict, verify: bool = True, host: str = "", _redirects: int = 3):
    """POST JSON. Segue i 3xx MANTENENDO il POST (urllib lo degraderebbe a GET:
    su avocado INSTANCE_HOST fa 301 verso l'host canonico). `host` forza
    l'header Host, così l'app compone i link col nome pubblico e non con quello
    del container a cui abbiamo bussato."""
    headers = {"Content-Type": "application/json", "Accept": "application/json", "User-Agent": UA}
    if host:
        headers["Host"] = host
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers=headers,
        method="POST",
    )

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *a, **k):
            return None

    handlers = [NoRedirect()]
    if not verify:
        import ssl
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        handlers.append(urllib.request.HTTPSHandler(context=ctx))
    opener = urllib.request.build_opener(*handlers)

    try:
        with opener.open(req, timeout=TIMEOUT) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        if e.code in (301, 302, 307, 308) and _redirects > 0:
            loc = e.headers.get("Location")
            if loc:
                return post(urllib.parse.urljoin(url, loc), payload, verify, host, _redirects - 1)
        body = e.read().decode(errors="replace")
        try:
            return e.code, json.loads(body)
        except Exception:
            return e.code, {"error": f"HTTP {e.code}: {body[:200]}"}
    except Exception as e:
        raise Unreachable(f"{url}: {e}")


def call(action: str, **payload) -> dict:
    """
    Prova ogni endpoint candidato e, per ciascuno, ogni slug plausibile: il primo
    200 vince. Un endpoint irraggiungibile non è un errore fatale — è il caso
    normale su un install dove l'host pubblico non si raggiunge da dentro.
    """
    errors = []
    canon = canonical_host()
    for api, verify in share_api_candidates():
        # Host canonico solo quando bussiamo a un endpoint di servizio (interno):
        # sugli endpoint pubblici l'host è già quello giusto.
        host = canon if (not verify and canon) else ""
        for slug in slug_candidates():
            nonce = secrets.token_urlsafe(30)
            REQUEST_FILE.parent.mkdir(parents=True, exist_ok=True)
            REQUEST_FILE.write_text(json.dumps({"nonce": nonce, "action": action, **payload}))
            try:
                status, body = post(api, {"brain": slug, "nonce": nonce}, verify, host)
            except Unreachable as e:
                errors.append(str(e))
                break                      # endpoint morto: inutile provare altri slug
            finally:
                REQUEST_FILE.unlink(missing_ok=True)
            if status == 200:
                return body
            errors.append(f"{api} [{slug}]: {body.get('error', status)}")
    return {"error": "; ".join(errors[-3:]) or "nessun endpoint raggiungibile"}


# ---------------------------------------------------------------- output

def show(rows: list) -> None:
    if not rows:
        print("Nessuna cartella pubblicata: niente di questo brain è raggiungibile dall'esterno.")
        return
    for r in rows:
        bad = check_url(r.get("url", ""))
        print(f"{r.get('folder') or '(tutta public/)'}\n  {r.get('url')}\n"
              f"  scade il {r.get('expires_human')}"
              f"{'  [password]' if r.get('password_set') else ''}"
              f"{chr(10) + '  ⚠️ ' + bad if bad else ''}")


def doctor() -> dict:
    """
    Cosa è VIVO su questa installazione, adesso. Da lanciare invece di fidarsi di
    un config scritto mesi fa: gli install della flotta non sono uguali (su alcuni
    esiste ancora un host statico sempre-pubblico, su altri no).
    """
    def probe(url):
        try:
            r = urllib.request.Request(url, method="GET", headers={"User-Agent": UA})
            with urllib.request.urlopen(r, timeout=10) as resp:
                return resp.status
        except urllib.error.HTTPError as e:
            return e.code
        except Exception:
            return None

    rep = {
        "infra_declared": "boot/local.yaml public:" if infra() else "NO — nessuna sezione public: in boot/local.yaml",
        "install_host": instance_host() or "(ignoto)",
        "share_api": ", ".join(u for u, _ in share_api_candidates()),
        "slug": slug_candidates()[0],
        "token_driver": None,
        "legacy_static": None,
    }

    res = call("list")
    rep["token_driver"] = "ok" if "published" in res else f"KO: {res.get('error')}"
    if isinstance(res.get("published"), list):
        rep["published"] = res["published"]

    legacy = str(infra().get("static_url")
                 or config().get("legacy_base_url") or config().get("base_url") or "").strip()
    if legacy:
        code = probe(legacy.rstrip("/") + "/")
        rep["legacy_static"] = f"{legacy} → HTTP {code}" + ("  (VIVO)" if code == 200 else "  (non serve)")
    return rep


def main() -> None:
    p = argparse.ArgumentParser(description="Pubblica/revoca/elenca le cartelle public/ del brain.")
    p.add_argument("action", choices=["list", "publish", "revoke", "doctor"])
    p.add_argument("folder", nargs="?", default="", help="cartella relativa a public/ (vuoto = tutta public/)")
    p.add_argument("--days", type=int, default=30, help="durata in giorni (1-90, default 30)")
    p.add_argument("--password", default="", help="protegge la pagina con password")
    p.add_argument("--json", action="store_true", help="output grezzo")
    a = p.parse_args()

    if a.action == "doctor":
        rep = doctor()
        print(json.dumps(rep, indent=2, ensure_ascii=False) if a.json else
              "\n".join(f"{k}: {v}" for k, v in rep.items() if k != "published"))
        return

    if a.action == "list":
        res = call("list")
        if a.json:
            print(json.dumps(res, indent=2, ensure_ascii=False))
        elif "published" in res:
            show(res["published"])
        else:
            sys.exit(f"Impossibile leggere le pubblicazioni: {res.get('error')}")
        return

    if a.action == "revoke":
        if not a.folder:
            sys.exit("revoke richiede la cartella.")
        res = call("revoke", folder=a.folder)
        if res.get("error"):
            sys.exit(f"Revoca non riuscita: {res['error']}")
        print(json.dumps(res, indent=2) if a.json else
              f"Revocata: {a.folder} — il link non risponde più.")
        return

    res = call("publish", folder=a.folder, days=a.days, password=a.password)
    if res.get("error") or not res.get("url"):
        sys.exit(f"Pubblicazione non riuscita: {res.get('error', 'nessun URL restituito')}")
    if bad := check_url(res["url"]):
        sys.exit(f"Pubblicato, ma il link non è utilizzabile: {bad}\n(url grezzo: {res['url']})")
    print(json.dumps(res, indent=2, ensure_ascii=False) if a.json else
          f"{res['url']}\nscade il {res['expires_human']} ({res['days']} giorni)"
          f"{'  [password impostata]' if res.get('password_set') else ''}")


if __name__ == "__main__":
    main()
