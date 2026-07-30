#!/usr/bin/env python3
"""
share_signer.py — shim di compatibilità.

Il meccanismo originale (token HMAC firmati con SHARE_SECRET, `{base}/share/{b64}`)
è morto: la rotta `/share/{token}` risolve i token contro la tabella delle
pubblicazioni, quindi un token firmato localmente non corrisponde a nulla e
risponde 404. Verificato il 2026-07-30.

Questo file resta solo perché `kindle_publisher.py` e altri script fanno
`from share_signer import generate_share_url`. La firma è la stessa, ma dentro
chiama il meccanismo vero (`share.py` → POST /api/share/cli), che pubblica la
cartella e restituisce l'URL con token reale.

Per il codice nuovo: usa direttamente `share.py`.
"""

import math

from share import call

__all__ = ["generate_share_url"]


def generate_share_url(folder: str, expires_in: int = 30 * 24 * 3600) -> str:
    """
    Pubblica `public/{folder}` e ritorna il suo URL pubblico reale.

    Attenzione: non è più una pura generazione di token — pubblica per davvero
    (operazione idempotente: ripubblicare la stessa cartella estende la scadenza
    e mantiene lo stesso link). `expires_in` viene arrotondato ai giorni, minimo 1,
    massimo 90 (limite dell'app).

    Solleva RuntimeError se la pubblicazione non va a buon fine: mai restituire
    un URL che non esiste.
    """
    days = max(1, min(90, math.ceil(expires_in / 86400)))
    res = call("publish", folder=folder.strip("/"), days=days, password="")
    if not isinstance(res, dict) or res.get("error") or not res.get("url"):
        raise RuntimeError(
            f"Pubblicazione di '{folder}' non riuscita: "
            f"{res.get('error') if isinstance(res, dict) else res}"
        )
    return res["url"]


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        sys.exit("Usage: python share_signer.py <folder> [expires_days]  (deprecato: usa share.py)")
    days = int(sys.argv[2]) if len(sys.argv) > 2 else 30
    print(generate_share_url(sys.argv[1], expires_in=days * 86400))
