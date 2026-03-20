# Post-Install: /public

This skill needs to know where your public sites are served.

## Ask the user:

1. **Base URL**: "What's the URL where your `public/` folder is served? (e.g. `https://public.example.com`)"
2. **Template directory**: "Do you have HTML templates? Where are they? (default: `public/template/`)"

## Then:

Create `wiki/skills/public.md` via brain_writer:

```yaml
---
type: skill-config
base_url: {user's answer}
public_dir: public
template_dir: {user's answer or default}
tags:
  - skill
  - public
---

# /public configuration

Base URL: {base_url}
Templates: {template_dir}
```

If the user doesn't have templates yet, suggest:
"You can create a `public/template/` directory with HTML templates, or I can generate one for you. Want me to create a starter template?"
