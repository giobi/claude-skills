---
name: learn
description: "Genera cheatsheet interattive in HTML per imparare comandi e tool tecnici"
user-invocable: true
argument-hint: "<topic> - es: linux, tmux, ssh, git, vim, docker, nginx, bash"
depends: [public]
parameters:
  - name: base_url
    description: "Base URL dove public/ viene servito"
    required: true
  - name: public_dir
    description: "Path a public/ relativo alla root del progetto"
    default: "public"
---

# /learn - Cheatsheet Interattive

Genera pagine HTML interattive in `public/learn/{topic}/` per imparare argomenti tecnici. Ogni pagina e self-contained, dark-theme, con comandi copiabili e quiz finale.

**Prima di usare:** Leggi i tuoi parametri da `wiki/skills/learn.md`.

## Configuration

Questa skill legge parametri da `wiki/skills/learn.md`:

```yaml
---
base_url: https://public.example.com
public_dir: public
---
```

## Commands

```
/learn <topic>                  Genera cheatsheet per un topic
/learn list                     Mostra cheatsheet gia generate
/learn update <topic>           Rigenera una cheatsheet esistente
```

## Topic supportati (ma non limitati a)

| Topic | Cosa copre |
|-------|-----------|
| `linux` | Comandi base: ls, cd, cp, mv, chmod, grep, find, pipe, redirect |
| `tmux` | Sessioni, pane, window, shortcuts, .tmux.conf |
| `ssh` | Connessioni, chiavi, config, tunnel, agent forwarding |
| `git` | Workflow, branch, merge, rebase, stash, log, bisect |
| `vim` | Modi, movimento, editing, search, macro, .vimrc base |
| `nano` | Shortcuts essenziali, config |
| `docker` | Container, immagini, compose, volume, network |
| `nginx` | Config, virtual host, proxy_pass, SSL, location |
| `bash` | Variabili, loop, condizioni, funzioni, scripting |
| `systemd` | Servizi, journalctl, timer, unit file |
| `networking` | ip, ss, curl, dig, nslookup, firewall, iptables |
| `permissions` | chmod, chown, umask, ACL, sudo, su |

Qualsiasi altro topic tecnico e accettato - genera comunque.

## Workflow

### 1. Interpreta il topic

L'utente dice cose come:
- `/learn tmux` - genera cheatsheet tmux
- `/learn comandi linux base` - genera guida comandi Linux fondamentali
- `fammi una pagina per imparare docker` - stessa cosa

### 2. Genera il contenuto

Organizza in sezioni progressive:

1. **Intro** - cos'e, a cosa serve, quando si usa (2-3 frasi, zero fuffa)
2. **Setup** - come installarlo se necessario
3. **Comandi essenziali** - i 10-15 comandi che usi il 90% del tempo
4. **Comandi intermedi** - roba utile ma meno frequente
5. **Comandi avanzati** - power user stuff
6. **Combinazioni reali** - come si combinano nella pratica (workflow)
7. **Troubleshooting** - errori comuni e soluzioni
8. **Quiz** - 5-10 domande a risposta multipla interattive

Per ogni comando mostra:
- **Comando** (copiabile con click)
- **Cosa fa** (spiegazione breve)
- **Esempio pratico** con output realistico
- **Warning** se ci sono gotcha pericolosi (comandi distruttivi)

### 3. Genera l'HTML

Usa il template in `.claude/skills/learn/templates/learn-template.html` come **BASE**.

Leggi il template, poi:
1. Sostituisci `{{TOPIC_TITLE}}` col titolo del topic
2. Sostituisci `{{TOPIC_SLUG}}` col slug
3. Sostituisci `{{TOPIC_ICON}}` con un emoji appropriato
4. Sostituisci `{{INTRO_TEXT}}` con l'intro
5. Sostituisci `{{DATE}}` con la data di generazione
6. Popola le sezioni comandi duplicando i blocchi `.command-card`
7. Popola il quiz duplicando i blocchi `.quiz-question`
8. Rimuovi i blocchi placeholder/commento

**Regole HTML:**
- Self-contained (CSS + JS inline)
- Google Fonts via CDN: Inter + JetBrains Mono
- Tema scuro, dev-friendly
- Ogni comando ha bottone Copia funzionante (JS clipboard API)
- Sezioni collassabili (details/summary)
- Barra di ricerca/filtro comandi
- Responsive (mobile OK)
- Badge di difficolta: base, intermedio, avanzato

### 4. Salva e comunica

```
mkdir -p {public_dir}/learn/{topic_slug}/
# Salva index.html
```

Output:
```
Generato: /learn {topic}
   Comandi: {N} comandi documentati
   Quiz: {N} domande
   URL: {base_url}/learn/{topic_slug}/
```

## Tono del contenuto

- **Informale ma preciso** - come un collega che ti spiega le cose
- **Zero fuffa accademica** - dritto al punto
- **Esempi REALI** - niente foo, bar, example.txt. Usa file veri: app.log, config.yaml, deploy.sh
- **Warning chiari** - se un comando e pericoloso, dillo con un box rosso
- **Progressivo** - dal base all'avanzato, chi e alle prime armi non deve sentirsi perso

## Template

Il template HTML e in `.claude/skills/learn/templates/learn-template.html`. Contiene la struttura base. Le personalizzazioni (colori, logo, stile extra) vengono da `wiki/skills/learn.md`.

Non modificare il template originale - usalo come base e genera l'HTML finale sostituendo i placeholder.
