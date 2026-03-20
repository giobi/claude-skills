# Post-Install: /stalker

Stalker needs a few things to work properly.

## Check dependencies

1. **`/linkedin` skill** — required for LinkedIn lookups. If not installed:
   "You need the linkedin skill. Install it with `/brain install linkedin`"

2. **`/public` skill** — required for HTML report output. If not installed:
   "You need the public skill for report output. Install it with `/brain install public`"

## Ask the user:

1. **Report output directory**: "Where should stalker reports go? (default: `public/stalker/`)"
2. **Proxycurl API key** (optional): "Do you have a Proxycurl API key for deep LinkedIn lookups? (leave empty to skip, you can add it later in .env as `PROXYCURL_API_KEY`)"
3. **Playwright available?**: Check if `npx playwright` works. If not: "Playwright is needed for screenshots at level 4+. Install with `npx playwright install chromium`"

## Then:

Create `wiki/skills/stalker.md` via brain_writer:

```yaml
---
type: skill-config
report_dir: public/stalker
proxycurl: true|false
playwright: true|false
depends:
  - linkedin
  - public
tags:
  - skill
  - stalker
  - osint
---

# /stalker configuration

Reports: {report_dir}
Proxycurl: {yes/no}
Playwright: {available/not installed}
```

## Environment variables (in .env):

```
PROXYCURL_API_KEY=...    # Optional, for deep LinkedIn data
```
