# Post-Install: /artifact

This skill needs to know **how** `public/` is exposed, before it can hand out any URL.

## 1. Detect the driver — don't ask if you can check

Run the probe. It answers both "which driver" and "does it actually work here":

```bash
python3 .claude/skills/artifact/share.py doctor
```

- `brain_root:` → confirm it points at the brain you meant. If it points somewhere
  else, run the command from the brain root or export `BRAIN_ROOT`.
- `internal_route: https://…/artifact/{slug}/` → the auth-gated address works. This
  is the one you hand out by default.
- `internal_route: KO …` → this install's village code has no `/artifact/` route, or
  `public.base_url` is missing from `boot/local.yaml`. Read the note.
- `token_driver: ok` → **`share-cli`**. Nothing else to configure in the normal case.
- `token_driver: KO …` → read the error. Usually the endpoint isn't derivable
  (missing `INSTANCE_HOST`/`INSTANCE_ID`) → set `share_api` in `boot/local.yaml`.
- `legacy_static: … (ALIVE)` → that install *also* serves a static always-public
  path. Record it as `static_url`, but prefer the token driver for anything new:
  the static ones are being dismissed.

**`static`** (a web root serves the folder, no token API). Ask the user:
*"What's the URL where your `public/` folder is served? (e.g. `https://public.example.com`)"*

Ask about templates either way: *"Do you have HTML templates? Where? (default: `public/template/`)"*

If `doctor` prints a link on an internal host (`{instance}-nginx`), set
`public.base_url` in `boot/local.yaml` to the host users actually type — that's the
install's environment being stale, and the declaration is how you override it.

## 2. Write the config

Infrastructure goes in `boot/local.yaml`:

```yaml
public:
  path: public/
  mode: share-token
  base_url: https://install.example.com
  share_api: https://install.example.com/api/share/cli
  brain_slug: brainname
```

Skill options go in `wiki/skills/artifact.md`, via brain_writer:

```yaml
---
type: skill-config
driver: {share-cli | static}
public_dir: public
template_dir: {user's answer or default}
default_days: 30
tags:
  - skill
  - artifact
---

# /artifact configuration

Driver: {driver}
Templates: {template_dir}
```

## 3. Clean up the lies

Old installs carry dead pointers that make the agent hand out URLs that 404. Check and
remove/correct them, so the driver is the only source of truth:

- **`PUBLIC_URL` in `.env`** — on ABChat installs this is a stale static URL that was
  never publicly reachable. It must not be used as a link. Remove it or leave it only
  if you verified it returns 200.
- **`share_signer.py`** (HMAC-signed token generator, older mechanism) — its tokens are
  not recognised by current installs and always 404. Superseded by `share.py`.
- **`.claude/skills/public/` as a real directory** — superseded by a symlink to the
  shared skill. Keep only the alias stub.

## 4. Verify end to end

The internal address first, because that is the default:

```bash
python3 .claude/skills/artifact/share.py link          # must print https://…/artifact/{slug}/
python3 .claude/skills/artifact/share.py list          # must list the folders in public/
```

Then, only if the install is meant to publish, try a real publication and `curl` it —
a token install isn't configured until a real link returns 200:

```bash
python3 .claude/skills/artifact/share.py publish <a throwaway folder>
curl -s -o /dev/null -w '%{http_code}\n' <url it printed>   # must be 200
python3 .claude/skills/artifact/share.py revoke <that folder>
```

If the user has no templates yet, offer: *"Want me to create a starter template in
`public/template/`?"*
