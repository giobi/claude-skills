---
name: formpilot
description: "/formpilot — also answers to /form and /forms, and to plain questions like \"how many applied to Fairtrade?\" or \"show me the CEFTA forms\". Application forms on FormPilot (forms.grworktech.com): list forms, read submissions, design new forms from existing blocks. Your own token, your own role."
user-invocable: true
argument-hint: "[forms | show <form> | submissions <form> [search] | modules]"
---

# `/formpilot` — application forms, from the brain

## Trigger — `/form` and `/forms` are the same thing

The team says "the form", "the Fairtrade form", "the CEFTA forms". Any message about an
application form, its candidates, or building a new one is this skill — `/form`, `/forms`,
`/formpilot` or no slash at all ("did anyone apply to Fairtrade?").

## What you can do depends on your role

The token in `.env` is the owner's own FormPilot account. Two roles exist:

- **viewer** — see forms, read and search submissions, export. Cannot change a form.
- **admin** — all of the above, plus create, clone, edit and open/close forms.

A viewer asking for a write gets a clear `PermissionError`; relay it, don't retry. Nobody can
delete a form through the API, by design.

**Perimeter.** An account may be restricted to some forms (one client's recruiter sees that
client's forms only). `forms` lists exactly what this account may see; anything else answers
`403 This form is not yours to see` — that is the system working, not a bug. Never work around
it, never guess ids from other brains: the list this account gets is the whole of its world.

## NLP-first

- "how many people applied to Fairtrade?" → `submissions fairtrade`, answer with the count
  and the names — and say out loud when entries look like tests (team addresses, "test").
- "who applied this week?" → `submissions <form>`, filter by date in the reply.
- "show me the Fairtrade form" → `show fairtrade`: sections and fields, readable.
- "which forms do we have open?" → `forms`.
- "make a form like the CEFTA Finance one for X" → admin only: `clone_form()` then edit,
  and show the owner what you are about to open before `toggle_status()`.

## Usage

```bash
python3 .claude/skills/formpilot/formpilot.py forms                       # all forms, status, count
python3 .claude/skills/formpilot/formpilot.py show fairtrade              # id, slug or part of the title
python3 .claude/skills/formpilot/formpilot.py submissions fairtrade       # who applied
python3 .claude/skills/formpilot/formpilot.py submissions 11 "Rossi"      # search inside the answers
python3 .claude/skills/formpilot/formpilot.py modules                     # field blocks used across forms
```

```python
import sys
sys.path.insert(0, '.claude/skills/formpilot')
from formpilot import (
    list_forms, get_form, list_submissions, list_modules,
    create_form, clone_form, update_form, toggle_status,   # the last four: admin role
)

sub = list_submissions(form_id=11, search="Rossi")
print(sub["meta"]["total"], "matches")

modules = list_modules()        # every field block used across all forms/sections
new_form = create_form("New position", clone_from=3)     # copy a sibling form, starts closed
form = get_form(new_form["id"])
form["config"]["sections"][0]["fields"].append({"type": "tel", "name": "phone", "label": "Phone"})
update_form(new_form["id"], config=form["config"])
toggle_status(new_form["id"])   # open it
```

A form's config is `{"sections": [{"type", "title", "fields": [...]}]}` — fields live inside
sections, never flat. Field shapes vary a little by type (`select`/`radio` carry `options`,
`checkbox` carries `checkbox_label`): copy the shape of an existing block from `modules`
rather than guessing.

## The candidates live here, not in the committee portal

The admin panel is https://forms.grworktech.com/admin — login by magic link, no password;
anyone with a company address gets an account on their first login request. Submissions are
on each form's page, with CSV export. Demo portals built elsewhere (artifacts, mockups) are
not the data: when someone cannot find the applicants, send them to the admin panel or
answer from `submissions`.

## Setup

`FORMPILOT_API_TOKEN` and `FORMPILOT_API_URL` in the brain's `.env`. If missing or rejected
(`ValueError` / 401): the owner creates a new one at forms.grworktech.com → **API Tokens** →
Create, and pastes it into `.env`. Plaintext tokens are shown once and never recoverable —
reissue, never ask for the old one.

## Where this comes from

Built 2026-09-22 for David Caggiari-Pallett's brain (Giant), on top of the admin API
(`App\Http\Controllers\Api\FormApiController`, FormPilot repo `github.com/giobi/formpilot`,
branch `generations` = this deployment). Promoted to a shared skill on 2026-10-01 with a
read-only CLI, so every brain on the installation uses one copy. 1.1 (same day): per-account
form perimeter documented.
