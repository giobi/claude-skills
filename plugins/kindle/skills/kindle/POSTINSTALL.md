# Post-Install: /kindle

This skill manages a personal reading site. You need a web server serving article HTML files.

## Ask the user:

1. **Site URL**: "Where is your reading site hosted? (e.g. `https://kindle.example.com`)"
2. **Articles directory**: "Where should articles be stored on disk? (full path)"
3. **Site name**: "What should the reader be called? (default: My Reader)"

## Then:

Create `wiki/skills/kindle.md` via brain_writer:

```yaml
---
type: skill-config
site_url: {answer}
articles_dir: {answer}
site_name: {answer}
tags:
  - skill
  - kindle
  - reading
---

# /kindle configuration

Site: {site_url}
Articles: {articles_dir}
Name: {site_name}
```

If the user doesn't have a reading site yet, suggest:
"I can create a basic reading site for you in `public/kindle/` with a clean index page. Want me to set it up?"
