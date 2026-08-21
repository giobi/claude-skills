#!/usr/bin/env python3
"""
IMAP/SMTP driver for the email skill.

Covers mailboxes that have no OAuth broker: Register.it, Aruba, Purelymail,
cPanel hosts, self-run mail servers. Reading goes over IMAP, sending over SMTP,
drafts are APPENDed to the server's Drafts folder so they show up in the user's
own mail client.

Configuration is read from the workspace .env. Primary names are IMAP_* / SMTP_*;
the older EMAIL_* names used by the root brain are accepted as a fallback so an
existing mailbox keeps working without editing its .env.

    IMAP_HOST, IMAP_PORT (993), IMAP_USER, IMAP_PASSWORD, IMAP_SSL (true)
    SMTP_HOST, SMTP_PORT (587), SMTP_USER (=IMAP_USER), SMTP_PASSWORD (=IMAP_PASSWORD)
    SMTP_STARTTLS (true), IMAP_FROM (=IMAP_USER)

Message ids are "<mailbox>:<uid>" — stable for as long as the mailbox keeps its
UIDVALIDITY, which is what the adapter needs to fetch a message it just listed.
"""

import email
import email.utils
import imaplib
import os
import re
import smtplib
import ssl
from datetime import datetime
from email.header import decode_header, make_header
from email.message import EmailMessage
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Folders we look for by SPECIAL-USE flag, with fallback names per role.
# Server naming is a mess (Sent / Sent Items / INBOX.Sent / Posta inviata),
# so we ask the server first and only guess if it stays silent.
SPECIAL_USE = {
    'sent': (r'\Sent', ['Sent', 'Sent Items', 'Sent Messages', 'INBOX.Sent', 'Posta inviata']),
    'drafts': (r'\Drafts', ['Drafts', 'INBOX.Drafts', 'Bozze']),
    'trash': (r'\Trash', ['Trash', 'Deleted Items', 'INBOX.Trash', 'Cestino']),
}

MAX_FETCH = 200


# ── configuration ─────────────────────────────────────────


def _workspace_root() -> Path:
    """
    Workspace root, preferring the one the adapter already resolved.

    The adapter exports EMAIL_WORKSPACE_ROOT before loading a driver, so both
    read the same .env even when the skill lives outside the brain it serves.
    Falling back to our own walk keeps the driver usable on its own.
    """
    declared = os.environ.get('EMAIL_WORKSPACE_ROOT')
    if declared and (Path(declared) / '.env').exists():
        return Path(declared)

    current = Path(__file__).resolve().parent
    for _ in range(10):
        if (current / 'boot').is_dir() and (current / '.env').exists():
            return current
        if current.parent == current:
            break
        current = current.parent
    current = Path(__file__).resolve().parent
    for _ in range(10):
        if (current / '.env').exists() and not (current / '.claude').is_dir():
            return current
        if current.parent == current:
            break
        current = current.parent
    return Path.cwd()


def _load_env() -> Dict[str, str]:
    """Read the workspace .env into a dict. Process env wins over the file."""
    env_file = _workspace_root() / '.env'
    values: Dict[str, str] = {}
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, _, value = line.partition('=')
            value = value.strip().strip('"').strip("'")
            values[key.strip()] = value
    values.update({k: v for k, v in os.environ.items() if k in values or k.startswith(('IMAP_', 'SMTP_', 'EMAIL_'))})
    return values


def _setting(env: Dict[str, str], *names: str, default: Optional[str] = None) -> Optional[str]:
    for name in names:
        value = env.get(name)
        if value:
            return value
    return default


def _config() -> Dict[str, object]:
    env = _load_env()

    user = _setting(env, 'IMAP_USER', 'EMAIL_ADDRESS')
    password = _setting(env, 'IMAP_PASSWORD', 'EMAIL_PASSWORD')
    host = _setting(env, 'IMAP_HOST', 'EMAIL_IMAP_HOST')

    if not (host and user and password):
        raise RuntimeError(
            "IMAP driver needs IMAP_HOST, IMAP_USER and IMAP_PASSWORD "
            "(or the EMAIL_IMAP_HOST / EMAIL_ADDRESS / EMAIL_PASSWORD equivalents) in .env"
        )

    def flag(*names: str, default: bool = True) -> bool:
        raw = _setting(env, *names)
        if raw is None:
            return default
        return raw.strip().lower() not in ('0', 'false', 'no', 'off')

    return {
        'imap_host': host,
        'imap_port': int(_setting(env, 'IMAP_PORT', 'EMAIL_IMAP_PORT', default='993')),
        'imap_ssl': flag('IMAP_SSL'),
        'user': user,
        'password': password,
        'smtp_host': _setting(env, 'SMTP_HOST', 'EMAIL_SMTP_HOST', default=host),
        'smtp_port': int(_setting(env, 'SMTP_PORT', 'EMAIL_SMTP_PORT', default='587')),
        'smtp_user': _setting(env, 'SMTP_USER', default=user),
        'smtp_password': _setting(env, 'SMTP_PASSWORD', default=password),
        'smtp_starttls': flag('SMTP_STARTTLS'),
        'from_address': _setting(env, 'IMAP_FROM', 'EMAIL_ADDRESS', default=user),
    }


# ── connection ────────────────────────────────────────────


class _Connection:
    """IMAP connection as a context manager. Always logs out, even on error."""

    def __init__(self):
        self.config = _config()
        self.imap: Optional[imaplib.IMAP4] = None

    def __enter__(self) -> imaplib.IMAP4:
        host, port = self.config['imap_host'], self.config['imap_port']
        if self.config['imap_ssl']:
            self.imap = imaplib.IMAP4_SSL(host, port, ssl_context=ssl.create_default_context())
        else:
            self.imap = imaplib.IMAP4(host, port)
            self.imap.starttls(ssl.create_default_context())
        self.imap.login(self.config['user'], self.config['password'])
        return self.imap

    def __exit__(self, *exc_info):
        if self.imap is not None:
            try:
                self.imap.close()
            except Exception:
                pass
            try:
                self.imap.logout()
            except Exception:
                pass
        return False


def _decode_mailbox_name(raw: bytes) -> str:
    """Pull the mailbox name out of a LIST response line."""
    text = raw.decode('utf-8', errors='ignore')
    match = re.search(r'"([^"]*)"\s*$', text)
    if match:
        return match.group(1)
    return text.rsplit(' ', 1)[-1].strip('"')


def _resolve_folder(imap: imaplib.IMAP4, role: str) -> str:
    """Find the folder for a role, asking the server before guessing."""
    if role == 'inbox':
        return 'INBOX'

    flag, fallbacks = SPECIAL_USE[role]
    status, lines = imap.list()
    names = []
    if status == 'OK':
        for line in lines or []:
            text = line.decode('utf-8', errors='ignore') if isinstance(line, bytes) else str(line)
            name = _decode_mailbox_name(line if isinstance(line, bytes) else line.encode())
            names.append(name)
            if flag.lower() in text.lower():
                return name

    lowered = {n.lower(): n for n in names}
    for candidate in fallbacks:
        if candidate.lower() in lowered:
            return lowered[candidate.lower()]
    return fallbacks[0]


# ── query translation ─────────────────────────────────────


def _format_imap_date(value: str) -> Optional[str]:
    """YYYY-MM-DD or YYYY/MM/DD to the DD-Mon-YYYY that IMAP SEARCH wants."""
    for fmt in ('%Y-%m-%d', '%Y/%m/%d', '%d-%m-%Y'):
        try:
            return datetime.strptime(value, fmt).strftime('%d-%b-%Y')
        except ValueError:
            continue
    return None


def translate_query(query: str) -> Tuple[str, List[str]]:
    """
    Translate a Gmail-style query into (folder role, IMAP SEARCH criteria).

    Understood: from: to: cc: subject: in: is:unread is:read after: before:
    newer_than:Nd older_than:Nd. Anything left over becomes a TEXT search.
    Unsupported Gmail operators (has:attachment, label:, category:) are dropped
    rather than silently changing what gets matched.
    """
    folder = 'inbox'
    criteria: List[str] = []
    leftovers: List[str] = []

    tokens = re.findall(r'(?:[a-z_]+:)?(?:"[^"]*"|\S+)', query or '', flags=re.IGNORECASE)

    for token in tokens:
        key, _, value = token.partition(':')
        key = key.lower()
        value = value.strip('"')

        if not value:
            leftovers.append(token.strip('"'))
            continue

        if key == 'from':
            criteria += ['FROM', value]
        elif key == 'to':
            criteria += ['TO', value]
        elif key == 'cc':
            criteria += ['CC', value]
        elif key == 'subject':
            criteria += ['SUBJECT', value]
        elif key == 'body':
            criteria += ['BODY', value]
        elif key == 'in':
            folder = {'inbox': 'inbox', 'sent': 'sent', 'drafts': 'drafts',
                      'draft': 'drafts', 'trash': 'trash'}.get(value.lower(), 'inbox')
        elif key == 'is':
            if value.lower() in ('unread', 'unseen'):
                criteria.append('UNSEEN')
            elif value.lower() in ('read', 'seen'):
                criteria.append('SEEN')
            elif value.lower() == 'starred':
                criteria.append('FLAGGED')
        elif key in ('after', 'since'):
            formatted = _format_imap_date(value)
            if formatted:
                criteria += ['SINCE', formatted]
        elif key == 'before':
            formatted = _format_imap_date(value)
            if formatted:
                criteria += ['BEFORE', formatted]
        elif key in ('newer_than', 'older_than'):
            match = re.match(r'(\d+)d', value)
            if match:
                from datetime import timedelta
                cutoff = datetime.now() - timedelta(days=int(match.group(1)))
                criteria += ['SINCE' if key == 'newer_than' else 'BEFORE',
                             cutoff.strftime('%d-%b-%Y')]
        elif key in ('has', 'label', 'category', 'filename'):
            continue  # Gmail-only; dropping beats mistranslating
        else:
            leftovers.append(token.strip('"'))

    if leftovers:
        criteria += ['TEXT', ' '.join(leftovers)]
    if not criteria:
        criteria = ['ALL']

    return folder, criteria


# ── parsing ───────────────────────────────────────────────


def _decode(value: Optional[str]) -> str:
    if not value:
        return ''
    try:
        return str(make_header(decode_header(value)))
    except Exception:
        return value


def _extract_body(message: email.message.Message) -> str:
    """Plain text if the message has any, otherwise HTML stripped of its tags."""
    plain, html = None, None

    if message.is_multipart():
        for part in message.walk():
            if part.get_content_maintype() == 'multipart':
                continue
            if 'attachment' in (part.get('Content-Disposition') or ''):
                continue
            content_type = part.get_content_type()
            if content_type == 'text/plain' and plain is None:
                plain = part
            elif content_type == 'text/html' and html is None:
                html = part
    else:
        if message.get_content_type() == 'text/plain':
            plain = message
        else:
            html = message

    chosen = plain or html
    if chosen is None:
        return ''

    payload = chosen.get_payload(decode=True)
    if payload is None:
        return ''
    text = payload.decode(chosen.get_content_charset() or 'utf-8', errors='ignore')

    if chosen is html:
        text = re.sub(r'<(script|style)[^>]*>.*?</\1>', ' ', text, flags=re.S | re.I)
        text = re.sub(r'<br\s*/?>|</p>', '\n', text, flags=re.I)
        text = re.sub(r'<[^>]+>', '', text)
        text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def _parse(raw: bytes, mailbox: str, uid: str) -> Dict:
    """Build the dict shape the adapter shares with the gmail driver."""
    message = email.message_from_bytes(raw)
    references = (message.get('References') or '').split()
    in_reply_to = (message.get('In-Reply-To') or '').strip()
    root = references[0] if references else (in_reply_to or message.get('Message-ID', ''))

    return {
        'id': f'{mailbox}:{uid}',
        'threadId': root.strip('<>') if root else f'{mailbox}:{uid}',
        'from': _decode(message.get('From')),
        'to': _decode(message.get('To')),
        'cc': _decode(message.get('Cc')),
        'subject': _decode(message.get('Subject')),
        'date': message.get('Date', ''),
        'body': _extract_body(message),
        'labelIds': [mailbox],
        'messageId': (message.get('Message-ID') or '').strip('<>'),
        'references': [r.strip('<>') for r in references],
        'list_unsubscribe': message.get('List-Unsubscribe', ''),
    }


IMAP_KEYWORDS = {
    'ALL', 'ANSWERED', 'BCC', 'BEFORE', 'BODY', 'CC', 'DELETED', 'DRAFT', 'FLAGGED',
    'FROM', 'HEADER', 'KEYWORD', 'LARGER', 'NEW', 'NOT', 'OLD', 'ON', 'OR', 'RECENT',
    'SEEN', 'SENTBEFORE', 'SENTON', 'SENTSINCE', 'SINCE', 'SMALLER', 'SUBJECT', 'TEXT',
    'TO', 'UID', 'UNANSWERED', 'UNDELETED', 'UNDRAFT', 'UNFLAGGED', 'UNKEYWORD', 'UNSEEN',
    'MESSAGE-ID', 'REFERENCES',
}


def _quote_criteria(criteria: List[str]) -> List[str]:
    """
    Quote search values so imaplib accepts them.

    A bare argument containing a space makes the server answer
    'BAD UID failed. Illegal arguments.', so anything that is not an IMAP
    keyword gets wrapped in quotes with its own quotes escaped.
    """
    quoted = []
    for item in criteria:
        if item.upper() in IMAP_KEYWORDS:
            quoted.append(item.upper())
        else:
            escaped = item.replace('\\', '\\\\').replace('"', '\\"')
            quoted.append(f'"{escaped}"')
    return quoted



def _search(imap: imaplib.IMAP4, criteria: List[str]):
    """
    Run a UID SEARCH, declaring UTF-8 when the criteria need it.

    Subject headers with non-ASCII characters are MIME-encoded on the server, so
    an accented or em-dashed term never matches a plain SEARCH. Declaring the
    charset makes the server decode before comparing; servers that reject the
    option fall back to the plain form rather than returning nothing.
    """
    quoted = _quote_criteria(criteria)
    needs_utf8 = any(not term.isascii() for term in criteria)

    if needs_utf8:
        try:
            encoded = [t.encode('utf-8') if not t.isascii() else t for t in quoted]
            return imap.uid('SEARCH', 'CHARSET', 'UTF-8', *encoded)
        except imaplib.IMAP4.error:
            pass
    return imap.uid('SEARCH', None, *quoted)

def _split_id(message_id: str) -> Tuple[str, str]:
    mailbox, _, uid = message_id.rpartition(':')
    if not mailbox:
        raise ValueError(f"Malformed message id: {message_id!r} (expected '<mailbox>:<uid>')")
    return mailbox, uid


def _fetch_uids(imap: imaplib.IMAP4, mailbox: str, uids: List[str]) -> List[Dict]:
    messages = []
    for uid in uids:
        status, data = imap.uid('FETCH', uid, '(RFC822)')
        if status != 'OK' or not data or not isinstance(data[0], tuple):
            continue
        messages.append(_parse(data[0][1], mailbox, uid))
    return messages


# ── read ──────────────────────────────────────────────────


def search_messages(query: str = '', max_results: int = 10) -> List[Dict]:
    """Search the mailbox. Newest first, like the other drivers."""
    role, criteria = translate_query(query)

    with _Connection() as imap:
        mailbox = _resolve_folder(imap, role)
        status, _ = imap.select(f'"{mailbox}"', readonly=True)
        if status != 'OK':
            return []

        status, data = _search(imap, criteria)
        if status != 'OK':
            return []

        uids = (data[0] or b'').split()
        uids = [u.decode() for u in uids][-min(max_results, MAX_FETCH):]
        uids.reverse()
        return _fetch_uids(imap, mailbox, uids)


def get_message(message_id: str) -> Optional[Dict]:
    mailbox, uid = _split_id(message_id)
    with _Connection() as imap:
        if imap.select(f'"{mailbox}"', readonly=True)[0] != 'OK':
            return None
        found = _fetch_uids(imap, mailbox, [uid])
        return found[0] if found else None


def get_thread(thread_id: str) -> Optional[Dict]:
    """
    Rebuild a conversation from References / In-Reply-To.

    IMAP has no thread id, so we take the root Message-ID and collect every
    message that references it, across inbox and sent.
    """
    root = thread_id.strip('<>')
    collected: List[Dict] = []

    with _Connection() as imap:
        for role in ('inbox', 'sent'):
            mailbox = _resolve_folder(imap, role)
            if imap.select(f'"{mailbox}"', readonly=True)[0] != 'OK':
                continue
            status, data = imap.uid('SEARCH', None, *_quote_criteria(['HEADER', 'REFERENCES', root]))
            uids = [u.decode() for u in (data[0] or b'').split()] if status == 'OK' else []

            status, data = imap.uid('SEARCH', None, *_quote_criteria(['HEADER', 'MESSAGE-ID', f'<{root}>']))
            if status == 'OK':
                uids += [u.decode() for u in (data[0] or b'').split()]

            collected += _fetch_uids(imap, mailbox, sorted(set(uids))[:MAX_FETCH])

    if not collected:
        return None

    collected.sort(key=lambda m: email.utils.parsedate_to_datetime(m['date']).timestamp()
                   if m.get('date') else 0)
    return {'id': root, 'messages': collected, 'messageCount': len(collected)}


# ── compose ───────────────────────────────────────────────


def _build(to: str, subject: str, body: str, body_html: Optional[str] = None,
           cc: Optional[str] = None, bcc: Optional[str] = None,
           sender: Optional[str] = None, in_reply_to: Optional[str] = None,
           references: Optional[List[str]] = None) -> EmailMessage:
    config = _config()
    message = EmailMessage()
    message['From'] = sender or config['from_address']
    message['To'] = to
    message['Subject'] = subject
    if cc:
        message['Cc'] = cc
    if bcc:
        message['Bcc'] = bcc
    message['Date'] = email.utils.formatdate(localtime=True)
    message['Message-ID'] = email.utils.make_msgid()
    if in_reply_to:
        message['In-Reply-To'] = f'<{in_reply_to.strip("<>")}>'
        chain = (references or []) + [in_reply_to]
        message['References'] = ' '.join(f'<{r.strip("<>")}>' for r in chain)

    message.set_content(body or '')
    if body_html:
        message.add_alternative(body_html, subtype='html')
    return message


def create_draft(to: str, subject: str, body: str, body_html: Optional[str] = None,
                 cc: Optional[str] = None, bcc: Optional[str] = None,
                 thread_id: Optional[str] = None, sender: Optional[str] = None,
                 **kwargs) -> Dict:
    """APPEND the draft to the server's Drafts folder, so it shows up in the user's client."""
    message = _build(to, subject, body, body_html, cc, bcc, sender, in_reply_to=thread_id)

    with _Connection() as imap:
        mailbox = _resolve_folder(imap, 'drafts')
        status, response = imap.append(
            f'"{mailbox}"', '\\Draft',
            imaplib.Time2Internaldate(datetime.now().timestamp()),
            message.as_bytes(),
        )
        if status != 'OK':
            raise RuntimeError(f"APPEND to {mailbox} failed: {response}")

        uid = None
        match = re.search(rb'APPENDUID \d+ (\d+)', b' '.join(x for x in response if isinstance(x, bytes)))
        if match:
            uid = match.group(1).decode()

    return {
        'id': f'{mailbox}:{uid}' if uid else mailbox,
        'to': to,
        'subject': subject,
        'status': 'draft',
        'mailbox': mailbox,
    }


def send_message(to: str, subject: str, body: str, body_html: Optional[str] = None,
                 cc: Optional[str] = None, bcc: Optional[str] = None,
                 sender: Optional[str] = None, in_reply_to: Optional[str] = None,
                 references: Optional[List[str]] = None, **kwargs) -> Dict:
    """
    Send over SMTP, then APPEND a copy to Sent.

    The copy is what makes a sent message visible in the user's own mail client;
    without it the mailbox looks like nothing was ever sent from here.
    """
    config = _config()
    message = _build(to, subject, body, body_html, cc, bcc, sender, in_reply_to, references)

    recipients = [a for a in (to, cc, bcc) if a]
    flat = [addr for field in recipients for addr in re.split(r'[,;]\s*', field) if addr]

    context = ssl.create_default_context()
    if config['smtp_port'] == 465:
        server = smtplib.SMTP_SSL(config['smtp_host'], config['smtp_port'], context=context)
    else:
        server = smtplib.SMTP(config['smtp_host'], config['smtp_port'])
        if config['smtp_starttls']:
            server.starttls(context=context)
    try:
        server.login(config['smtp_user'], config['smtp_password'])
        server.send_message(message, to_addrs=flat)
    finally:
        server.quit()

    sent_copy = None
    try:
        with _Connection() as imap:
            mailbox = _resolve_folder(imap, 'sent')
            imap.append(f'"{mailbox}"', '\\Seen',
                        imaplib.Time2Internaldate(datetime.now().timestamp()),
                        message.as_bytes())
            sent_copy = mailbox
    except Exception:
        pass  # the mail is gone already; a missing copy must not read as a failure

    return {
        'id': message['Message-ID'].strip('<>'),
        'to': to,
        'subject': subject,
        'sent': True,
        'sent_copy': sent_copy,
    }


def send_draft(draft_id: str, confirm: Optional[str] = None, **kwargs) -> Dict:
    """Send a draft stored on the server, then drop it from Drafts."""
    mailbox, uid = _split_id(draft_id)

    with _Connection() as imap:
        if imap.select(f'"{mailbox}"')[0] != 'OK':
            raise ValueError(f"Cannot open {mailbox}")
        status, data = imap.uid('FETCH', uid, '(RFC822)')
        if status != 'OK' or not data or not isinstance(data[0], tuple):
            raise ValueError(f"Draft not found: {draft_id}")
        raw = data[0][1]

    original = email.message_from_bytes(raw)
    result = send_message(
        to=original.get('To', ''),
        subject=_decode(original.get('Subject')),
        body=_extract_body(original),
        cc=original.get('Cc'),
        sender=original.get('From'),
    )

    with _Connection() as imap:
        if imap.select(f'"{mailbox}"')[0] == 'OK':
            imap.uid('STORE', uid, '+FLAGS', '(\\Deleted)')
            imap.expunge()

    return result


def reply_to_message(message_id: str, body: str, body_html: Optional[str] = None,
                     send_immediately: bool = False, sender: Optional[str] = None,
                     confirm: Optional[str] = None, **kwargs) -> Optional[Dict]:
    """Reply in thread: Re: subject, To the original sender, References chained."""
    original = get_message(message_id)
    if not original:
        raise ValueError(f"Message not found: {message_id}")

    subject = original['subject']
    if not subject.lower().startswith('re:'):
        subject = f'Re: {subject}'

    recipient = original['from']
    parent = original.get('messageId') or ''
    references = original.get('references', [])

    if send_immediately:
        return send_message(to=recipient, subject=subject, body=body, body_html=body_html,
                            sender=sender, in_reply_to=parent, references=references)
    return create_draft(to=recipient, subject=subject, body=body, body_html=body_html,
                        thread_id=parent, sender=sender)


def reply_to_thread(thread_id: str, body: str, body_html: Optional[str] = None,
                    send_immediately: bool = False, sender: Optional[str] = None,
                    confirm: Optional[str] = None, **kwargs) -> Optional[Dict]:
    """Reply to the most recent message in a thread."""
    thread = get_thread(thread_id)
    if not thread or not thread.get('messages'):
        raise ValueError(f"Thread not found: {thread_id}")
    return reply_to_message(thread['messages'][-1]['id'], body, body_html,
                            send_immediately, sender, confirm)


# ── diagnostics ───────────────────────────────────────────


def check_connection() -> Dict:
    """Verify credentials and report which folders were resolved."""
    with _Connection() as imap:
        folders = {role: _resolve_folder(imap, role) for role in ('inbox', 'sent', 'drafts', 'trash')}
        imap.select('INBOX', readonly=True)
        status, data = imap.uid('SEARCH', None, 'ALL')
        total = len((data[0] or b'').split()) if status == 'OK' else 0

    config = _config()
    return {
        'driver': 'imap',
        'host': config['imap_host'],
        'user': config['user'],
        'from': config['from_address'],
        'smtp': f"{config['smtp_host']}:{config['smtp_port']}",
        'folders': folders,
        'inbox_messages': total,
    }


if __name__ == '__main__':
    import json
    print(json.dumps(check_connection(), indent=2))
