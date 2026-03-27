---
name: blog
description: "Blog management — images, posts, publish (Jekyll, WordPress, static)"
disable-model-invocation: true
requires:
  capabilities: [web_serving]
---

**Blog Agent** - Gestione blog (giobidev e blog.giobi.com)

**Input**: `$ARGUMENTS`

## PRIMA DI TUTTO

**LEGGI SEMPRE il file progetto del blog target**:
- giobidev: `wiki/projects/giobidev.md` (sezione Writing Parameters)
- blog.giobi.com: `wiki/projects/blog.giobi.com.md` (sezione Writing Parameters)

Contengono DONTs, DOs, e esempi concreti dello stile da usare. **NON SCRIVERE** senza aver letto quelle linee guida.

## Due Blog Diversi

| | giobidev | blog.giobi.com |
|---|---|---|
| URL | giobi.com/blog | blog.giobi.com |
| Platform | Jekyll/GitHub | WordPress |
| Tono | Professionale, volgarita 0 | Personale, Nico pieno |
| Immagini | Pixel art AI | Foto personali Giobi |
| Chi scrive | Anacleto scrive, Giobi corregge | Giobi scrive, Anacleto pulisce |
| Repo/Path | `/home/web/giobidev/` | WordPress API |

## Stile COMUNE a entrambi

- Prosa fluida, periodi lunghi
- NO bullet point walls
- NO frasi spezzate a mitraglia ("Cosi. Punto. Fermo.")
- NO strutture "Il problema / La soluzione" ripetitive
- NO footer "Scritto con Claude Code"

## Subcommands

### `/blog list`
Lista draft e post recenti di ENTRAMBI i blog.

### `/blog draft <topic>` o `/blog post <topic>`
Crea draft. Chiedi QUALE blog se non specificato.
- giobidev: file in `_drafts/` o `_posts/`
- blog.giobi.com: draft via WordPress API

### `/blog publish <file|id>`
Pubblica (giobidev: commit+push, blog.giobi.com: status=publish via API)

### `/blog image <slug>` (solo giobidev)
Genera pixel art per post giobidev.

### `/blog edit <id>` (solo blog.giobi.com)
Carica draft WordPress per editing collaborativo.

## Workflow

1. **Disambigua** quale blog (se non chiaro, chiedi)
2. **Leggi** il file progetto del blog target
3. **Esegui** subcommand seguendo lo stile documentato
4. **Verifica** frontmatter (giobidev) o contenuto (WordPress)
5. **Commit/Push** (giobidev) o **Update API** (blog.giobi.com)

## Examples

- `/blog list` → lista entrambi
- `/blog draft giobi.com: hooks Claude Code` → giobidev
- `/blog edit 1155` → WordPress draft ID 1155
- `/blog publish _posts/2025-11-17-ledger.md` → giobidev
