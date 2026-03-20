# Post-Install: /figma

## Ask the user:

1. **Figma API token**: "You need a Figma personal access token. Get it from Figma → Settings → Personal access tokens."

## Then:

Create `wiki/skills/figma.md`:

```yaml
---
type: skill-config
tags:
  - skill
  - figma
---

# /figma configuration

Token configured in .env
```

Remind: "Add `FIGMA_TOKEN=your_token` to your `.env` file."
