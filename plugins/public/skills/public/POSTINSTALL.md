# Post-Install: /public

This skill needs to know **how** `public/` is exposed, before it can hand out any URL.

## 1. Detect the driver — don't ask if you can check

**`share-cli`** (ABChat installs: the app mints per-folder token URLs). Signs:

```bash
grep -q WORKSPACE_SLUG .env && ls .claude/skills/public/share.py   # both present → share-cli
python3 .claude/skills/public/share.py list                        # works → confirmed
```

**`static`** (a web root serves the folder). Then ask the user:
*"What's the URL where your `public/` folder is served? (e.g. `https://public.example.com`)"*

Ask about templates either way: *"Do you have HTML templates? Where? (default: `public/template/`)"*

## 2. Write the config

Create `wiki/skills/public.md` via brain_writer:

```yaml
---
type: skill-config
driver: {share-cli | static}
base_url: {only for driver static}
public_dir: public
template_dir: {user's answer or default}
tags:
  - skill
  - public
---

# /public configuration

Driver: {driver}
Templates: {template_dir}
```

## 3. Clean up the lies

Old installs carry dead pointers that make the agent hand out URLs that 404. Check and
remove/correct them, so the skill is the only source of truth:

- **`PUBLIC_URL` in `.env`** — on ABChat installs this is a stale static URL that was
  never publicly reachable. It must not be used as a link. Remove it or leave it only
  if you verified it returns 200.
- **`share_signer.py`** (HMAC-signed token generator, older mechanism) — its tokens are
  not recognised by current installs and always 404. Superseded by `share.py`.

## 4. Verify end to end

Publish something small and `curl` it — the install isn't configured until a real link
returns 200:

```bash
python3 .claude/skills/public/share.py publish            # publishes all of public/
curl -s -o /dev/null -w '%{http_code}\n' <url it printed> # must be 200
```

If the user has no templates yet, offer: *"Want me to create a starter template in
`public/template/`?"*
