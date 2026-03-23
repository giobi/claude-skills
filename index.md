# Brain Update Protocol v1.0

You are reading this because a user asked you to update their brain.
Follow these instructions step by step. Do not skip steps.

Source: https://github.com/giobi/claude-skills
Protocol version: 1.0
Brain protocol version: 4.0

---

## Step 0: Assess current state

Check what exists:

```bash
echo "=== Brain root ==="
ls boot/ 2>/dev/null || echo "NO boot/ directory"
echo "=== Brain version ==="
grep -m1 'Versione' boot/brain.md 2>/dev/null || echo "NO brain.md or no version"
echo "=== Skills ==="
ls .claude/skills/ 2>/dev/null | head -20 || echo "NO skills directory"
echo "=== Permissions ==="
touch boot/.write-test 2>/dev/null && rm boot/.write-test && echo "WRITE OK" || echo "READ-ONLY"
```

Based on the output, determine:

1. **Is boot/ writable?** If NO → you are in a domain brain with shared boot.
   Tell the user: "I file di boot/ sono in sola lettura — sono gestiti dal tuo admin.
   Posso aggiornare le skill e la configurazione locale, ma per aggiornare il protocollo
   brain devi chiedere al tuo admin di eseguire l'update sulla piattaforma."
   Then skip to Step 2.

2. **Does brain.md exist?** If NO → this is a fresh brain. Go to Step 1a (fresh install).
   If YES → check the version and go to Step 1b (upgrade).

---

## Step 1a: Fresh brain — first install

This brain has no boot/ protocol yet. Set it up.

### Create boot/ structure

```bash
mkdir -p boot wiki/skills .claude/skills/brain
```

### Download protocol files

```bash
# Brain protocol
curl -sL https://update.abchat.it/boot/brain.md -o boot/brain.md

# Templates — rename to actual files, user will customize
curl -sL https://update.abchat.it/boot/soul.template.md -o boot/soul.md
curl -sL https://update.abchat.it/boot/identity.template.md -o boot/identity.md
curl -sL https://update.abchat.it/boot/user.template.md -o boot/user.md
curl -sL https://update.abchat.it/boot/tools.md -o boot/tools.md
```

### Personalize

Ask the user:
1. "Come ti chiami?" → Update boot/user.md
2. "Come vuoi che si chiami il tuo assistente?" → Update boot/soul.md
3. "Sei su un server o sul tuo computer?" → Create boot/local.yaml

For local.yaml, auto-detect:

```bash
cat > boot/local.yaml << YAMLEOF
platform: $(test -f /etc/nginx/nginx.conf && echo server || echo local)
hostname: $(hostname)
services:
  python3: $(which python3 >/dev/null 2>&1 && echo true || echo false)
  node: $(which node >/dev/null 2>&1 && echo true || echo false)
  docker: $(which docker >/dev/null 2>&1 && echo true || echo false)
  playwright: $(npx playwright --version >/dev/null 2>&1 && echo true || echo false)
  tmux: $(which tmux >/dev/null 2>&1 && echo true || echo false)
  git: true
capabilities: {}
YAMLEOF
```

Then go to Step 2.

---

## Step 1b: Existing brain — upgrade

Compare the installed version with the latest.

```bash
# Current version
CURRENT=$(grep -oP 'Versione.*?(\d+\.\d+)' boot/brain.md | grep -oP '\d+\.\d+' | head -1)
echo "Current: $CURRENT"
echo "Latest: 4.0"
```

### If current < 4.0: Update protocol files

```bash
# Backup current
cp boot/brain.md boot/brain.md.bak
cp boot/tools.md boot/tools.md.bak 2>/dev/null

# Download latest
curl -sL https://update.abchat.it/boot/brain.md -o boot/brain.md
curl -sL https://update.abchat.it/boot/tools.md -o boot/tools.md
```

**DO NOT overwrite:** soul.md, identity.md, user.md, local.yaml — these are personalized.

### If no local.yaml exists: create it

```bash
if [ ! -f boot/local.yaml ]; then
  echo "boot/local.yaml non esiste — lo creo con auto-detect"
  # (same auto-detect block as Step 1a)
fi
```

### If no wiki/skills/ exists: create it

```bash
mkdir -p wiki/skills
cat > wiki/skills/.index.yaml << 'EOF'
registry: giobi/claude-skills
installed: {}
EOF
```

---

## Step 2: Install/update the package manager

```bash
mkdir -p .claude/skills/brain
curl -sL https://update.abchat.it/plugins/brain/skills/brain/SKILL.md \
  -o .claude/skills/brain/SKILL.md
```

Verify:

```bash
head -3 .claude/skills/brain/SKILL.md
```

Should show `name: brain`.

---

## Step 3: Show available skills

Fetch the skill catalog and present it to the user:

| Skill | Category | Description |
|-------|----------|-------------|
| brainstorm | creative | Zero-filter brainstorming |
| devil | creative | Devil's advocate — tears apart any plan |
| stalker | osint | Deep research on any subject |
| linkedin | osint | LinkedIn intelligence + Proxycurl |
| figma | design | Extract design system from Figma |
| site-ripper | design | Extract design from any website |
| playralph | testing | Playwright diagnostic loop |
| playw | testing | Playwright sidecar verification |
| radar | testing | Site audit with ELI5 report |
| scar | devops | Structured incident documentation |
| snapshot | devops | Docker Time Machine for PHP apps |
| tmux | devops | Tmux pane/window management |
| pressless | web | AI static site generator |
| blog | content | Blog management Jekyll/WordPress |
| public | web | Static mini-sites (requires nginx) |
| kindle | content | Personal reading site (requires web server) |
| cmd | meta | Manage slash commands |

Tell the user:
```
✅ Brain aggiornato alla versione 4.0
📦 Package manager /brain installato

Per installare skill: /brain install <nome>
Per vedere tutto: /brain list --available

Skill consigliate per iniziare:
  /brain install brainstorm    (brainstorming creativo)
  /brain install devil         (avvocato del diavolo)
  /brain install cmd           (gestisci i tuoi comandi)
```

---

## Step 4: Commit (if git repo)

```bash
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  git add -A
  git commit -m "Brain update: protocol v4.0 + package manager

  Source: https://update.abchat.it
  Co-Authored-By: Claude <noreply@anthropic.com>"
fi
```

---

## Notes

- boot/ files that are READ-ONLY belong to the platform admin, not to the brain
- soul.md, identity.md, user.md are PERSONAL — never overwrite during update
- local.yaml is LOCAL CONFIG — never overwrite, only create if missing
- wiki/skills/*.md contains per-skill config — survives skill updates
- All skills: https://github.com/giobi/claude-skills
- Report issues: https://github.com/giobi/claude-skills/issues
