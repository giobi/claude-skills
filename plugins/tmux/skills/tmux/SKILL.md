---
name: tmux
description: "Tmux management (pane/window titles, layout, move panes)"
user-invocable: true
argument-hint: "[rename|list|4x4|restore|layout|move|borders] [args]"
---

**Tmux Manager** - Gestione titoli e layout tmux

## NLP-First Design

Interpreta linguaggio naturale:
- `/tmux rinomina questo pane innesto` → rename pane
- `/tmux questa window si chiama job` → rename window
- `/tmux mostra tutto` → list
- `/tmux sposta pane 2 in window 4` → move pane
- `/tmux layout colonne` → even-horizontal
- `/tmux rimetti a posto` → reset layout
- `/tmux 4x4` → setup completo
- `/tmux restore recent` → ripristina ultime 16 sessioni

## CRITICAL: 1-Based Indexing

**TUTTO è 1-based.** `base-index=1`, `pane-base-index=1`.
- Windows: 1, 2, 3, 4 (NON 0, 1, 2, 3)
- Panes: 1, 2, 3, 4 (NON 0, 1, 2, 3)
- **MAI** usare indice 0 per pane o window

## Intent Detection

```python
args = "$ARGUMENTS".strip().lower()

if args in ["rename", "rinomina", "name", "nome"]:
    intent = "auto_rename"
elif any(w in args for w in ["restore recent", "restore", "ripristina recenti"]):
    intent = "restore_recent"
elif any(w in args for w in ["4x4", "4 x 4", "standard"]):
    intent = "setup_4x4"
elif any(w in args for w in ["list", "ls", "mostra", "status", "vedi"]):
    intent = "list"
elif any(w in args for w in ["layout", "colonne", "rimetti a posto", "riorganizza"]):
    intent = "layout"
elif any(w in args for w in ["sposta", "muovi", "metti", "move"]) and "pane" in args:
    intent = "move_pane"
elif any(w in args for w in ["border", "bordi", "titoli"]):
    intent = "borders"
elif any(w in args for w in ["window", "finestra", "win"]):
    intent = "rename_window"
else:
    intent = "rename_pane"
```

## Emoji Automatica

**SEMPRE aggiungere un'emoji prima del titolo** (sia window che pane):
- Progetti creativi: 📝 ✍️ 📖
- Lavoro/business: 💼 🏢 💰
- Tecnico/dev: 🔧 ⚙️ 💻
- Server/infra: 🖥️ 🌐 ☁️
- Email: 📧 💬 📱
- Se topic ha emoji nota (innesto=🦉, circus=🎪), usa quella

## Actions

### setup_4x4
```bash
~/.tmux/setup-4x4.sh
```
4 window × 4 pane con tema Mille e una Notte.

### restore_recent
Ripristina ultime 16 sessioni Claude in 4 window × 4 pane con `--dangerously-skip-permissions`.

### list
```bash
tmux list-windows -F "#{window_index}: #{window_name} (#{window_panes} panes)"
for win in $(tmux list-windows -F "#{window_index}"); do
    tmux list-panes -t $win -F "  pane #{pane_index}: #{pane_title}"
done
```

### auto_rename
Rinomina pane corrente in base al contesto della sessione (progetto, task, topic).

### rename_pane
**NON usare `tmux select-pane -T`** — Claude Code sovrascrive il pane_title.
Titoli gestiti via file in `~/.tmux/titles/`:
```bash
~/.tmux/set-pane-title.sh "EMOJI NAME"
~/.tmux/set-pane-title.sh "EMOJI NAME" $PANE_ID  # pane specifico
```

### rename_window
```bash
tmux rename-window "EMOJI NAME"
```

### move_pane
```bash
# Indici 1-based!
tmux join-pane -s SOURCE_WIN.SOURCE_PANE -t TARGET_WIN
```

### layout
```bash
tmux select-layout even-horizontal   # colonne (default)
tmux select-layout even-vertical     # righe
tmux select-layout tiled             # griglia
tmux select-layout main-horizontal   # uno grande sopra
tmux select-layout main-vertical     # uno grande a sinistra
```

### borders
```bash
tmux set -g pane-border-status top
tmux set -g pane-border-format ' #(cat /home/giobi/.tmux/titles/#{s/%//:pane_id}) '
```

## Args provided:
```
$ARGUMENTS
```
