---
name: brain
description: "Brain package manager — install, update, list skills from registries"
user-invocable: true
argument-hint: "install <skill> | update [skill] | list [--available] | uninstall <skill> | info <skill>"
---

# /brain — Package Manager

Manages skill installation from remote registries into the brain.

## Commands

```
/brain install <skill>          Install a skill from registry
/brain install <repo>/<skill>   Install from a specific repo
/brain update [skill]           Update one or all installed skills
/brain list                     List installed skills
/brain list --available         List skills available in registry
/brain uninstall <skill>        Remove an installed skill
/brain info <skill>             Show skill details and parameters
```

## Architecture

```
.claude/skills/{name}/          ← Code (from registry, replaceable on update)
  SKILL.md                       Skill instructions
  *.py, *.sh                     Supporting scripts

wiki/skills/                    ← Brain-specific configuration (survives updates)
  .index.yaml                    Registry of installed skills
  {name}.md                      Per-skill parameters and customization
```

**Key principle:** `.claude/skills/` = code (updatable). `wiki/skills/` = config (yours forever).

## Install Flow

When user says `/brain install <skill>`:

### Step 1: Resolve registry

Read `wiki/skills/.index.yaml` for the default registry. Default: `giobi/claude-skills`.

If user specifies `<repo>/<skill>` (e.g. `someone/their-skills/brainstorm`), use that repo instead.

### Step 2: Fetch marketplace

```bash
# Fetch marketplace.json from the registry repo
gh api repos/{owner}/{repo}/contents/.claude-plugin/marketplace.json \
  -q '.content' | base64 -d
```

Find the skill in the `plugins` array. If not found, show available skills and abort.

### Step 3: Download skill files

```bash
# Download the plugin directory
cd /tmp
gh api repos/{owner}/{repo}/tarball/main > repo.tar.gz
tar xzf repo.tar.gz
# Find and copy the skill
cp -r */plugins/{skill}/skills/{skill}/* .claude/skills/{skill}/
# Also copy scripts if they exist
cp -r */plugins/{skill}/skills/{skill}/scripts/* .claude/skills/{skill}/ 2>/dev/null
```

### Step 4: Check dependencies

Read the skill's SKILL.md frontmatter for `depends:` field. If dependencies are listed, install them first (recursive).

### Step 5: Create parameter file

Create `wiki/skills/{skill}.md` via brain_writer:

```python
import sys; sys.path.insert(0, '.claude/skills/brain-writer')
from brain_writer import create_entity

create_entity('skills', skill_name, f'''
Parametri per la skill **{skill_name}**.

## Configuration

_Nessuna configurazione necessaria._
''', entity_type='tech', tags=['skill', 'installed', skill_name])
```

### Step 6: Post-install

If the skill directory contains `POSTINSTALL.md`, read it and execute the instructions. This typically asks the user for configuration (e.g., style samples for ghostwriter, API keys for external services).

### Step 7: Update registry

Update `wiki/skills/.index.yaml`:

```yaml
installed:
  {skill_name}:
    source: {owner}/{repo}
    version: {version from plugin.json}
    installed_at: {today}
```

### Step 8: Confirm

```
✅ Installed: {skill_name} v{version}
   Source: {registry}
   Config: wiki/skills/{skill_name}.md
   Use: /{skill_name}
```

## Update Flow

When user says `/brain update [skill]`:

### Single skill
1. Read `wiki/skills/.index.yaml` → get source and current version
2. Fetch latest from registry
3. Compare versions — if same, skip
4. **Overwrite** `.claude/skills/{skill}/` with new code
5. **DO NOT touch** `wiki/skills/{skill}.md` (user parameters are sacred)
6. Update version in `.index.yaml`
7. If POSTINSTALL.md changed, notify user of new config options

### All skills
Loop through all entries in `.index.yaml` `installed:` section.

## Uninstall Flow

1. Delete `.claude/skills/{skill}/` directory
2. Ask user: "Keep config in wiki/skills/{skill}.md? (y/n)"
3. Remove entry from `.index.yaml`

## List Flow

### `/brain list` (installed)
Read `.index.yaml`, show table:
```
Skill         Version  Source              Installed
brainstorm    1.0.0    giobi/claude-skills 2026-03-20
stalker       1.0.0    giobi/claude-skills 2026-03-20
```

### `/brain list --available`
Fetch marketplace.json, show all plugins with descriptions. Mark installed ones with ✅.

## Info Flow

`/brain info stalker`:
1. Read `.index.yaml` for install info
2. Read `.claude/skills/stalker/SKILL.md` for description
3. Read `wiki/skills/stalker.md` for current parameters
4. Show combined info

## Parameter Pattern

Skills that need user configuration include a `parameters:` section in their SKILL.md frontmatter:

```yaml
---
name: ghostwriter
parameters:
  - name: style_samples
    description: "Writing samples in the user's voice"
    required: true
  - name: tone
    description: "Default tone (formal/informal/technical)"
    default: informal
---
```

During install, if `parameters:` exist with `required: true`, the post-install prompts the user. Parameters are stored in `wiki/skills/{name}.md` frontmatter.

At runtime, the SKILL.md instructions say: "Read your parameters from `wiki/skills/{name}.md`".

## Notes

- Skills are flat in `.claude/skills/` — no nesting, no prefixes
- The registry is just a GitHub repo with a `marketplace.json`
- Anyone can create a registry — just follow the plugin structure
- `wiki/skills/` is managed by brain_writer, follows brain conventions
