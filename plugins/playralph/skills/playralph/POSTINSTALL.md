# Post-Install: /playralph

## Check:

1. Run `npx playwright --version` — if it fails:
   "PlayRalph needs Playwright. Install with: `npm init -y && npx playwright install chromium`"

## Then:

Create `wiki/skills/playralph.md`:

```yaml
---
type: skill-config
playwright: true
tags:
  - skill
  - playralph
  - testing
---

# /playralph configuration

Playwright: installed
```
