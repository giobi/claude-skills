# Claude Skills

Brain-native skills for [Claude Code](https://claude.ai/claude-code). Each skill is a self-contained plugin that adds capabilities to your Claude Code sessions.

## Skills

### Creative
| Skill | Description |
|-------|-------------|
| **brainstorm** | Zero-filter brainstorming on projects, ideas, and decisions |
| **devil** | Devil's advocate — ruthlessly challenges any idea, plan, or decision |

### OSINT & Research
| Skill | Description |
|-------|-------------|
| **stalker** | Deep OSINT research on any subject — people, companies, domains, concepts |
| **linkedin** | LinkedIn intelligence — query builder, result parser, Proxycurl integration |

### Design
| Skill | Description |
|-------|-------------|
| **figma** | Extract design system from Figma files via API |
| **site-ripper** | Extract design system from any website via Playwright |

### Testing & QA
| Skill | Description |
|-------|-------------|
| **playralph** | Playwright diagnostic loop for sites and apps |
| **playw** | Playwright sidecar — visual verification after every code change |
| **radar** | Site audit with ELI5 report + technical details |

### DevOps
| Skill | Description |
|-------|-------------|
| **scar** | S.C.A.R. — Signal, Cause, Action, Reinforcement. Structured incident docs |
| **snapshot** | Docker Snapshot — Time Machine for PHP apps |

### Web & Content
| Skill | Description |
|-------|-------------|
| **pressless** | PressLess — AI static site generator. WordPress without the weight |
| **blog** | Blog management — draft, publish, images for Jekyll and WordPress |

### Meta
| Skill | Description |
|-------|-------------|
| **cmd** | Slash command manager — list, create, edit, delete custom commands |

## Installation

Each skill is a Claude Code plugin. To install:

```bash
# Install a single skill
claude plugin install giobi/claude-skills/plugins/brainstorm

# Or clone and symlink
git clone https://github.com/giobi/claude-skills.git
cd your-project
ln -s /path/to/claude-skills/plugins/brainstorm/.claude-plugin .claude-plugin
```

## Structure

```
plugins/
├── brainstorm/
│   ├── .claude-plugin/plugin.json
│   └── skills/brainstorm/SKILL.md
├── figma/
│   ├── .claude-plugin/plugin.json
│   └── skills/figma/
│       ├── SKILL.md
│       └── scripts/figma_parser.py
└── ...
```

Each plugin follows the Claude Code plugin format:
- `.claude-plugin/plugin.json` — plugin metadata
- `skills/{name}/SKILL.md` — skill definition (prompt + instructions)
- `skills/{name}/scripts/` — supporting scripts (optional)

## License

MIT

## Author

[Giobi Fasoli](https://giobi.com) — built with [ABChat](https://abchat.it) brain system
