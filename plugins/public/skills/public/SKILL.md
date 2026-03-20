---
name: public
description: "CRUD for public mini-sites and reports — static HTML with templates"
user-invocable: true
argument-hint: "[create|update|delete|list|rebuild-index] [slug] [title]"
parameters:
  - name: base_url
    description: "Base URL where public/ is served (e.g. https://public.example.com)"
    required: true
  - name: public_dir
    description: "Path to public/ directory relative to project root"
    default: "public"
  - name: template_dir
    description: "Path to templates inside public dir"
    default: "public/template"
---

# /public — Public Sites Manager

CRUD for static mini-sites and reports served from a `public/` directory.

**Before using:** Read your config from `wiki/skills/public.md`.

## Configuration

This skill reads parameters from `wiki/skills/public.md`:

```yaml
---
base_url: https://public.example.com
public_dir: public
template_dir: public/template
---
```

## Commands

```
/public list                    List all published sites
/public create <slug> <title>   Create new mini-site from template
/public update <slug>           Update existing site
/public delete <slug>           Delete a site
/public rebuild-index           Regenerate the index page
```

## Rules

1. **Use templates.** Check `{template_dir}/` for available templates before creating.
2. **Self-contained HTML.** CSS inline, Google Fonts via CDN only.
3. **No sensitive data.** Never put passwords, tokens, or personal data in public files.
4. **Kebab-case names.** All folder names lowercase with hyphens.
5. **Main file = `index.html`.** Always.

## Template System

Templates live in `{template_dir}/`. Each is a self-contained HTML file with placeholder blocks.

When creating a new site:
1. List available templates: `ls {template_dir}/*.html`
2. Let user pick one (or suggest based on content type)
3. Copy template → `{public_dir}/{slug}/index.html`
4. Replace placeholders with real content
5. Report URL: `{base_url}/{slug}/`

## Available Blocks (common across templates)

| Block | CSS Class | Use for |
|-------|-----------|---------|
| Key numbers | `.stat-grid` | Metrics, KPIs |
| Text | `.text-block` | Paragraphs |
| Highlight | `.highlight-box` | Conclusions, recommendations |
| Status list | `.status-list` | Activities with badges |
| Data table | `.data-table` | Structured rows |
| Key-value | `.kv-card` | Reference pairs |
| Links | `.link-list` | Clickable links |

## Output

After creating/updating:
```
✅ Published: {base_url}/{slug}/
   Template: {template_name}
   Files: index.html [+ assets]
```
