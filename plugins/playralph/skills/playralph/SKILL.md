---
name: playralph
description: "PlayRalph - Playwright diagnostic loop for sites/apps"
user-invocable: true
argument-hint: "[project|URL] [context]"
---

**PlayRalph** - Diagnostic loop with Playwright

**Nota:** Per report client-facing, usa `/radar` (evoluzione di PlayRalph con report ELI5).

## Scenari

| Scenario | Cosa fa | Iterazioni |
|----------|---------|------------|
| **Bug fix** | Issue/bug → branch → fix → verify loop | max 5 |
| **Bug verification** | Screenshot e documentazione del bug | 1-2 |
| **Post-fix validation** | Fix gia pushato, verifico che funzioni | 1-2 |
| **Post-deploy check** | Check generale post-deploy | 1-3 |
| **Crisis** | Rotto ORA, trova e fixa | max 5 |

## Regole inviolabili

1. **MAI cleanup su staging/dev**
2. **Utenti test sono PERMANENTI**
3. **MAI sed/regex su file PHP/codice**
4. **Verifica FINALE** — ultimo screenshot DOPO ogni operazione

## Step 0: Parse input e carica progetto

```python
args = "$ARGUMENTS".strip()
# Se inizia con http → URL diretto, risolvi progetto dal dominio
# Altrimenti → prima parola = progetto, resto = contesto
# Carica wiki/projects/{nome}/index.md
# Leggi: domain_dev, server_dev, server_dev_path, repo, github_token_env
# Leggi sezione PlayRalph: test_user, test_password, auth_type
```

## Step 1: Scenario detection

```python
context_lower = context.lower()
if any(w in context_lower for w in ["non funziona", "rotto", "errore", "500", "bug", "fix"]):
    scenario = "bugfix"
elif any(w in context_lower for w in ["verifica bug", "documenta", "screenshot del bug"]):
    scenario = "verification"
elif any(w in context_lower for w in ["post-fix", "ho fixato", "ho pushato"]):
    scenario = "postfix"
elif any(w in context_lower for w in ["deploy", "post-deploy"]):
    scenario = "postdeploy"
elif any(w in context_lower for w in ["down", "crash", "urgente", "crisis"]):
    scenario = "crisis"
else:
    scenario = None  # → questionario con AskUserQuestion
```

## Step 2: Auth autonoma

Ordine: radar_auth_cmd → credenziali esplicite → artisan tinker → wp-cli → DB diretto → chiedi a Giobi

### Laravel
```bash
ssh {server} "cd {path} && php artisan tinker --execute=\"...magic link...\""
```

### WordPress
```bash
ssh {server} "cd {path} && wp user update {email} --user_pass=RadarTemp$(date +%s)!"
```

### Timeout
- `domcontentloaded` (non `networkidle`)
- Timeout 60s
- `asyncio.sleep(3)` dopo ogni navigazione

## Step 3: Analisi log

```bash
# Laravel
ssh {server} "grep 'local.ERROR' {path}/storage/logs/laravel-$(date +%Y-%m-%d).log | tail -5"
# WordPress
ssh {server} "tail -20 {path}/wp-content/debug.log"
```

## Step 4: Report

Report HTML su `public/playralph/{project}/{slug}/`
Discord notifiche start/end.

## Escalation

Se dopo 2 tentativi non si risolve → proponi PlayRalph in background (max 20 iterazioni).

## Args Provided:
```
$ARGUMENTS
```
