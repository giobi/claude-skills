# Post-Install: /public

This skill needs to know **how** `public/` is exposed, before it can hand out any URL.

## 1. Detect the driver — don't ask if you can check

Run the probe. It answers both "which driver" and "does it actually work here":

```bash
python3 .claude/skills/public/share.py doctor
```

- `token_driver: ok` → **`share-cli`**. Nothing else to configure in the normal case.
- `token_driver: KO …` → read the error. Usually the endpoint isn't derivable
  (missing `INSTANCE_HOST`/`INSTANCE_ID`) → set `share_api` in the config.
- `legacy_static: … (VIVO)` → that install *also* serves a static always-public
  path. Record it as `base_url`, but prefer the token driver for anything new:
  the static ones are being dismissed.

**`static`** (a web root serves the folder, no token API). Ask the user:
*"What's the URL where your `public/` folder is served? (e.g. `https://public.example.com`)"*

Ask about templates either way: *"Do you have HTML templates? Where? (default: `public/template/`)"*

If `doctor` prints a link on an internal host (`{instance}-nginx`), set
`public_base_url` to the host users actually type — that's the install's env being
stale, and the config is how you override it.

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
