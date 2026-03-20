# Post-Install: /linkedin

LinkedIn skill works in two modes:
- **Basic** (no API key): builds search URLs, user opens in browser
- **Deep** (with Proxycurl): fetches profile data programmatically

## Ask the user:

1. **Proxycurl API key** (optional): "Do you have a Proxycurl API key? (Get one at proxycurl.com — or skip for basic mode)"

## Then:

Create `wiki/skills/linkedin.md`:

```yaml
---
type: skill-config
mode: basic|deep
tags:
  - skill
  - linkedin
---

# /linkedin configuration

Mode: {basic or deep}
```

If deep mode, remind:
"Add `PROXYCURL_API_KEY=your_key` to your `.env` file."
