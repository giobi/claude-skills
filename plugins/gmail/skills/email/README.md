# Email adapter — drivers

`EmailAdapter` exposes one interface (`search`, `get_message`, `get_thread`, `draft`,
`send`, `send_draft`, `reply`) over three backends. The driver is picked from the
workspace `.env`; pass `driver=` to override it.

| Driver | Picked when `.env` has | Transport |
|---|---|---|
| `o365` | `O365_CLIENT_ID` or `O365_REFRESH_TOKEN` | Microsoft Graph |
| `gmail` | `GMAIL_CLIENT_ID` or `GMAIL_REFRESH_TOKEN` | Gmail API |
| `imap` | `IMAP_HOST` or `EMAIL_IMAP_HOST` | IMAP + SMTP |

Detection order is o365 → gmail → imap. IMAP comes last on purpose: it is the fallback
for mailboxes with no OAuth broker and must never win over a mailbox that has real
tokens. A brain whose `.env` carries both keeps using the API driver.

The send gate (`confirm="SEND"` plus a fresh `/send` token plus no workspace lock)
lives in the adapter, so it applies to every driver equally.

## IMAP driver

For mailboxes that no OAuth broker covers: Register.it, Aruba, Purelymail, cPanel
hosts, self-run servers. Reading over IMAP, sending over SMTP, drafts APPENDed to the
server's Drafts folder so they appear in the user's own mail client, and sent messages
copied to Sent for the same reason.

### Configuration

```
IMAP_HOST=mail.example.com
IMAP_PORT=993            # default 993
IMAP_USER=user@example.com
IMAP_PASSWORD=...
IMAP_SSL=true            # false uses STARTTLS on the given port
SMTP_HOST=...            # defaults to IMAP_HOST
SMTP_PORT=587            # 465 switches to implicit TLS
SMTP_USER=...            # defaults to IMAP_USER
SMTP_PASSWORD=...        # defaults to IMAP_PASSWORD
SMTP_STARTTLS=true
IMAP_FROM=...            # defaults to IMAP_USER
```

The older `EMAIL_ADDRESS` / `EMAIL_PASSWORD` / `EMAIL_IMAP_HOST` / `EMAIL_SMTP_HOST`
names are accepted as fallbacks, so a mailbox already configured that way works
unchanged.

### Behaviour worth knowing

**Message ids are `<mailbox>:<uid>`.** Stable while the mailbox keeps its UIDVALIDITY —
enough to fetch a message that was just listed, not a permanent handle to store.

**Folders are resolved by SPECIAL-USE, not by name.** The server is asked which folder
carries `\Sent` / `\Drafts` / `\Trash` before falling back to a list of common names,
because naming varies wildly (`Sent`, `Sent Items`, `INBOX.Sent`, `Posta inviata`).

**Queries are Gmail-flavoured and translated.** `from:` `to:` `cc:` `subject:` `body:`
`in:` `is:unread` `is:read` `is:starred` `after:` `before:` `newer_than:Nd`
`older_than:Nd`; anything left over becomes a `TEXT` search. Gmail-only operators
(`has:attachment`, `label:`, `category:`) are **dropped rather than mistranslated** —
they would otherwise silently change what matches.

**Search values are quoted, and UTF-8 is declared when needed.** An unquoted argument
containing a space makes the server answer `BAD ... Illegal arguments`, and a subject
with accents or an em dash is MIME-encoded on the server, so a plain search never
matches it. Both are handled; servers that reject the charset option fall back to the
plain form instead of returning nothing.

**Threads are rebuilt from `References` / `In-Reply-To`.** IMAP has no thread id, so
`get_thread` takes the root `Message-ID` and gathers what references it across inbox
and sent, ordered by date.

**A missing Sent copy is not a send failure.** If the APPEND to Sent fails after SMTP
accepted the message, the send still reports success — the mail is already gone, and
reporting failure would invite a duplicate.

### Diagnostics

```bash
python3 drivers/imap/imap_driver.py
```

Prints host, resolved folders and inbox count, which is the fastest way to tell a bad
password from a bad folder name.

### Verified

Collaudato end-to-end su Purelymail (2026-08-21): login, ricerca, fetch, parsing di
header e body, bozza APPENDed e ritrovata, invio SMTP con consegna reale e copia in
Sent, risposta in-thread, e il send gate che blocca l'invio senza `confirm="SEND"`.

Not exercised: OAuth-authenticated IMAP (XOAUTH2), attachments, and servers that only
speak plain IMAP4 without TLS.
