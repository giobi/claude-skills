# Brain Protocol Skills

Installable skills for [Brain Protocol](https://brainprotocol.it) brains — and for any
[Claude Code](https://docs.anthropic.com/en/docs/claude-code) project, brain or not.

A skill is a markdown file that teaches an agent a procedure: how to design something before
building it, how to research a company, how to verify a page with a real browser, how to
document an incident. They are protocol-level, so they work on any brain with any model.

Browse the catalogue at **[brainprotocol.it/skills](https://brainprotocol.it/skills/)**.

## Install

### As a Claude Code plugin marketplace

```
/plugin marketplace add giobi/brainprotocol-skills
/plugin install design
/plugin install build
```

### With the `/brain` package manager

Bootstrap the package manager once:

```bash
mkdir -p .claude/skills/brain
curl -sL https://raw.githubusercontent.com/giobi/brainprotocol-skills/main/plugins/brain/skills/brain/SKILL.md \
  -o .claude/skills/brain/SKILL.md
```

Then, inside Claude Code:

```
/brain install design
/brain install build
/brain list --available
```

### By hand

Every skill is a single folder. Copy it into `.claude/skills/` and it works:

```bash
curl -sL https://raw.githubusercontent.com/giobi/brainprotocol-skills/main/plugins/design/skills/design/SKILL.md \
  -o .claude/skills/design/SKILL.md
```

## The design → build pair

Two skills that are worth reading together, because they are two halves of one idea.

**`/design`** builds shared understanding before anyone writes anything. It grills you one
question at a time until the concept holds in three sentences, captures the vocabulary as it
surfaces (the words you and the agent are using differently without noticing), and settles the
system into a few **deep modules** — narrow interfaces, complexity hidden inside. The output is
a `design.md` that a future session, or a different agent, can read cold.

**`/build`** implements those modules under two constraints at once: TDD for the rhythm (one
test, one implementation, no code without a test that demands it) and deep modules for the
structure (you design the interface, the agent may write the implementation). After each area
it runs a **grey box check** — can this be delegated now? — and loops back to update
`design.md`, so the map stays alive instead of decaying into a document from week one.

Both are domain-agnostic: they were written for software, and they work on a wedding, a
renovation or an onboarding process. The credit for the original idea goes to Matt Pocock's
talk "Software Fundamentals Matter More Than Ever" and his
[Grill Me skill](https://github.com/mattpocock/claude-code-skills); the deep-module vocabulary
is John Ousterhout's.

## Catalogue

37 skills.

### Thinking & Building

| Skill | What it does |
|-------|--------------|
| **build** | Build mode — TDD + deep modules + a return loop that keeps the design alive |
| **design** | Collaborative design — builds shared understanding of any project before acting |
| **save** | Mid-session checkpoint (log, database, commit, push) without closing |

### Creative

| Skill | What it does |
|-------|--------------|
| **brainstorm** | Zero-filter brainstorming on projects, ideas, and decisions |
| **devil** | Devil's advocate — ruthlessly challenges any idea, plan, or decision |

### Brain core

| Skill | What it does |
|-------|--------------|
| **inbox** | Inbox manager — classify and route files from inbox/ to diary, wiki, or log |
| **project** | Project-first session management — activate, create, search brain projects |

### OSINT & Research

| Skill | What it does |
|-------|--------------|
| **linkedin** | LinkedIn intelligence — query builder, result parser, Proxycurl integration |
| **stalker** | Deep OSINT research on any subject — people, companies, domains, concepts |

### Design

| Skill | What it does |
|-------|--------------|
| **figma** | Figma Parser — extract design system from Figma files via API |
| **site-ripper** | Site Ripper — extract design system from any website via Playwright |

### Testing & QA

| Skill | What it does |
|-------|--------------|
| **playralph** | PlayRalph — Playwright diagnostic loop for sites and apps |
| **playw** | Playwright sidecar — visual verification after every code change |
| **radar** | Radar — site audit with ELI5 report + technical details |

### DevOps

| Skill | What it does |
|-------|--------------|
| **scar** | S.C.A.R. — Signal, Cause, Action, Reinforcement. Structured incident documentation. |
| **snapshot** | Docker Snapshot — Time Machine for PHP apps |
| **tmux** | Tmux management — pane/window titles, layout, move panes |

### Web & Content

| Skill | What it does |
|-------|--------------|
| **pressless** | PressLess — AI static site generator. WordPress without the weight. |
| **public** | CRUD for public mini-sites and reports — static HTML, driver-aware URLs (static | share-cli) |
| **wordpress** | WordPress management — REST API, WP-CLI, multi-site, Puppeteer, GDPR |

### Content & Publishing

| Skill | What it does |
|-------|--------------|
| **blog** | Blog management — draft, publish, images for Jekyll and WordPress |
| **kindle** | Kindle-style reader — manage long-form articles as a personal reading site |

### Writing

| Skill | What it does |
|-------|--------------|
| **ghostwriter** | Ghostwriter — write in the user's voice, not as an LLM |

### Email

| Skill | What it does |
|-------|--------------|
| **gmail** | Gmail orchestrator — triage inbox, search, draft replies in-thread |

### Messaging

| Skill | What it does |
|-------|--------------|
| **discord** | Discord bot — send messages to channels, DMs, and project channels |
| **telegram** | Telegram bot — send messages, read inbox, manage bot interactions |

### Productivity

| Skill | What it does |
|-------|--------------|
| **calendar** | Google Calendar — create, list, update, delete events |
| **drive** | Google Drive organizer — audit, triage inbox, split PDF, rename, move |

### Automation

| Skill | What it does |
|-------|--------------|
| **autoresponder** | AI email auto-responder — monitors Gmail, drafts context-aware replies, never sends without approval |
| **schedule** | Schedule manager — list, add, edit, disable, enable brain scheduled tasks |

### AI

| Skill | What it does |
|-------|--------------|
| **imagen** | AI image generation — Gemini Imagen, fal.ai (image/video/audio/TTS), Replicate Flux |

### Infrastructure

| Skill | What it does |
|-------|--------------|
| **cloudflare** | Cloudflare DNS — zones, records, cache purge, R2, Pages |

### Domains

| Skill | What it does |
|-------|--------------|
| **internetbs** | Internet.bs — domain management: check, register, renew, DNS, nameservers |

### Learning

| Skill | What it does |
|-------|--------------|
| **learn** | Learn — genera cheatsheet interattive per imparare comandi e tool tecnici |

### Developer

| Skill | What it does |
|-------|--------------|
| **github** | GitHub — repos, issues, PRs, gists, Pages, branches via API |

### Meta

| Skill | What it does |
|-------|--------------|
| **brain** | Brain package manager — install, update, list skills from registries |
| **cmd** | Slash command manager — list, create, edit, delete custom commands |
## Writing your own

A skill is a folder with a `SKILL.md`. The frontmatter is the whole contract:

```markdown
---
name: my-skill
description: One line — this is what the agent matches on
user-invocable: true
argument-hint: "[what to pass]"
---

# /my-skill

Then plain markdown: when to use it, when NOT to, the workflow, the fallbacks.
```

Write it in English, including the name — a skill name is an address, and addresses do not get
translated. Keep the "when NOT to use this" section honest; it is what stops an agent reaching
for the wrong tool.

To publish it here, add `plugins/<name>/.claude-plugin/plugin.json` and an entry in
`.claude-plugin/marketplace.json`, then open a pull request.

## Related

- **[brainprotocol.it](https://brainprotocol.it)** — the specification
- **[giobi/brainprotocol](https://github.com/giobi/brainprotocol)** — the protocol repo: `boot/brain.md`, the reference brain, the core skills

## License

MIT
