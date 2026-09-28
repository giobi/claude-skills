---
name: design
description: Collaborative design — builds shared understanding of any project before acting. Software, events, trips, processes, anything.
user-invocable: true
argument-hint: "[project / idea / free-form description]"
---

# /design — Collaborative Design

**Source:** Inspired by the talk "Software Fundamentals Matter More Than Ever" by Matt Pocock (2026). The original *Grill Me* skill lives at `github.com/mattpocock/claude-code-skills`. Extended here to non-software domains, with a shared vocabulary (Pocock's Failure Modes 1 and 2) and persistent brain artifacts.

**The problem it solves:** You and the AI (or anyone else) hold divergent mental models of what you are building. You have implicit intuitions you never verbalised, and you use words that mean different things in different contexts. The gap is invisible — until you see the wrong output. This applies to a feature, a wedding, a group holiday, a company process.

**Architectural principle — Deep & Grey:** the macro-areas of a design must be **deep modules** (Ousterhout): few of them, narrow interfaces, a lot of hidden complexity inside. And they must be **grey**: neither you nor the AI should need to know what is inside in order to use one or delegate it. If explaining the *how* is the only way to convey the *what*, the module is not deep enough. The synthesis phase forces that separation: real modules versus thin interfaces. `/build` then implements and verifies them with the grey box check.

---

## Language

**Run the grill in the user's language** — the dialogue belongs to whoever is talking. **But write `design.md` in English**, contents included: Design Concept, Vocabulary, Modules, Constraints, all of it. `design.md` outlives the session, gets read by future agents and future sessions — possibly ones that do not speak the user's language — and it is a technical artifact, not the agent's voice. The session context injected after the grill (section 4) stays in the language of the chat, because it is conversational.

## Two deliverables

`/design` always produces **two distinct outputs**:

1. **`design.md`** — the persistent artifact. It outlives the session and is readable by future sessions and other agents. Saved to `wiki/projects/{name}/design.md`.

2. **Session context** — the operational injection. After the grill, the AI holds the vocabulary and the design concept and uses them automatically for the rest of the session. If the context gets compressed, it re-reads `design.md` to recover.

---

## When to use /design

- Before starting anything non-trivial
- When you have an idea that is not yet clear even to you
- When you are working with other people (or with an AI) on something complex
- When you sense that "something is missing" from the plan but cannot name it

**Do not use /design:**
- For single, clear tasks ("add a field to the form")
- When you already have a detailed PRD or brief
- When you only want to generate ideas → run `/brainstorm` first

---

## Workflow

### 0. Contextualise

```python
args = "$ARGUMENTS".strip()

# Detect the domain (it calibrates the grill questions):
# software / event / travel / business / process / personal / other

# If the brain has a matching project: fuzzy-match against wiki/projects/
# Found: read index.md and any existing design.md as the starting point
# Not found: work from conversational context
```

---

### 1. Grill phase — Concept + Vocabulary

The grill has two intertwined goals, not sequential ones:
- Build the shared **design concept** (what is being built, why, for whom)
- Build the shared **vocabulary** (what each key word means *in this context*)

The vocabulary emerges *during* the grill, not after. Every time the user uses an ambiguous or misreadable term, stop and clarify: "what exactly do you mean by X here?". That definition goes into the vocabulary.

**Grill rules:**
- ONE question at a time. Wait for the answer.
- Dig deeper on ambiguous answers
- Explore the dependencies between decisions
- Capture ambiguous terms the moment they surface
- Minimum 10 questions, no maximum
- Stop only when your understanding is good enough to build the right thing
- **Deep & Grey probe:** as functional areas surface during the grill, ask yourself (and the user): "is this a thing that does work, or a thing that connects things that do work?" If it is the second, it is not a module — it is glue. Let the real modules surface before synthesis.

**Questions by domain:**

*Software / technical:*
- What is the real problem this solves?
- Who are the users? What will they concretely do?
- What does this system NOT do?
- What are the constraints (time, budget, tech debt)?
- [Vocabulary] When you say "X", do you mean Y or Z?

*Event (wedding, concert, meeting):*
- What experience do you want the attendees to have?
- What absolutely cannot go wrong?
- Who decides when there is a conflict?
- Which constraint can you not touch?
- [Vocabulary] "Simple" means how many people, to you? What kind of venue?

*Travel / holiday:*
- What pace do you want? Intense, relaxed, mixed?
- Who in the group has special needs?
- What happens if one person wants to do something different?
- What is the thing you will not compromise on?
- [Vocabulary] Is "modest budget" under X per person, for you?

*Business / process:*
- Who is accountable when something goes wrong?
- What is the expected state after this process runs?
- Where does this process end and the next one begin?
- Who approves what?
- [Vocabulary] Does "customer" include prospects, or only signed ones?

---

### 2. Synthesis phase — `design.md`

The canonical structure of the file. Do not add sections, do not remove any.

```markdown
# Design: [Project / Idea Name]

**Date:** YYYY-MM-DD
**Domain:** software | event | travel | business | personal

## Design Concept
[2-3 sentences. What is being built, why, for whom.
Readable by anyone, including people with no technical context.
If you cannot write it in 3 sentences, the grill is not over.]

<!-- VERBOSITY RULE: design.md must be VERBOSE and SELF-CONTAINED.
Whoever reads it in six months — or an AI agent in a fresh session — must
understand the project FROM SCRATCH without reading anything else. No cryptic
one-liners, no unexplained abbreviations. Every section explains the why, not
just the what. The vocabulary is the single most important section: one term =
one heading with a paragraph covering context, usage, traps, and what it is NOT. -->

## Shared Vocabulary
[Key terms, defined VERBOSELY in the context of THIS project.
Not generic definitions, not one-liners — analytical paragraphs covering:
- What the term means in this specific project
- Why it exists as a separate concept
- Where it is used, and what the traps are
- What it is NOT (to avoid confusion with neighbouring terms)

The vocabulary is the most important section of design.md.
Whoever reads it in six months must understand the project FROM SCRATCH
from this section alone.
One term = one H3 heading + an explanatory paragraph.]

### user
A registered profile with a verified email. In this project a "user" is always
a salesperson in a shop, never the end customer. The end customer is a `client`
(a separate model). This distinction is critical: the user sells, the client buys.

### order
A completed transaction with confirmed payment. It excludes abandoned carts and
quotes — those are `draft`. An order always has a payment reference and a
finalisation timestamp.

## Deep Modules
[The real modules of the system — few, deep, with narrow interfaces.
A deep module hides complexity: its callers must not need to know how it works inside.
If you cannot state input/output in 2 lines, the module is not deep enough.]

### [Module name]
- **Interface:** [input] → [output] (1-2 lines — the public contract)
- **Does:** ...
- **Does NOT:** ...
- **Owner:** ...
- **Depends on:** ...

## Interfaces (glue)
[Thin layers that combine the deep modules.
API, CLI, frontend, webhooks — they hold no logic of their own, only orchestration.
If an interface grows complex, there is probably a deep module trying to get out.]

- **[Interface name]** — connects [module A] + [module B], exposed via [channel]

## Non-Negotiable Constraints
- [constraint 1 — why it cannot be touched]
- [constraint 2]

## Open Decisions
[Things that have not been decided — to resolve before proceeding.
Each one with: what to decide, who decides, by when.]

- [ ] [Decision] — Owner: X — By: Y
```

---

### 3. Saving

```python
import os

# Canonical path
design_path = f"wiki/projects/{name}/design.md"

if os.path.exists(f"wiki/projects/{name}/"):
    # Save design.md inside the project folder
    pass
else:
    # Suggest /project to create the project
    # Fallback: save a draft under storage/
    pass

# Log it in the diary (brain-writer, if installed)
create_log(
    date=today,
    title=f"Design: {name}",
    content="Design concept complete. Vocabulary: N terms. Modules: N.",
    tags=['design', domain, name],
    project=name,
)
```

---

### 4. Session context injection

After saving `design.md`, synthesise and inject the session context.
This block does NOT go into the file — it is an operational instruction for the
current session.

```
━━━ ACTIVE SESSION CONTEXT ━━━

Design concept: [2 sentences from the file]

Active vocabulary:
- "[term]" = [definition]
- "[term]" = [definition]
(only the terms whose meaning differs from common usage)

Deep modules: [Name (interface)] | [Name (interface)]
Interfaces (glue): [Name] | [Name]

→ I will use these terms for the rest of the session.
  Correct me if I use one wrongly.
  If the context is lost, I re-read wiki/projects/{name}/design.md.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

### 5. Pipeline check

```python
import os

NEXT_SKILLS = [
    {
        "skill": "devil",
        "label": "/devil",
        "desc": "Tear the design apart — find the weak spots before proceeding",
        "domains": ["all"],
        "flow_position": "validation",
        "fallback": "Ask 'tear this design apart' in chat",
    },
    {
        "skill": "build",
        "label": "/build",
        "desc": "Build mode — TDD + deep modules + return loop. Implements the modules.",
        "domains": ["all"],
        "flow_position": "execution",
        "fallback": "Define each module's interface, test from the outside, implement one piece at a time",
    },
]

for s in NEXT_SKILLS:
    if "all" not in s["domains"] and domain not in s["domains"]:
        continue
    if os.path.exists(f'.claude/skills/{s["skill"]}/'):
        print(f"→ {s['label']} — {s['desc']}")
    else:
        print(f"{s['label']} not installed ({s['flow_position']})")
        print(f"   /brain install {s['skill']}  |  fallback: {s['fallback']}")
```

---

## Related skills

**All optional** — `/design` works standalone.

### Before

| Skill | When | Fallback |
|-------|------|----------|
| `/brainstorm` | Still exploring | Think out loud in chat |
| `/project` | The project already exists in the brain | Describe the context in the argument |

### During

| Skill | When | Fallback |
|-------|------|----------|
| `/budget` | There is a relevant financial constraint | Capture it as a constraint during the grill |
| `/calendar` | There are time milestones | Add them under Open Decisions |

### After

| Skill | When | Fallback |
|-------|------|----------|
| `/devil` | Validating the design | "Tear this design apart" in chat |
| `/todo` | Open Decisions → tracked tasks | Copy them into todo/ by hand |
| `/signals` | Software with GitHub issue tracking | Open issues by hand from the modules |
| `/ghostwriter` | design.md needs to be shared with others | "Rewrite this for [audience]" |
| `/artifact` | Sharing via link | Copy into a shareable document |

### If it goes wrong

| Skill | When | Fallback |
|-------|------|----------|
| `/scar` | Wrong design, failed project | Log it in diary/ with the `post-mortem` tag |

> **Note for brain maintainers:** check what is installed with `ls .claude/skills/` — these are suggestions, not dependencies.

---

## Usage examples

```
/design a wedding in August for 80 people
/design magic-link login for the customer portal
/design a trip to Scotland with 6 people, flexible budget
/design the client onboarding process for the agency
/design a new album with the band — 8 tracks, recorded at home
```

---

## Operating notes

- **Do not skip phases:** grill first, synthesis after. Do not write design.md before you have explored enough.
- **Vocabulary during the grill, not after:** every ambiguous term gets clarified the moment it surfaces.
- **Design concept ≠ PRD:** the design concept is the shared idea. The PRD comes later, if at all.
- **If you cannot write the Design Concept in 3 sentences**, the grill is not over — go back.
- **Deep & Grey is the final test of the synthesis:** more than 3-4 macro-areas usually means you are mixing modules and interfaces. Separate them. If a module has no interface you can state in 2 lines (input → output), it is not deep enough. If you must explain the how to convey the what, it is not grey enough.
- **Handoff to /build:** `/design` defines the high-level interface of each module. `/build` refines it into a technical contract and implements it with TDD + the grey box check. Do not duplicate the work — the design says "what it does and what it does not do", the build says "what it is called and what it returns".

---

## Convention: pipeline awareness

The full flow of this skill family:

```
/brainstorm  →  /design  →  /devil  →  /build
(explore)      (structure)  (validate)  (execute + return loop)
```

Every skill in the flow:
1. Knows where it sits in the flow
2. Checks for the next skills with `os.path.exists('.claude/skills/{name}/')`
3. If one is missing: names it, offers `/brain install`, gives the fallback
4. Does not suggest skills irrelevant to the detected domain

### Flow status

| Skill | Position | Domains | Status |
|-------|----------|---------|--------|
| `/brainstorm` | Pre-design | all | available |
| `/design` | Structuring | all | this skill |
| `/devil` | Validation | all | available |
| `/build` | Execution + return loop | all | available |
