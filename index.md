# Brain Update Protocol v2.0

You are reading this because a user asked you to update their brain.
Follow these instructions step by step. Do not skip steps.

Source: https://github.com/giobi/claude-skills
Protocol version: 2.0
Brain protocol version: 5.0

---

## Step 0: Assess current state

```bash
echo "=== Brain root ==="
ls boot/ 2>/dev/null || echo "NO boot/ directory"
echo "=== Brain version ==="
head -5 boot/brain.md 2>/dev/null || echo "NO brain.md"
echo "=== Skills ==="
ls .claude/skills/ 2>/dev/null | head -20 || echo "NO skills directory"
echo "=== Permissions ==="
touch boot/.write-test 2>/dev/null && rm boot/.write-test && echo "WRITE OK" || echo "READ-ONLY"
```

Based on the output:

1. **No boot/ at all?** → This is a fresh brain. Tell the user to run the install instead:
   "Non hai ancora un brain. Per crearlo: `curl -sL https://abchat.it/install | head -200` e segui le istruzioni."

2. **boot/ exists, brain.md < v5.0?** → Upgrade. Go to Step 1.

3. **boot/ is READ-ONLY?** → Domain brain with managed boot.
   Tell the user: "I file boot/ sono gestiti dalla piattaforma. Posso aggiornare le skill."
   Skip to Step 2.

---

## Step 1: Upgrade protocol files

### Backup and download

```bash
cp boot/brain.md boot/brain.md.bak

# Download latest brain.md
curl -sL https://raw.githubusercontent.com/giobi/brain-template/main/boot/brain.md -o boot/brain.md
```

### Remove deprecated files

```bash
# identity.md is deprecated — absorbed into soul.md
rm boot/identity.md 2>/dev/null
# tools.md is deprecated — replaced by skill system
rm boot/tools.md 2>/dev/null
```

**DO NOT overwrite:** soul.md, user.md, local.yaml — these are personalized.

### Create local.yaml if missing

```bash
if [ ! -f boot/local.yaml ]; then
  cat > boot/local.yaml << YAMLEOF
platform: $([ -f /.dockerenv ] && echo "container" || (test -f /etc/nginx/nginx.conf && echo server || echo local))
hostname: $(hostname)
os: $(uname -s | tr '[:upper:]' '[:lower:]')
arch: $(uname -m)
services:
  git: $(which git >/dev/null 2>&1 && echo true || echo false)
  python3: $(which python3 >/dev/null 2>&1 && echo true || echo false)
  node: $(which node >/dev/null 2>&1 && echo true || echo false)
  docker: $(which docker >/dev/null 2>&1 && echo true || echo false)
  tmux: $(which tmux >/dev/null 2>&1 && echo true || echo false)
YAMLEOF
fi
```

### Create wiki/skills/ if missing

```bash
mkdir -p wiki/skills
if [ ! -f wiki/skills/index.yaml ]; then
  cat > wiki/skills/index.yaml << 'EOF'
registry: giobi/claude-skills
installed: {}
EOF
fi
```

---

## Step 2: Install/update the package manager

```bash
mkdir -p .claude/skills/brain
curl -sL https://raw.githubusercontent.com/giobi/claude-skills/main/plugins/brain/skills/brain/SKILL.md \
  -o .claude/skills/brain/SKILL.md
```

Verify:

```bash
head -3 .claude/skills/brain/SKILL.md
```

Should show `name: brain`.

---

## Step 3: Show available skills

Tell the user:

```
Brain aggiornato alla versione 5.0
Package manager /brain installato

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
  git commit -m "Brain update: protocol v5.0 + package manager

  Source: https://github.com/giobi/claude-skills
  Co-Authored-By: Claude <noreply@anthropic.com>"
fi
```

---

## Notes

- soul.md, user.md are PERSONAL — never overwrite during update
- local.yaml is LOCAL CONFIG — never overwrite, only create if missing
- wiki/skills/*.md contains per-skill config — survives skill updates
- All skills: https://github.com/giobi/claude-skills
- Report issues: https://github.com/giobi/claude-skills/issues
