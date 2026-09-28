---
name: build
description: Build mode — TDD + deep-module architecture + a return loop that keeps the design alive. Implements the macro-areas of a design.
user-invocable: true
argument-hint: "[macro-area or feature to implement]"
---

# /build — Build Mode

**Source:** Failure Modes 3, 4, 5 and 6 of the talk "Software Fundamentals Matter More Than Ever" by Matt Pocock (2026). It combines TDD (small verifiable steps), deep modules (clean boundaries, simple interfaces — John Ousterhout) and grey box delegation (design the interface, delegate the implementation). It adds a return loop back into `/design` to keep the map alive.

**The problem it solves:** an unconstrained AI does too much at once ("outrunning your headlights"), ignores module boundaries, and produces codebases of shallow modules that are impossible to navigate or test. You leave those sessions exhausted, because you had to hold everything in your head. `/build` imposes a rhythm and a structure that fix both.

---

## Two things together, not separable

`/build` fuses two disciplines that make no sense apart:

**TDD** — the rhythm. One test at a time, one implementation at a time. The feedback loop is the speed limit. No code without a test that demands it.

**Deep modules** — the structure. Every piece of work has clean boundaries: a small interface that you design, a large implementation that the AI can write. You test from the interface, not from the internals.

Plus a third piece that is neither:

**The return loop** — after each completed module, `/build` updates design.md with the real state. The map stays alive instead of decaying into a document from the start of the project.

---

## When to use /build

- After `/design` — you have a design.md with macro-areas and a vocabulary
- After `/devil` — the design has been validated
- When you are about to implement something non-trivial
- When you notice you are "running" without verifying

**Do not use /build:**
- Quick, obvious fixes
- Throwaway prototypes where speed matters more than stability
- Work with no design.md (run `/design` first)

---

## Workflow

### 0. Load context

```python
args = "$ARGUMENTS".strip()

# Read the active project's design.md
# wiki/projects/{name}/design.md → macro-areas, vocabulary, constraints

# If there is no design.md:
# → suggest /design before proceeding
# → fallback: ask the user to describe what they are building

# Stack detection (to pick the test framework):
# composer.json  → PHP/Laravel → Pest/PHPUnit
# package.json   → Node/React  → Vitest/Jest
# pyproject.toml → Python      → pytest
```

**Mandatory questions at startup** — unless design.md or the context already answers them:

1. **Where does the code live?** — repo path, git remote. Do not assume the current directory.
2. **Where does staging run?** — server, URL, how to deploy there for testing.
3. **Where does production run?** — server, URL, how to deploy a release.
4. **Skill config** — read `wiki/skills/build.md` if it exists. Rules there **override** the defaults in this SKILL.md (e.g. RefreshDatabase, mocking).

If the project is a local module with no server and no deploy, questions 2-3 do not apply. But **always ask them for anything with a server or a web app**.

### 1. Pick the macro-area

If the user says what to implement, map it onto the matching area of design.md.
If not, show the map and ask.

```
━━━ MACRO-AREA MAP (from design.md) ━━━

1. [Area A] — not started
2. [Area B] — not started
3. [Area C] — depends on: Area A

Which area are we implementing?
```

### 2. Define the interface

Before any code, define the macro-area's interface.

The interface is the public contract — what goes in, what comes out, what the caller is allowed to do. The implementation is everything else.

```
━━━ INTERFACE: [Area name] ━━━

Input:   [what it receives]
Output:  [what it returns / produces]
Effects: [side effects: writes to the DB, sends email, ...]

Does NOT: [explicit boundaries]
Depends on: [other areas]
```

Show it to the user and confirm before proceeding.

### 3. TDD plan for the area

Break the area into testable units, ordered by dependency:

```markdown
## Plan: [Area name]

1. [ ] [Behaviour 1] — test: [what it verifies]
2. [ ] [Behaviour 2] — test: [what it verifies]
3. [ ] [Behaviour 3] — depends on: 1
...

## Out of scope
[Everything we are NOT implementing in this cycle]
```

Confirm with the user before proceeding.

### 4. Red → Green → Refactor loop

For every unit in the plan, strictly in order:

```
┌─────────────────────────────────────────────┐
│                                             │
│  RED       Write THE test (one only).       │
│            It must fail for the right       │
│            reason.                          │
│                                             │
│  GREEN     Implement the MINIMUM that makes │
│            it pass. Nothing more.           │
│            Do not anticipate future tests.  │
│                                             │
│  REFACTOR  Improve the code. Tests green.   │
│            If they go red → roll back.      │
│                                             │
│  DONE      Tick the box in the plan.        │
│            Next unit.                       │
│                                             │
└─────────────────────────────────────────────┘
```

**Architectural signals during the loop:**

- **The test is hard to write** → the module is shallow, the boundaries are wrong. Stop and redesign the interface.
- **The implementation reaches outside the area** → the boundary leaks. Stop and redefine what is in and what is out.
- **You need to know another module's internals** → the coupling is too tight. That module's interface is not deep enough.

When you hit a signal: **say so explicitly**, propose the architectural fix, and do not proceed until it is resolved.

### 5. Grey box check

After completing an area:

```
━━━ GREY BOX CHECK: [Area name] ━━━

Interface defined:            yes
Tested from the interface:    yes (N tests)
Implementation delegatable:   [yes/no]

If yes → this module is a grey box.
Future sessions need not understand the inside —
the tests passing and the interface holding is enough.
```

This is the real cognitive saving. You no longer have to hold this module's implementation in your head.

### 6. Return loop → update design.md

After each completed area, update design.md:

```
# Update the macro-area's state in design.md
# not started → complete (grey box, N tests)
# Add notes if the boundaries moved during the build
# If new unplanned areas surfaced → add them as "not started"
```

Show the updated map:

```
━━━ UPDATED MAP ━━━

1. [Area A] — complete (grey box, 8 tests)
2. [Area B] — ready (dependencies resolved)
3. [Area C] — not started
4. [Area D] — NEW, surfaced while building Area A

→ Next area? Or do we update the design?
```

If the boundaries moved significantly → suggest re-running `/design` on the part that changed.

---

## Parallelisation — one subagent per area or bug

When the plan's macro-areas (Step 1) are **independent of each other** (no mutual "depends on") — typically backend/frontend/infra on one feature, or several unrelated bugs in the same project — there is no need to do them one at a time. Assign a subagent per area or bug and run them **in parallel**, each with its interface (Step 2) and its TDD plan (Step 3) defined *before* launching it.

**When NOT to:** a small project, a single area, or areas that touch or depend on each other. Two subagents editing the same file in parallel produce conflicts; that friction is avoidable by choosing what to parallelise. The test is simple: if a single human developer would split the work between two people (backend and frontend, or two unrelated bugs), parallelise; if they would knock it out alone in an afternoon, do not.

**Every subagent, without exception:**
- **Real development environment**, not mocks, wherever possible — real repo and staging, a real database (small or test-grade is fine, but not a fake in-memory one when the real environment is something else), real external services with their test keys. If a mock is genuinely necessary (cost, time or risk of the real service), it must be **declared explicitly in the final report**, never assumed silently.
- **End-to-end TDD**: reproduce the problem or behaviour BEFORE the fix (a baseline that fails for the right reason), then implement, then verify end-to-end with a real write, call or run — not "the code compiles", and not a synthetic assertion that runs against nothing. Same discipline as Step 4, applied by an isolated executor instead of inline.
- **Confined, declared scope**: it is told explicitly what is in and what is out (the same idea as the explicit boundaries in Step 2). It must not improvise into adjacent, unassigned scope.
- **Updates its own state as it goes, not only at the end** — a dedicated tracking entry (one per subagent, never shared) with comments added along the way, so whoever is coordinating can check progress without waiting for the final report and without reading the subagent's transcript.
- **Does not deploy or push on its own** when the work touches shared staging or production. It stops at local/staging verification and leaves the merge and deploy to the coordinator, who sees all the pieces together before propagating anything.

**The coordinator** (the main session):
- Launches the independent subagents **in the same turn** (parallel calls), not in sequence — otherwise the whole point is lost.
- Does not sit blocked: it continues other work, or stays with the user, until the completion notifications arrive.
- **Before integrating**: re-reads what each subagent actually changed (the real diffs, not the summary — a summary describes intent, not necessarily outcome), and checks that different areas have not touched the same file incompatibly.
- Runs the grey box check (Step 5) and the merge/deploy per area, in dependency order if any were discovered along the way.
- Updates design.md (Step 6) once, with the state of ALL areas, not once per subagent.

Origin: two unrelated bugs in one project (a cross-instance notification bug in the backend, and an agent-behaviour bug on one model) assigned to two subagents in parallel on staging, both with reproduce-before-fix and end-to-end verification against real systems and models rather than mocks. They came back with verified fixes in roughly half the time of a sequential pass. The fleet deploy (three installations) was done by the main session after reviewing the diffs, not by the subagents.

---

## Human check via /radar

When a cycle of end-to-end TDD (Step 4, or a subagent from the section above) produces something **visitable in a browser** — a page, a flow, an authenticated endpoint — `/build` is **free to run `/radar`** (or update an existing radar page) on its own initiative, without asking first, if it judges that this gives a better human check than a description in words. It is not a mandatory step on every cycle: it fires when the end-to-end verification produced something worth looking at with your eyes (a login flow, a computation shown on the page, a visual before/after). A silent CLI test that simply passes does not call for it.

The point is to hand the user **clickable links** rather than a summary: the radar page becomes the place where they find "what the application does right now", held to the same standard as the rest of the Radar protocol (real Playwright screenshots — Rule 0 in `radar/SKILL.md` — not a CLI call passed off as visual verification).

This applies both to the main session in `/build` and to a subagent from the parallelisation section. In the second case the subagent **declares in its own report** that it published or updated the radar page, and gives the link — it does not do so silently behind the coordinator's back.

---

## Testing policy — environment-aware

`/build` detects the environment type and adapts test behaviour accordingly.

### Detection

The first step of `/build` is working out **where** you are working and **under which rules**.

```python
# 1. Try to work it out yourself
#    - .env APP_ENV, APP_URL, DB_DATABASE
#    - SSH host (local? remote? staging?)
#    - wiki/projects/{name}/index.md → server, environment, notes
#    - Presence of real data versus seeds/factories

# 2. If you are not sure → ASK
#    "I am about to work on [domain/path]. Does it hold real data, or can I be
#     destructive? Is mocking fine, or do you want tests against real data?"

# 3. NEVER assume "testing" as the default
#    There is no default. Infer, then confirm. Be cautious.
```

**Ask once** at the start of the `/build` session. The answer holds for the whole session.

**No default.** Infer from the environment, state your reading, ask for confirmation. Never assume.

### Rules per environment (agnostic defaults)

| Environment | Destructive | Mocking | RefreshDatabase | Backup first |
|-------------|:-----------:|:-------:|:---------------:|:------------:|
| **testing** (empty/seeded DB) | yes | yes | ask | no |
| **development** (local) | yes | ask | ask | no |
| **staging** (real data) | NEVER | ask | NEVER | always |
| **production** | NEVER | ask | NEVER | always |

**IMPORTANT:** if `wiki/skills/build.md` exists, the rules there **override** this table. Always read it when `/build` starts.

### Staging with real data

**This is the common case.** Staging platforms hold data entered by the team — colleagues, clients, testers. That data is not expendable.

Rules:
- **NEVER `RefreshDatabase`** — the data is not yours
- **NEVER truncate, mass-delete, or let a factory pollute** — you are working in someone else's garden
- **NEVER mock without asking** — most users prefer tests against real data and real services
- **Read-only or additive tests** — assert against existing data, or create records you then clean up surgically
- **If a destructive test is genuinely needed** → back up first (a dump to local disk, plus remote object storage if configured), then test, then roll back if needed
- **Transaction wrapping** — if the framework supports it, wrap the single test in a transaction that rolls back, leaving the shared database untouched

### Pre-test backup

```bash
# Minimum: a dump to local disk
mysqldump -u"$USER" -p"$PASS" "$DB" > /tmp/$DB-pre-test-$(date +%s).sql

# Better: to remote object storage as well (S3, R2, ...)
php artisan app:dbbackup --filename="$DB-pre-test-$(date +%Y%m%d%H%M%S).sql"
```

The backup is **mandatory** before any operation that modifies data on staging or production.
The rollback must be one command away.

---

## Build-mode rules

These rules are active for the whole session.

| Rule | Detail |
|------|--------|
| **Interface first** | Define the public contract before writing code |
| **Test first** | No implementation without a test that demands it |
| **One step at a time** | One test → one implementation → refactor → next |
| **Minimum green** | Only the code needed to pass the current test |
| **Signals are mandatory** | Hard test or leaking boundary → stop, do not proceed |
| **Explicit grey box** | After each area: state whether it is delegatable |
| **Living map** | design.md updated after every completed area |
| **Code in English** | Identifiers, comments, logs, error messages, columns, subcommands. See below |
| **Parallelise independent areas** | Backend/frontend, or unrelated bugs in one project → subagents in parallel, not in a queue. See above |

### Code in English

Everything you write in `/build` is in English: variable, function, class, file and column names, comments, log and error messages, CLI subcommands, config keys. The conversation with the user stays in their language — the code does not.

Three boundaries, so the rule does not become a rake to step on:

- **Text aimed at the end user is not code.** Labels, copy, emails and interface messages follow the product's language. It is the identifier around that text that stays in English.
- **Do not translate something that is already a contract.** Production columns, API fields, config keys other systems read, endpoints, event names: renaming those is a migration. You plan it, you do not do it in passing.
- **No mass renames of existing code.** Convert what you are already touching for another reason. A wholesale linguistic refactor breaks things no test covers, and it is not the work you were asked to do.

---

## Related skills

| Skill | When | Fallback |
|-------|------|----------|
| `/design` | Before — you need a design.md | Describe what you are building in chat, but it will be less precise |
| `/devil` | Before — validate the design | "Tear this design apart" in chat |
| `/playw` | Frontend — a quick screenshot after each RED→GREEN→REFACTOR cycle, a light sidecar while you work | Manual screenshot |
| `/radar` | Before calling a frontend or e2e area verified — real login (CLI or magic link, never a console session alone), Playwright navigation, before/after screenshots, a report with clickable links. Rule 0 of that skill: "never a report built from the CLI alone". It is the level above `/playw`: that one is for during, this one is for "actually verified" at the end of a cycle | Manual screenshot plus a written description of what you saw |
| `/scar` | Something went wrong during the build | Log it in diary/ with the post-mortem tag |

---

## Position in the flow

```
/brainstorm → /design → /devil → [/build] → ···
                 ↑                    │
                 └────────────────────┘
                     return loop
                 (design.md updated)
```

`/build` is the last operational link. The return loop back into `/design` is the piece that keeps the system alive.

---

## Beyond software

This skill was born for code, but the pattern is universal.

For any complex project with macro-areas defined in a design.md — an event, a renovation, a campaign — the cycle is the same: take an area → define what it must do and what it must not → verify one piece at a time → mark it handled → update the map → next area.

"Interfaces" become explicit agreements (with the supplier, the team, the group). "Tests" become concrete checks ("has the caterer confirmed for 80? yes"). "Architectural signals" become conflicts between areas ("the venue constrains the catering → the boundary needs redrawing").

If you use `/build` outside software, ignore the parts about test frameworks and adapt the vocabulary to the domain.

---

## Usage examples

```
/build the authentication area of the customer portal
/build the notifications module — isolate sending from scheduling
/build the catering macro-area of the wedding
/build client onboarding — first step
```

---

## Flow status

| Skill | Position | Domains | Status |
|-------|----------|---------|--------|
| `/brainstorm` | Pre-design | all | available |
| `/design` | Structuring | all | available |
| `/devil` | Validation | all | available |
| `/build` | Execution | all | this skill |
| `/tdd` | Reference (folded into /build) | software | reference |
