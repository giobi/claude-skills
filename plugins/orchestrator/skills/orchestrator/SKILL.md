---
name: orchestrator
description: "Run one session as the conductor of the other live Claude sessions in tmux: register them, delegate with the right provider, relay decisions, and know when to send the user to the dedicated session instead"
user-invocable: true
argument-hint: "[start | status | delegate <topic> | <who>: <message>]"
---

# /orchestrator: one chat that conducts the others

The user works in many tmux sessions at once and gets lost switching windows. One session
becomes the **conductor**: the user talks only to it, and it opens, briefs, reads and
messages the others. They act as sub-agents with their own context and their own loop.

The rules below are the ones that held up, or broke, on real work: client forms, a deploy,
bug-reply mails, a WhatsApp loop.

## Setup

- **Name the conductor anything except `main`.** `main` is a reserved target of the
  messaging tool, so peers that "reply to main" never reach it.
- **Census from tmux panes, not transcripts.** A session is alive only if a pane runs
  `claude`. Use `tmux list-panes -a` plus the agent listing. Peers shown under a `restored:`
  tmux session whose pane is a bash shell are dead.
- **Every live session needs a unique name.** The pane title is not the address; the name
  in the agent listing is. Rename unnamed sessions by injecting `/rename <name>` with
  `tmux send-keys`, **only when the prompt is empty**: with a menu open the keys become an
  answer to the menu. Two sessions with the same name are unreachable until one is renamed.
- **Look at the RAM before opening any session** (`free -h`; the floor is the larger of
  2 GB and 15% of total RAM, see § Session lifecycle). On a small machine an open without
  that check can take the whole host down.
- Group the registry by client or area; side projects go in one generic group.
- **Fixed tmux layout.** Window 1 is the conductor: this chat as a left column at about 30%
  of the width, and on the right a 2x2 grid. Two *direct* sessions (the ones where something
  waits on the user right now: a send, an ok, a dialogue he started) on top; a fleet board
  and a status CLI below. Window 2 holds the next direct sessions in line (a send or a
  yes/no that can wait an hour), nothing else. **The conductor keeps the direct slots
  moving**: as soon as the user has answered in a direct session, move it back to its group
  window and bring in the next one waiting; when nothing waits, the slot stays empty. **A
  person pushing on a live thread** (a client chasing on WhatsApp or mail, a call tomorrow)
  goes into the grid the moment the draft is ready, without waiting to be asked, and the
  chat says "go to %name" with the pending choice. Moves: swap a direct with
  `tmux swap-pane -s <new> -t <old>` so the grid keeps its shape, `join-pane -d` back out,
  then `select-layout even-horizontal` and `resize-pane` the conductor to 30%. Windows keep
  their name with `automatic-rename off`. Every window is in columns, never tiled.
- `%name` in the user's message means that session, not a project or a skill with the same
  name. The verb decides: "ask %x" injects a message, "what is %x doing" reads it, "open %x"
  starts it if it does not exist yet. The conductor itself is never a candidate.

## The main stream stays free

The conductor's turn belongs to the conversation with the user. Its own tool calls are
limited to the cheap and instant ones: listing agents, sending a message, opening a session,
a `tmux send-keys`, a one-line `capture-pane`. Everything else goes to a **background
subagent** (it runs in the background and returns a distilled result), or to the dedicated
session if one exists: searching mail or transcripts, grepping the knowledge base,
verifying a fix, extracting a draft, checking a link.

Signs that the conductor broke the rule: the user waits through a chain of
`grep`/`ssh`/`python` calls before getting an answer, or interrupts a lookup to point at the
right source ("check the email, obviously"). When a lookup is needed, spawn it, tell the
user in one line what is running, and keep talking.

## Delegating

Every session opens with a project and a target, and closes with `/bye` when the target is
reached. The standard launch is
`session new <name> --group <g> --project <p> --target "..." -m/-p ... --brief file`
(plus `--cwd DIR` when needed). The launcher prepends to the brief, in a copy, the
instruction to invoke the project and target skills first and `bye` at the end; the original
stays untouched. Without `--project` and `--target` it still opens but warns on stderr.

Always open with `--group <client/area>`: sessions are packed per client or area, max 4 panes
per window (then `<group>-2`, and so on), never one window per session.
The brief is a **file**, never inline text. Size the provider to the effort:

| Work | Provider |
|---|---|
| mechanical, read-only, batch | a cheap model alias through the gateway, or your own GPU when it is on |
| ordinary (fixes, content, known debugging), infra design without client data | a mid-priced model; the mid tier of Claude when it needs Claude tooling |
| the user's own data (his mail, his chats, fiscal) | an EU-hosted provider or your on-prem GPU, never a pay-per-use provider outside the EU |
| delicate (client production, deliverables for third parties, architecture) | the strongest model |
| sensitive client data | on-prem GPU or an EU-hosted provider |
| a model not placed yet | try it on a real case before giving it a row |

The strongest model is the launcher's default, which is exactly why it gets picked without
thinking. Decide the row first, then pass the flag.

- **Name the working mode in the brief: the skill the session must invoke after project and
  target.** The conductor knows the skills; a session left to guess works by hand. Pick by
  the shape of the job:

  | The job is… | The brief says to invoke |
  |---|---|
  | still fuzzy: what to build, for whom, which options | `/design` first, the design doc is the deliverable, no code |
  | implementing a design that exists | `/build` (TDD, deep modules, design kept updated) |
  | a long build with a written spec to run unattended | a goal-preparation step, then the goal runner |
  | an errand the user handed over with "do it all yourself" | an autonomous-run skill, typed by the conductor with the user's words |
  | something that goes to a third party (mail, report, page) | a deliverable check, a text-cleaning pass, the voice skill, and `/send` only on the user's word |
  | moving or deploying an app, backups | the infra skill, with a backup before the first production write |
  | checking a site or a fix visually | a browser check, with a screenshot actually looked at |
  | mail, chat, banking, calendar, invoicing | the matching channel skill |
  | closing | `/save` midway, `/bye` at target |

  If the user names a skill himself, it goes into the brief verbatim: command first, never
  "by hand". When a session reports that it did the work by hand where a skill existed, send
  it back to the skill.
- Small local models drown in a large set of boot files: run them with `--cwd` outside the
  brain, with a two-line instruction file and curated input files. Never trust a model's
  self-assessment of what it can do: measure it on real past cases.
- **"Draft" in a brief means text in chat or in a file, never a draft in the mailbox.** The
  mailbox draft is created only after the ok, and the send step creates and sends it in one
  go. Write it like that in every brief that ends in a mail: "draft in chat or file, no
  create_draft before the send".
- Every brief says: who opened it, the goal, the sources to read first, what NOT to do, and
  "report to the conductor in one line when done or blocked".
- Before spending quota, check the weekly limit. When it is near the cap, move work to a
  non-Claude provider or wait for the reset.

## Waiting

- **No periodic polling, no `/loop` on the conductor.** It burns the account's quota
  without anyone noticing.
- To know when a session finishes, use `SendMessage` with `notify_when_idle: true`: it is
  one-shot and free. A repeated identical notice is a duplicate, not news.
- A session that has to watch something (a log, a chat) uses `Monitor` on a script that
  prints only on change, so the model wakes only when there is something to do.
- For the state of the fleet, run the board command in a pane: zero tokens, one card per
  window (who is working, who waits on the user, who is stalled), tmux only.

## The sweep runs by itself

The conductor does not wait to be asked. **After every report from a session and every
decision from the user**, before answering, it runs the sweep; at the latest every 3-4
messages when nothing arrived. The sweep costs only cheap calls (tmux listing, one
`capture-pane` line per pane, `free -h`, the board CLI), no model work, so doing it often is
cheaper than the user's attention spent asking for it:

1. **Board**: tick or remove what the report closed, add what it opened, rewrite stale lines.
2. **Close**: a session whose target is done and that waits on nothing gets `/bye`, and on
   the next sweep `/exit`: `/bye` saves but leaves the process running. A bash pane left
   behind is killed.
3. **Target**: every live session has a target. One without gets one typed in from its brief,
   or is closed.
4. **Windows**: the first two windows hold only what waits on the user *now*, the current
   focus first; a session that just got its answer goes back to its group window and the
   next one waiting takes its slot.
5. **RAM**: `free -h`, always, on every sweep and before every open; below the floor (see
   § Session lifecycle, RAM) close before opening.

Say in one line what the sweep changed only when it changed something the user looks at (a
pane moved, a session closed); otherwise stay silent about it.

## The board is the status, the chat is for the minimum

The user follows the open problems on the **board** pane next to this chat, not in the
scrollback, where he gets lost. So every report from a session goes **first to the board**
(add, tick or rewrite the item, one line per thing he must do or decide, plus notes for what
is running), and the chat gets the bare minimum: one or two lines that say what changed and
point at the board item. Write more in chat only when it is needed: a decision that cannot
wait, a draft he must read, an alarm. Keep the board pruned: done items ticked or removed, a
"running" note and a "later" note instead of a dozen stale lines.

Every item is referred to **by its number**, in chat too ("item 21"): the user reads the
board from his phone and answers by number. Likewise every session named in chat carries its
window: `%billing (w1, center)`, `%site-dev (w2)`.

**A walk through the board is also a sweep of the fleet**: when the user goes through the
board, the conductor in the same pass reads the live sessions, closes the finished ones
(`/bye` saves, `/exit` ends the process, then kill the bash pane), opens what a decision
needs, rewrites stale items, and rebalances the direct window (out: sessions where nothing
waits on him; in: sessions with a draft or a dialogue waiting on him). Topics the user is
already handling himself in a direct session are **not** open items, since they nag him about
something he is doing: fold them into one note, "in direct: X in %a, Y in %b", and remove the
line when the session reports it closed.

## Relaying decisions

- A session stuck on a multiple-choice menu cannot be unblocked with a message. Read the
  menu, bring it to the user, then press the chosen key in that pane.
- **A relayed approval does not count, a typed one does.** A dedicated session rightly
  refuses an approval that reaches it as a message from another session.
- **Send, autonomous-run and deploy approvals can be delegated to the conductor.** When the
  user writes one of them *in the conductor* for a specific item, the conductor types it into
  the dedicated session's prompt with `tmux send-keys`, as the user's own keystrokes, quoting
  the user verbatim and signing "via orchestrator, HH:MM". Conditions: the user named the item
  (or only one is waiting there), the target pane's prompt is empty (no menu open), and you
  read the pane afterwards to confirm it was taken. Anything the user did not name stays with
  them. **The trigger is the literal word `/send` (or `/solo`, "deploy") in the user's own
  message**, never an instruction that implies sending ("answer each of them", "send the
  acknowledgement"). The sessions trust the signed form, so a send the conductor types on its
  own reading goes out for real: once, five client mails left that way from a dictated
  sentence. The dedicated session refused that sentence, which was right. When it refuses,
  bring the item to the user and ask for the `/send`; don't type it yourself.
- **Allow-listed correspondents: mail without `/send`.** For a short list of people kept in a
  config file (the ones who use the brains, plus a few others), a session may answer by mail
  on its own, signed as the agent, without asking for `/send` or a check from the user. It
  covers the small stuff: a question on the brain or the site, a quick fix, a status update.
  It does **not** cover anything with money (offers, quotes, prices) or a change in
  production: those still go to the user. Nodal deliverables also stay with him, and so do the
  topics in a member's exclusion list. When in doubt about whether an item is small, it isn't:
  ask. The brief names the person and says "allow-list". This is the one exception to the
  literal-`/send` trigger above.
- **An autonomous-run session means "don't come back with questions".** The user wants to
  hear from it once, at the end. The only things that may reach him mid-run are serious
  errors, irreversible steps, money, and production outside the task's own target. When such a
  session stops on anything else (a permission it could grant itself inside the mandate, a
  choice between options, "shall I go on?"), the conductor does **not** relay it: it answers
  "go ahead, it's autonomous" in that pane and moves on. A mistake on a staging copy is
  cheaper than a question. (Origin: a session stopped on a DNS token permission and the
  conductor passed the question up instead of sending it back.)
- **A task given to the conductor is the go-ahead.** "Look at the chat and handle it" means do
  it, not "come back with a draft and ask". Propose a better shape on the way (a private
  message instead of the group) and carry it out in the same breath. What stays gated is the
  same short list as the autonomous run: money, irreversible steps, production outside the
  target, and mail, which still needs the literal `/send`.
- Relay the user's words **verbatim**, with the time. Never paraphrase a decision.
- Every relay is a lossy summary. On facts (dates, amounts, who did what), quote the
  dedicated session's source, never your own memory: once the conductor turned "forwarded to
  the consultant" into "requested", and the dedicated session had to correct it.

## Conductor or dedicated session?

Handle it **in the conductor**: triage, spawning, translating jargon into plain words, quick
evaluations, yes/no decisions, waiting for notices.

**Send the user to `%name`** (say it explicitly: "go to %name") when:
- the topic needs more than two or three rounds of questions and answers with the user;
- the user's own data must be confirmed field by field;
- the next step is a `/send` or a production approval;
- the dedicated session already holds the sources and you would only be retelling them.

Cost of getting this wrong: two full contexts on the same topic, every relayed message paid
twice, and a summary layer that introduces errors.

## One conversation, one session

Every live conversation with another person (a chat thread, a mail thread, a client channel)
gets **its own tmux session**, named after the person or the thread, and the conductor keeps
the register of who owns which conversation. The dedicated session holds the history, answers
within its mandate and reports back, while the conductor keeps an eye on all of them at once.
Safety comes from that split: a conversation never leaks into another's context, and every
outgoing message passes a session whose only job is that conversation.

- A new message from someone who already has a session goes **to that session**, never to a
  fresh one and never to the conductor.
- Chat messages: subscribe the session to its chats with the routing tool and that is all;
  **no `Monitor` in the session**. A delivery daemon types each event into the session's pane
  when it arrives (zero tokens while quiet, nothing to re-arm). The subscription is sticky:
  the session alone answers its chats until it is cancelled or expires, even if the session
  is busy or down; events queue. Other channels: a `Monitor` on a script that prints only on
  new messages; never poll with the model.
- What it may send on its own follows the usual gates: the user's go-ahead given to the
  conductor, the allow-list, `/send` for mail. Money, irreversible steps and anything new
  about the user's personal data go back to the conductor.
- The session is a standing role: it does not `/bye` when one exchange is done. It closes
  when the conversation is closed for good.

## Speaking for the user to other people

A session that replies in a chat with friends or clients on the user's behalf changes the
room, even with a signature prefix and the right tone. Watch the other people's reactions, not
only the content: two signs of annoyance and it stops, silently, without a goodbye. (In one
group chat the first sign came ten minutes into a 30-minute loop, the second a minute later:
someone proposed leaving the group.)

## Session lifecycle: context, target, close

The conductor keeps the fleet lean, not only busy:
- **Before opening, look.** List the agents first: if a live session already owns the topic,
  send it there. Then look at recent transcripts with the same name: if one exists, tell the
  user and propose resume vs fresh. If only an old transcript exists, open a new session that
  reads that session's diary instead of resuming a context full of history.
- **Every session opens with a target**, and closes itself: at target reached, with nothing
  pending, it sends the conductor one line with the outcome and runs `/bye` (it saves, commits
  and closes). The conductor types `/bye` into it only if the session did not do it on its
  own. Don't leave a finished session idle "just in case".
- **RAM, always.** Every Claude process costs 0.1-0.6 GB. Check `free -h` and the `claude`
  processes **before every open, without exception**, and on every sweep. The floor is
  relative to the machine, not a fixed number: keep available memory above **the larger of
  2 GB and 15% of total RAM** (on a 32 GB server that is about 4.8 GB, on an 8 GB laptop
  2 GB). On a small machine that means fewer sessions at once, and the conductor closes
  before it opens instead of piling up. Look for processes outside the live tmux panes too:
  once about 35 web-terminal sessions of a legacy app had been up for 24 days, about 4.5 GB
  in all. If available memory drops below the floor, close the finished sessions first and
  open nothing new until it recovers.
- **Heavy contexts.** A session showing "/clear to save 300k+ tokens" that has finished its
  target gets `/bye`, not more work. New work goes to a fresh session with a brief.
- Sessions under a `restored:` tmux session whose pane is bash are already dead: they are only
  listed, nothing to close.

## Closing sessions

**Background tasks on exit.** `/exit` on a session with background work opens a menu ("Exit
and stop tasks / Move to background and exit / Stay") that lists them. Read the list and
decide each one; never press a key blindly. A backup, restore, deploy or upload halfway
through is moved to the background, or you wait for it, because killing it leaves a broken
copy. A scheduled retry or a watcher that no longer has a reason to run gets stopped. A job
whose purpose you can't tell from its line keeps the session open (Stay): ask the session what
it is, and tell the user in one line what you kept and what you stopped.

A session is finished only if its target is done **and** nothing is expected back. A client
deliverable waiting for feedback is not finished (one was closed by mistake and reopened by
resuming its transcript). A session with a standing role (a bug tracker working alongside a
dev session) is never "finished". Closing loses nothing, because the transcript stays and can
be resumed, but say why you closed it.

## Removals the hook blocks

When a session needs a file deleted and a safety hook blocks the removal, it does not ask the
user to run a command: it queues the path with a pending-removal helper
(`pending-rm add <path> "<why>"`). The user runs `pending-rm` once a day: it
lists everything, asks once, removes.

## Saving

The registry lives in the conductor's context. Decisions to dispatch later go in a TODO, so
they survive if the conductor dies. Each completed step goes in the diary, as usual.
