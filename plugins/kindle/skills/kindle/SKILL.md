---
name: kindle
description: "Kindle-style reader — manage long-form articles as a personal reading site"
user-invocable: true
argument-hint: "[list|stats|add title|show slug|verify|rename|archive|delete]"
parameters:
  - name: site_url
    description: "URL of the reading site (e.g. https://kindle.example.com)"
    required: true
  - name: articles_dir
    description: "Path to articles directory"
    required: true
  - name: site_name
    description: "Name shown in the reader UI"
    default: "My Reader"
requires:
  capabilities: [web_serving]
---

# /kindle — Personal Reader Management

Manages a personal long-form reading site. Claude generates prose articles on any topic, served as a clean reading experience.

**Before using:** Read your config from `wiki/skills/kindle.md`.

## Commands

```
/kindle                     List articles
/kindle list                List articles (with type/tag filters)
/kindle stats               Stats by type and tag
/kindle add "Title"         Create new article (Claude generates full prose)
/kindle show <slug>         Show article info and metadata
/kindle verify              Fix file permissions
/kindle rename <old> <new>  Rename article slug
/kindle archive <slug>      Archive article
/kindle delete <slug>       Delete article
```

## Configuration

Reads from `wiki/skills/kindle.md`:

```yaml
---
site_url: https://kindle.example.com
articles_dir: /path/to/articles
site_name: My Reader
---
```

## Article Structure

Each article is a directory:

```
articles/{slug}/
  index.html          Main content (clean reading layout)
  meta.json           Metadata (title, date, tags, type, word count)
  cover.jpg           Optional cover image
```

## Naming Conventions

| Type | Pattern | Example |
|------|---------|---------|
| Topic deep-dive | `topic-name` | `rust-ownership` |
| Series | `series-name-01` | `design-patterns-01` |
| Translation | `original-slug-lang` | `clean-code-it` |

Rules: lowercase, hyphens only, max 50 chars, no dates in slug.

## Article Generation

When user says `/kindle add "Title"`:

1. Determine article type (explainer, tutorial, essay, etc.)
2. Generate full prose (2000-5000 words typical)
3. Create clean HTML with reading-optimized layout
4. Generate `meta.json` with title, date, tags, word count
5. Report: URL, word count, reading time

## Output

```
✅ Published: {site_url}/{slug}/
   Words: 3,200 (~13 min read)
   Tags: rust, programming, memory
```
