---
name: artifact
requires:
  capabilities: [web_serving]
description: "Artifacts — build static mini-sites, reports and reveal.js slideshows, hand out the internal address, publish only on demand. Triggers: slideshow, presentation, slides, deck, one-pager, one-page."
user-invocable: true
argument-hint: "[link|list|create|update|delete|publish|revoke|rebuild-index|slideshow] [slug] [title]"
parameters:
  - name: public_dir
    description: "Path to the public/ directory relative to the brain root"
    default: "public"
  - name: template_dir
    description: "Path to templates inside the public dir"
    default: "public/template"
  - name: default_days
    description: "Default publication lifetime in days (share-token installs)"
    default: 30
---

# /artifact — Artifacts Manager

Build static mini-sites, reports and reveal.js slideshows in `public/`, and hand
out the right address for them. Formerly `/public`; that name still works as an
alias.

**Before using:** read `boot/local.yaml` (`public:` section) for this install's
infrastructure, and `wiki/skills/artifact.md` for skill options.

## Trigger — "slideshow" means run the slideshow driver, not write a page of text

If the user says (in any language) **slideshow, presentation, slides, deck,
one-pager, one-page, "una pagina", "fammi una presentazione"** — that is a
request for `slideshow.py`, below. It is **not** a request for a report page,
and answering it with paragraphs of text is the bug this trigger exists to
close: on 2026-09-15, asked twice in the same call for "a slideshow, one page",
the brain answered with text both times (village TODO #1534). If in doubt
between a slideshow and a static page, ask; do not default to text.

## Rule zero — the URL is a fact you read, never a fact you compose

Writing the files and making them reachable are two different steps, and only the
platform knows the resulting address. So:

1. **Never invent, guess, or pattern-match a URL.** Not from the brain slug, not
   from the folder name, not from an old link you saw in a chat, not from
   `PUBLIC_URL` in `.env` (stale in many installs).
2. **Get the URL from the driver** — `share.py link` for the internal address,
   `share.py list` / `share.py publish` for token URLs, or `{base_url}/{slug}/`
   for the `static` driver. That output is the only address you may give the user.
3. **Verify before delivering.** For a token URL,
   `curl -s -o /dev/null -w '%{http_code}' <url>` must return 200. A 302 to a login
   page means it is *not* public.
4. **If it isn't published, say so.** "It isn't published, that link doesn't exist
   yet" is a correct answer. A plausible-looking dead link is not — it costs the
   user several rounds of 404s before they find out you were guessing.
5. **Never explain the platform's behaviour from intuition.** If a link fails, run
   the check and read the error. Do not tell the user *why* it failed (or what to
   click) unless you verified it.

## The two addresses — which one to hand out, and when

An artifact has **two** addresses, and they are not interchangeable. Handing out
the wrong one is how a client's material ends up on the open web.

| | Internal | Token |
|---|---|---|
| Shape | `/artifact/{brain}/{folder}/` | `/share/{token}` |
| Who can open it | whoever is logged into the village | **anyone holding the link** |
| Expiry | none | yes, needs renewing |
| Share bar | yes, for the owner | no (it is the recipient's view) |
| How you get it | `share.py link <folder>` | `share.py publish <folder>` |

**The internal address is the default. Always.**

When the user asks for a page, a report, a profile, an artifact — anything that
ends up in `public/` — you write it and give them the **internal** link. That's it.
You do not publish. You do not ask whether they want to publish. You do not bring
publishing up. They open it, look at it, have you fix it: it is their working
material, not something that leaves the building.

**Publishing is a second step, and it is their call.**

Offer to publish **only** when the conversation shows the page has to reach someone
who is not in the village: a client, a candidate, an outside party. Even then you
do not publish — you **ask**, and you say what it means:

> To send this to [name] I have to make it public: anyone with the link can open
> it, without logging in, for N days. Shall I?

Then you wait for the answer. **Publishing without being asked is a mistake, not a
courtesy**: it puts on the open web something the user believed was internal. If
you are unsure whether it is needed, the answer is the internal address plus a
question.

**What is NOT a request to publish:** "make me a page", "put together a report",
"put it in a page I can look at", "make me an artifact". Those are all requests to
*write*. The internal link satisfies every one of them.

### The reason, which matters more than the rule

This skill used to be able to produce exactly one kind of link, the token one.
Since rule zero forbids it — rightly — from composing URLs by hand, the only way it
had of answering "here's the link" was to **publish**. That was not a choice: it
was the only exit the code left it, and the result was pages carrying client data
on the open web every time somebody asked for a page.

The driver now knows both addresses, so the alibi is gone.

### Rule zero has not been relaxed

`share.py link` does **not** compose the URL blind: it checks the folder exists on
disk, and probes the route on this install. If either is missing it returns nothing
and says why.

Watch out for one trap: a protected route answers **302 (go to login) for any
path**, existing or not. So a 302 proves *the route* exists on this install, and
**never** that *the folder* does. Never use an HTTP response as proof that an
artifact exists — and never hand-compose `/artifact/...` trusting the pattern: ask
`share.py link`, which performs both checks.

### The `folder` argument is relative to `public/` — and both spellings are accepted

`link`, `publish` and `revoke` all take a folder **relative to `public/`**: the page
at `public/plukon-proposal/` is `plukon-proposal`.

Writing the prefix (`public/plukon-proposal`) used to make the server look for
`public/public/plukon-proposal` and answer a bare `folder not found` — which reads
like the publishing service is down rather than like a wrong argument, and has been
reported as an outage more than once. Since 1.4 the prefix is **normalised away**, so
both spellings resolve to the same folder, and when a folder genuinely is not there
the error names the rule and the spelling that would have worked.

A brain that really does have a folder called `public` inside `public/` is not
affected: the literal path on disk always wins, and the prefix is only read as a slip
when the literal path does not exist and the stripped one does.

## Configuration

**Infrastructure is not configured here.** The public host, the endpoint, any
always-public path are facts about the machine: they are declared in
**`boot/local.yaml`**, `public:` section, and that is where `share.py` reads them.
The rules live in `boot/domain.md`. This is the brain protocol separation — machine
in `local.yaml`, skill config in `wiki/skills/`, secrets in `.env` — and it holds
because an infrastructural fact inferred from the environment is the same class of
error this skill exists to close.

```yaml
# boot/local.yaml — the install's declaration
public:
  path: public/
  mode: share-token                                   # share-token | static
  base_url: https://install.example.com               # host that appears in links
  share_api: https://install.example.com/api/share/cli
  share_api_internal: https://abc-nginx/api/share/cli  # fallback, TLS not verified
  static_url: null                                    # only where one really exists
  brain_slug: brainname                               # how the app knows this brain
```

```yaml
# wiki/skills/artifact.md — skill options only
---
public_dir: public
template_dir: public/template
default_days: 30
---
```

If `local.yaml` does not declare the section, `share.py` falls back to the
container environment so older brains keep working, and `doctor` flags it with
`infra_declared: NO`. That is a fallback, not the right way: declare it.

## Driver `share-cli` — ABChat installs

`public/` is not served by a web root. Each folder gets an internal, auth-gated
address, and can additionally be published on demand for an **opaque token URL**
(`{install}/share/{token}/…`) that expires. The token is generated by the app and
cannot be derived from anything the brain knows.

```bash
python3 .claude/skills/artifact/share.py doctor                    # what is alive on THIS install
python3 .claude/skills/artifact/share.py link  client-report       # internal address — the default
python3 .claude/skills/artifact/share.py list                      # published + unpublished, with addresses
python3 .claude/skills/artifact/share.py publish client-report     # publish, print the token URL
python3 .claude/skills/artifact/share.py publish client-report --days 7 --password secret
python3 .claude/skills/artifact/share.py revoke  client-report     # kill the link
```

### Fleet installs are not identical — run `doctor` before saying anything

Same codebase, different infrastructure. Measured on 2026-08-03 by actually running
publish → `curl` → revoke on each:

| Install | endpoint used by the brain | host in links | always-public static |
|---|---|---|---|
| avocado (`abc`) | `avocado.abchat.it` → 301 to the canonical host | `abchat.it` | no |
| grbrain (`grb`) | `grbrain.com` directly | `grbrain.com` | **yes**, `public.grworktech.com/{slug}/` (being retired) |
| emibrain (`emi`) | on-prem: the public host is **not reachable from the container**, it goes through `emi-nginx` | `brain.emisfera.it` | no |

Do not memorise this table: **`doctor` recomputes it**. It exists precisely because
a config written months ago lies (on emibrain 19 containers out of 25 still carry
`INSTANCE_HOST=v2.emibrain.it`, a dead vhost).

Two traps `share.py` handles, worth knowing if something looks off:

- **The app builds the URL from the request host, not from `APP_URL`.** Knocking on
  the internal nginx would return `https://emi-nginx/share/…`, a container name
  nobody can open. Hence the canonical `Host:` header on the internal hop, taken
  from `public.base_url` in `boot/local.yaml`. If a link on an internal host comes
  back anyway, `share.py` **refuses to print it** and says what to configure.
- **The slug is not in the same place everywhere**: on avocado `manifest.json`
  carries the UID and not the slug, on grbrain the right slug. Candidates are tried
  in order.

Facts about this driver, verified — do not extrapolate beyond them:

- **A published folder serves everything under it**, at any depth. If the whole of
  `public/` is published, `…/share/{token}/report.html` and
  `…/share/{token}/report/index.html` both work. **A file directly inside `public/`
  does not need to be wrapped in a folder with an `index.html`** — that is a myth.
- `index.html` is served automatically when the URL points at a folder — so a
  folder is still the tidier shape for a multi-file site.
- Publishing is **idempotent per folder**: re-publishing extends the expiry and
  keeps the same link. Revoking and re-publishing mints a **new** token.
- Max 90 days. An expired publication returns an error page, not the content.
- The user can also publish from the web UI. Either way, `share.py list` is the
  truth — check it before saying anything about what is or isn't public.

## Driver `static`

`public/` is served by a web root at `base_url`. The URL of a site is
`{base_url}/{slug}/`. Nothing to publish: writing the file is enough. Still verify
with `curl` before handing over the link.

## Driver `slideshow` — reveal.js presentations

A different medium from the five artifact-1.css layouts above: fullscreen, one
screen at a time, not a scrollable page. Use it whenever the trigger above
fires. Reference implementation this was adapted from: efesto's `/talk` skill
(not part of the fleet, but the working prior art for a reveal.js deck out of a
brain's own context).

```bash
python3 .claude/skills/artifact/slideshow.py <slug> --title "T" [--subtitle "S"] \
        [--from <existing-artifact-slug>] [--one-page]
```

- `<slug>` — destination folder under `public/`, same rules as everywhere else
  (kebab-case, `index.html` is the main file).
- `--from <existing-slug>` — build the deck **from an artifact already in
  `public/`**: its `<h2>` sections become slides, the text under each becomes
  bullets. This is the "slideshow from this artifact" case — do not re-type
  content that already exists on a page, point the driver at it.
- `--one-page` — the literal "slideshow, one page" ask: every section
  flattened onto a **single** fullscreen slide instead of a multi-slide deck.
  Reach for this before a 10-slide deck when the user said "one page", "a
  single slide", "one-pager" — it is not the same request as a full deck.
- No `--from` (or a source with no `<h2>` sections): the script writes a
  scaffold (title slide + one placeholder slide) and says so — fill the
  content by **editing `public/<slug>/index.html` directly**, same iterative
  flow as every other artifact. It never invents slide content.
- Template lives in `shared/core/templates/minisite/slideshow.html`
  (placeholders `{title}` `{slides_html}`, filled by the script) — edit it to
  change the look of every deck generated afterward, not per-artifact.

The script does not print a URL — rule zero applies here too: get the address
with `share.py link <slug>` afterward, same as any other artifact.

## Commands

```
/artifact link <slug>             The INTERNAL address (default: use this)
/artifact list                    What is published right now + the unpublished folders
/artifact create <slug> <title>   Create a new mini-site from a template
/artifact update <slug>           Update an existing site
/artifact delete <slug>           Delete a site
/artifact slideshow <slug>        Reveal.js presentation — see "Driver slideshow" above
/artifact publish <slug>          (share-cli) Publish and return the token link
/artifact revoke <slug>           (share-cli) Kill the link
/artifact rebuild-index           Regenerate the index page
```

## Rules

1. **Reason about the page before writing anything, out loud, in three steps.**
   Open `/assets/artifact/templates/index.html` — five layouts (timeline, faq,
   gallery, event, directory), each a different structure (grid, nav, block
   sequence) for a different job. Then:
   - **Layout**: which of the five solves the problem this page solves? Pick by
     job, not by taste — a sequence of dated things is `timeline` even on a page
     you'd rather looked like `directory`. A page of questions and answers is
     `faq`, not a wall of text with bold questions. A single date/place/action
     is `event`, not a `timeline` with one entry.
   - **Palette**: pick one of the five palettes in `palettes.html` (or the
     layout's own default). Rotating the palette is how two artifacts from the
     same batch — the same class, the same batch of candidates — read as a
     family without being identical. Don't invent a sixth colour.
   - **Density**: keep the layout's own padding for normal content. Widen it a
     notch for a page that is short on content and wants to read as more
     considered; tighten it for a page dense with numbers.
   Say the reasoning, then act on it — e.g. *"this is a progress log for a
   school project, so I use the Timeline layout, not FAQ or Gallery: the content
   is a sequence of things that happened, not questions or images. The group
   updates it often, so I widen the padding one step so it doesn't read as
   cramped; to tell it apart from the other pages in the same class I rotate the
   palette to Cobalt instead of Slate — same structure, same type system, only
   the accent changes."* Copy the chosen layout, keep its type pairing, replace
   the example content with real content. If none of the five fits (a short
   one-screen note, something with no real precedent), only then fall back to
   `{template_dir}/base.html` — still check `{template_dir}/` for available
   templates first.
2. **Start from the shared base.** Every layout (and `base.html`) links
   `/assets/artifact/artifact-1.css` — see "Design". Write your own CSS only for
   what the base does not cover, in a `<style>` block placed AFTER the link. No
   fonts from external CDNs: self-host, like the five layouts already do
   (`/assets/artifact/fonts/`) — a page that depends on a third-party font host
   either waits on it or tells that host who is reading, and this brain does
   neither.
3. **No sensitive data.** A published page is readable by anyone holding the URL.
   Never passwords, tokens, personal data, or client-confidential material. Ask the
   user before publishing anything that mentions a third party. **Publishing is
   never the default**: see "The two addresses" above. If you were not asked, hand
   out the internal link.
4. **Kebab-case names.** All folder names lowercase with hyphens.
5. **Main file = `index.html`.** For multi-file sites.
6. **Only facts you sourced.** A page is a deliverable: every number, dimension,
   name, and date in it must come from a document, a message, or the user — not
   from a plausible reconstruction. If a value is missing, leave a visible gap
   ("to be confirmed") instead of filling it in. An invented figure on a page the
   user forwards to a contractor or a client is worse than an empty cell.

## Design — five layouts on three independent axes, then the shared base

**Start at `/assets/artifact/templates/index.html`.** It links the five ready
layouts — see rule 1 for how to pick one and how to reason about it. They are
not five closed identities: layout, palette and padding are three separate
choices, and only the layout is tied to the job. A changelog, a set of FAQ and
an event invite are different jobs; they should not share one structure because
writing a new one felt like more work. Two pages that are the *same* job for
the *same* batch (two candidates, two classes in the same course) should share
the layout and differ only by a palette rotation — that is what makes them read
as a family instead of as five unrelated brands.

Every artifact — the five layouts included — starts from a **shared base**: a
stylesheet served by the platform, not pasted into the page.

```html
<link rel="stylesheet" href="/assets/artifact/artifact-1.css">
```

The plain fallback template is in `{template_dir}/base.html`: copy it, drop the
blocks you don't need, fill the placeholders `{{TITOLO}}` `{{SOTTOTITOLO}}`
`{{DATA}}` `{{PIEDE}}` `{{LANG}}`. Reach for it only when none of the four
layouts fits — see rule 1.

**Why linked and not pasted.** A fix to the stylesheet reaches pages that were
already written. That is the whole point of having a base: if every page carries
its own copy, the consistency is a snapshot of the day you wrote it and diverges
from then on.

**Version in the name, updates inside.** Refinements and fixes go into
`artifact-1.css` and apply to everyone. A redesign that would *break* existing
pages becomes `artifact-2.css`, and pages pointing at 1 stay intact. Do not append
`?v=` to the link: changing it on every edit defeats the cache exactly when it is
needed.

**It is not mandatory.** A page that has to look entirely its own removes the link
line and dresses itself. The base exists to start the majority off well, not to
forbid the exception.

**To customise, redefine the variables — not the rules.** Variables survive updates
to the stylesheet; an overridden rule does not:

```html
<style>:root{ --accent:#0b5fa5; --width:960px; }</style>
```

### Data blocks

| Block | Class | For |
|--------|--------|-----|
| Key figures | `.stat-grid` with `.num` / `.lab` | metrics, KPIs |
| Bar chart | `.bar-chart` → `.bar-row` with `style="--v:75"` | comparing items. Pure CSS, no library |
| Progress | `.progress` with `style="--v:40"` | state of a search, of a pipeline |
| Timeline | `.timeline` (`li.step` / `.ok` / `.closed`) | the history of an assignment, milestones |
| Comparison | `.compare` (`.pro` / `.con`) | two options side by side, before/after |
| Quote | `.quote` + `.quote-by` | somebody's words, reported |
| Callout | `.callout info\|warn\|risk` | the tones. `.highlight-box` remains the neutral conclusion |
| Tag | `.tag` | skills, sectors, labels |
| Person | `.person` (`.person-name` `.person-role` `.person-ref`) | a contact line |
| Table | `.data-table`, `td.num` for numbers | structured rows |
| Key/value | `.kv-card` | reference cards |
| Links | `.link-list` | lists of links |
| Missing value | `.missing` | "to be confirmed" — see rule 6 |

The chart and the progress bar draw themselves from the value: `<div class="bar"
style="--v:75"></div>`. 0 to 100. No canvas, no library: it prints, a screen reader
reads it, and it does not depend on a script that might not load.

A `.quote` must **look like** a quote: if you put a client's words inside an
ordinary paragraph, the reader takes them for our own statement.

### Filterable and sortable table

```html
<script src="/assets/artifact/artifact-1.js" defer></script>
...
<table class="data-table" data-filter="Filter candidates…">
  <thead><tr><th data-sort>Name</th><th data-sort="num">Years</th></tr></thead>
```

`data-filter` adds the search bar with the counter; `data-sort` makes a column
sortable, `data-sort="num"` sorts it as a number. If the script does not load it
stays an ordinary table and still reads fine: **no content may depend on the script
to be seen**.

### Structural components

| Component | Class | Notes |
|-----------|--------|-------|
| Header | `.page-header` | install logo + date. Always at the top |
| Header, dotted variant | `.page-header.trama` | same header, a dot pattern instead of a plain border. Colour from `--hero-1` (dots) and `--hero-2` (fill) — override both per artifact for a family look with its own accent |
| Navigation | `.nav-bar` | internal anchors or pages of the artifact; the active one takes `aria-current` or `.attivo` |
| Two-column layout | `.with-sidebar` + `.sidebar` | below 720px the side column becomes a block at the end, on its own |
| Table of contents in the sidebar | `.sidebar .toc` | a list of anchors |
| Card | `.card` + `.card-head` / `-body` / `-foot` | a candidate card, a client, an assignment |
| Card grid | `.card-grid` | adapts on its own, do not declare the columns |
| Footer | `.page-footer` | data source, date, note |

A `.card` can be **clickable as a whole**: use `<a class="card" href="...">`.

### Brand header — the logo the "install logo" row above means

`.page-header` is documented as "install logo + date", but a header only carries
one if you put it there — the base fallback template starts from
`shared/core/templates/minisite/base.html`, and every page copied from the five
layouts needs the same header filled. `brand.py` (next to `share.py` in this
skill's folder) resolves which logo/colour this install (or this one brain, if
it overrides) is supposed to show, and fills it into the header in place:

```
python3 brand.py resolve            # what this brain resolves to — check before writing
python3 brand.py fill public/<slug>/index.html   # injects BRAND_* placeholders in place
```

Resolution order: `artifact.brand` in this brain's own `boot/local.yaml` (an
explicit per-brain override) first, then the install's default — derived from
`public.base_url` in the same file, loaded from
`shared/core/templates/minisite/brand/<install>/brand.json`. An install with no
brand configured resolves to nothing, and the header renders as it always did:
text only, no crash, no placeholder logo pretending to be real.

**Only `base.html` carries the placeholders `brand.py fill` understands**
(`{{BRAND_LOGO_INLINE}}`, `{{BRAND_LOGO_ARIA_HIDDEN}}`, `{{BRAND_PRIMARY}}`). The
five ready layouts (`faq.html`, `gallery.html`, …) predate this and still ship a
text-only `.page-header`: when you copy one of them and the install has a brand
configured, add the same three placeholders to its header by hand before running
`fill` — or start from `base.html`'s header markup and paste it in.

The logo is inlined (`<svg>` or a `data:` `<img>`), never linked by URL: it
travels with the page regardless of how — or whether — this install serves
static assets out of the shared folder, and a page someone copies elsewhere
still shows it.

**Give the reader something to navigate by past three sections.** An artifact that
grows past three or four `<h2>`s and offers no way to jump around is a page people
scroll blind. Two patterns cover it, and the template has both ready, commented out:

- `.nav-bar` across the top — internal anchors, or the other pages of a multi-page
  artifact. Cheap, and it doubles as an at-a-glance table of contents.
- `.with-sidebar` + `.sidebar .toc` — a running index down the side, for anything
  long enough that a top bar would need to scroll itself.

Neither is mandatory for a short page. The point is to default to one once the
artifact has grown, not to bolt it on after someone complains they got lost.

Two details you don't see until they break something:

- A wide table must be wrapped in `<div class="scroll-x">`, otherwise it makes
  **the whole page** scroll horizontally on a phone.
- The platform's share bar sits fixed at the bottom: the stylesheet already leaves
  room for it, don't remove that.

### When the stylesheet changes

Editing it is NOT enough: Cloudflare sits in front. After touching
`artifact-1.css` the cache for that single URL must be purged, otherwise pages keep
seeing the old version for hours. This is not an operational detail: without the
purge, "updatable later" is false.

## How much an artifact can "do"

An artifact is a **page**, not an application. It lives in the browser of whoever
opens it and has nowhere to write: there is no database behind it, no address to
send data to.

**Possible** — everything that happens in the page and stays there: filtering,
sorting, searching, opening and closing sections, switching views, computing a
total, copying to the clipboard, printing. Also state put in the address
(`?view=list`), which survives because it is in the link.

**Not possible** — everything that has to *persist* or *leave*: a form that
submits, a button that saves, preferences that are still there on the next visit, a
file upload, a comment, a signature, a login, a notification. It is not that they
work badly: **there is nobody on the other side**.

### How to say it to whoever asks

When somebody asks for something in the second group, **do not try it anyway** and
do not leave a form that looks functional and silently loses what they type. And do
not explain the architecture: say the thing and offer the alternative.

> That would need a form, but a heads-up: forms don't work on the documents I
> prepare for you — it's a technical limit, the page has no way to save what you
> type into it. I can either send the data to the right person myself, or prepare
> the page for you to print and fill in by hand. Which do you prefer?

The rules: **warn first**, not after building. **The limit belongs to the medium,
not to you.** Always offer at least one route that actually works. And no
insider vocabulary — *backend*, *server*, *static*, *API* mean nothing to somebody
asking you for a document.

The most frequent case is **collecting answers** (a client who has to fill
something in, a candidate who has to confirm). There the good route is almost
always: the page shows, and the collection happens by email or on a tool made for
it — not inside the artifact.

## Output

After creating or updating, report the address and what it means:

```
Internal: <url from share.py link>   [visible to whoever is logged in, no expiry]
Template: {template_name}
Files: index.html [+ assets]
```

And only if the user asked for it to be published:

```
Published: <url from the driver>   [HTTP 200 verified]
Expires: 06/08/2026
```

Full links, always with `https://` — a bare domain isn't clickable in a terminal.
