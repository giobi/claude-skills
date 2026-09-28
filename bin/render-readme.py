#!/usr/bin/env python3
"""Regenerate the README catalogue section from .claude-plugin/marketplace.json.

The catalogue is data, not prose: it lives in marketplace.json, and this script
renders it into README.md between the CATALOGUE markers. Run it after adding,
removing or renaming a plugin.

    python3 bin/render-readme.py
"""
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
MANIFEST = ROOT / ".claude-plugin" / "marketplace.json"
README = ROOT / "README.md"
START, END = "<!-- CATALOGUE:START -->", "<!-- CATALOGUE:END -->"

LABELS = {
    "workflow": "Thinking & Building",
    "creative": "Creative",
    "brain": "Brain core",
    "osint": "OSINT & Research",
    "design": "Design",
    "testing": "Testing & QA",
    "devops": "DevOps",
    "web": "Web & Content",
    "content": "Content & Publishing",
    "writing": "Writing",
    "email": "Email",
    "messaging": "Messaging",
    "productivity": "Productivity",
    "automation": "Automation",
    "ai": "AI",
    "infrastructure": "Infrastructure",
    "domains": "Domains",
    "learning": "Learning",
    "developer": "Developer",
    "meta": "Meta",
}
ORDER = list(LABELS)


def render(plugins):
    groups = {}
    for plugin in plugins:
        groups.setdefault(plugin.get("category", "other"), []).append(plugin)

    out = [f"{len(plugins)} skills.", ""]
    for category in ORDER + [c for c in sorted(groups) if c not in ORDER]:
        if category not in groups:
            continue
        out += [f"### {LABELS.get(category, category.title())}", ""]
        out += ["| Skill | What it does |", "|-------|--------------|"]
        for plugin in sorted(groups[category], key=lambda p: p["name"]):
            out.append(f"| **{plugin['name']}** | {plugin['description']} |")
        out.append("")
    return "\n".join(out)


def main():
    plugins = json.loads(MANIFEST.read_text())["plugins"]
    readme = README.read_text()
    if START not in readme or END not in readme:
        sys.exit(f"markers {START} / {END} not found in README.md")
    catalogue = f"{START}\n{render(plugins)}{END}"
    README.write_text(re.sub(re.escape(START) + r".*?" + re.escape(END),
                             lambda _: catalogue, readme, flags=re.S))
    print(f"README.md catalogue regenerated: {len(plugins)} skills")


if __name__ == "__main__":
    main()
