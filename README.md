# Claude Skills

Skills for [Claude Code](https://docs.anthropic.com/en/docs/claude-code). Install them in any project or brain.

## Quick Start

### 1. Bootstrap the package manager

Copy the `/brain` skill into your project:

```bash
# From your project root
mkdir -p .claude/skills/brain
curl -sL https://raw.githubusercontent.com/giobi/claude-skills/main/plugins/brain/skills/brain/SKILL.md \
  -o .claude/skills/brain/SKILL.md
```

That's it. Now you have `/brain` available in Claude Code.

### 2. Install skills

In Claude Code:

```
/brain install brainstorm
/brain install stalker
/brain list --available
```

### 3. Use them

```
/brainstorm Should I rewrite this in Rust?
/stalker acme-corp.com
/devil Here's my deployment plan...
```

## Available Skills

### Creative
| Skill | What it does |
|-------|-------------|
| **brainstorm** | Zero-filter brainstorming — ideas without judgement |
| **devil** | Devil's advocate — ruthlessly tears apart any plan |

### OSINT & Research
| Skill | What it does |
|-------|-------------|
| **stalker** | Deep research on any subject — people, companies, domains |
| **linkedin** | LinkedIn intelligence with Proxycurl integration |

### Design
| Skill | What it does |
|-------|-------------|
| **figma** | Extract design system from Figma files via API |
| **site-ripper** | Extract design system from any live website via Playwright |

### Testing & QA
| Skill | What it does |
|-------|-------------|
| **playralph** | Playwright diagnostic loop — finds what's broken |
| **playw** | Playwright sidecar — visual verification after every change |
| **radar** | Full site audit with ELI5 summary + technical details |

### DevOps
| Skill | What it does |
|-------|-------------|
| **scar** | S.C.A.R. — structured incident documentation (Signal → Cause → Action → Reinforcement) |
| **snapshot** | Docker Time Machine — snapshot and restore PHP apps |

### Web & Content
| Skill | What it does |
|-------|-------------|
| **pressless** | AI static site generator — WordPress without the weight |
| **blog** | Blog management — draft, publish, images for Jekyll/WordPress |

### Content & Publishing
| Skill | What it does |
|-------|-------------|
| **public** | Static mini-sites and reports — CRUD with HTML templates |
| **kindle** | Personal reading site — Claude generates long-form articles |

### Meta
| Skill | What it does |
|-------|-------------|
| **cmd** | Manage your own slash commands — list, create, edit, delete |
| **brain** | This package manager |

## How It Works

Skills are Claude Code [custom slash commands](https://docs.anthropic.com/en/docs/claude-code/tutorials/custom-slash-commands) — a `SKILL.md` file in `.claude/skills/{name}/` that Claude reads when you type `/{name}`.

The `/brain` skill adds package management:

```
.claude/skills/{name}/     ← Skill code (from registry, replaceable)
  SKILL.md                  Instructions for Claude
  *.py                      Supporting scripts (optional)

wiki/skills/               ← Your config (survives updates)
  .index.yaml               What's installed, versions, sources
  {name}.md                 Per-skill parameters
```

When you `/brain update`, code gets replaced but your config stays.

## Skill Parameters

Some skills accept configuration. For example, a writing style skill needs samples of *your* writing. Parameters live in `wiki/skills/{name}.md` and survive updates.

During install, if a skill needs configuration, it asks you interactively.

## Dependencies

Some skills depend on others:

| Skill | Depends on | Also needs |
|-------|-----------|------------|
| **stalker** | linkedin, public | Playwright, Proxycurl (optional) |
| **playralph** | — | Playwright |
| **playw** | — | Playwright |
| **figma** | — | Figma API token |
| **linkedin** | — | Proxycurl API key (optional) |
| **public** | — | Web server for public/ dir |
| **kindle** | — | Web server for articles |

When you `/brain install stalker`, it checks for dependencies and prompts you to install them first.
Skills that need API keys or external tools include a `POSTINSTALL.md` that guides setup.

## Create Your Own Skills

A skill is just a folder with a `SKILL.md`:

```
.claude/skills/my-skill/
  SKILL.md        # Instructions (YAML frontmatter + markdown)
```

To publish, add it to a registry repo following this structure:

```
plugins/my-skill/
  .claude-plugin/plugin.json    # {"name":"my-skill","description":"...","version":"1.0.0"}
  skills/my-skill/SKILL.md      # The skill itself
```

## License

MIT — [Giobi Fasoli](https://giobi.com)
