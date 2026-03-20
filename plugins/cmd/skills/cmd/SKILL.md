---
name: cmd
description: "Manage slash commands (list, create, edit, delete)"
user-invocable: true
argument-hint: "[list|show|create|edit|delete] [name]"
---

**Command Manager** - Meta-gestione comandi slash

Alias: `/command`

## Subcommands:

### `/cmd list` (alias: `/cmd ls`)
Lista tutti i comandi disponibili con descrizioni.

### `/cmd show <nome>` (alias: `/cmd cat <nome>`)
Mostra contenuto di un comando specifico.

### `/cmd create <nome>`
Crea nuovo comando interattivamente.

### `/cmd edit <nome>`
Modifica comando esistente.

### `/cmd delete <nome>`
Elimina comando (con conferma).

### `/cmd help <nome>`
Mostra help dettagliato per comando.

## Instructions:

1. Parse subcommand: "list"/"ls", "show"/"cat"/"view", "create"/"new", "edit"/"modify", "delete"/"rm", "help"
2. Location: `/home/giobi/brain/.claude/skills/` (skills) e `/home/giobi/brain/.claude/commands/` (legacy)
3. File format: Markdown con frontmatter YAML
4. List format: show nome + description
5. Create: chiedi interattivamente description, args, instructions
6. Edit: modifica inline
7. Delete: chiedi conferma prima di rimuovere

## Args Provided:
```
$ARGUMENTS
```
