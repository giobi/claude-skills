#!/usr/bin/env python3
"""
Gmail API Library - WRITE Operations

Provides write functions for Gmail operations (send, draft, delete).
Used by commands for sending emails and managing drafts.
"""

import os
import mimetypes
import requests
import base64
from pathlib import Path
from typing import Optional, Dict, List, Tuple
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from email.utils import make_msgid

# Import shared utilities from gmail_read
from gmail_read import _get_headers, _make_request, get_draft_by_thread, get_thread, get_message


# ============================================================
# SIGNATURE — Centralized email signature builder
# ============================================================
# All email-generating processes MUST use build_signature()
# to ensure consistent formatting and process traceability.
#
# Format: {channel}/{ai_score}
#   channel  = which process generated the email (cmd, eml, sig, aex, chk)
#   ai_score = 0 (full AI) to 100 (full human)
#
# Channels:
#   cmd = /send command (Giobi in session)
#   eml = email-agent / email-followup-agent
#   sig = Signal-triggered action
#   aex = autonomous_executor
#   chk = email-checker
# ============================================================

# Valid channels for validation
VALID_CHANNELS = {'cmd', 'eml', 'sig', 'aex', 'chk', 'dig'}


def build_signature(channel: str = 'cmd', ai_score: int = 70) -> Tuple[str, str]:
    """
    Build Giobi's email signature with process tag.

    Args:
        channel: Process that generated the email (cmd, eml, sig, aex, chk, dig)
        ai_score: 0 = full AI, 100 = full human

    Returns:
        Tuple of (signature_html, signature_plain)
    """
    if channel not in VALID_CHANNELS:
        raise ValueError(f"Invalid channel '{channel}'. Valid: {', '.join(sorted(VALID_CHANNELS))}")

    ai_score = max(0, min(100, ai_score))
    tag = f"{channel}/{ai_score}"

    S = '&#x2500;' * 37  # riga separatore HTML

    signature_html = f"""<div style="font-family:monospace,monospace;white-space:pre">&nbsp;</div>
<div style="font-family:monospace,monospace;white-space:pre">g/</div>
<div style="font-family:monospace,monospace;white-space:pre">&nbsp;</div>
<div style="font-family:monospace,monospace;white-space:pre">{S}</div>
<div style="font-family:monospace,monospace;white-space:pre"> <b>Giobi Fasoli</b>&nbsp;&nbsp;&nbsp;*</div>
<div style="font-family:monospace,monospace;white-space:pre">{S}</div>
<div style="font-family:monospace,monospace;white-space:pre"> web&nbsp;&nbsp;&nbsp;&nbsp;<a href="https://giobi.com" style="color:#1a73e8;text-decoration:none">giobi.com</a></div>
<div style="font-family:monospace,monospace;white-space:pre"> mail&nbsp;&nbsp;&nbsp;<a href="mailto:giobi@giobi.com" style="color:#1a73e8;text-decoration:none">giobi@giobi.com</a></div>
<div style="font-family:monospace,monospace;white-space:pre"> wa&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<a href="https://wa.me/393483697620" style="color:#1a73e8;text-decoration:none">+39 348 3697620</a></div>
<div style="font-family:monospace,monospace;white-space:pre"> addr&nbsp;&nbsp;&nbsp;Via 42 Martiri 165,</div>
<div style="font-family:monospace,monospace;white-space:pre">&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;28924 Verbania (VB)</div>
<div style="font-family:monospace,monospace;white-space:pre">{S}</div>
<div style="font-family:monospace,monospace;white-space:pre"> P.IVA IT02419370032</div>
<div style="font-family:monospace,monospace;white-space:pre">{S}</div>
<div style="font-family:monospace,monospace;white-space:pre">&nbsp;&nbsp;{{o,o}}</div>
<div style="font-family:monospace,monospace;white-space:pre">&nbsp;&nbsp;/)&nbsp;&nbsp;/)&nbsp;&nbsp;&nbsp;&nbsp;{tag}</div>
<div style="font-family:monospace,monospace;white-space:pre">&nbsp;&nbsp;-&quot;-&quot;-</div>"""

    signature_plain = f"""--

g/

─────────────────────────────────────
 Giobi Fasoli   *
─────────────────────────────────────
 web    giobi.com
 mail   giobi@giobi.com
 wa     +39 348 3697620
 addr   Via 42 Martiri 165,
        28924 Verbania (VB)
─────────────────────────────────────
 P.IVA IT02419370032
─────────────────────────────────────
  {{o,o}}
  /)  /)    {tag}
  -"-"-"""

    return signature_html, signature_plain


def wrap_body_with_signature(
    body_plain: str,
    body_html: str,
    channel: str = 'cmd',
    ai_score: int = 70
) -> Tuple[str, str]:
    """
    Wrap email body with signature. Convenience function.

    Returns:
        Tuple of (full_body_html, full_body_plain)
    """
    sig_html, sig_plain = build_signature(channel, ai_score)

    mono = 'font-family:monospace,monospace;white-space:pre'
    full_html = f"""<div dir="ltr">
{body_html}
<div style="{mono}">--</div>
{sig_html}
</div>"""

    full_plain = f"""{body_plain}

{sig_plain}"""

    return full_html, full_plain


# ============================================================
# SEND GATE — Safety lock for all outgoing email
# ============================================================
# All functions that SEND email (not draft) require confirm="SEND"
# parameter. Without it, the function raises ValueError.
# This prevents accidental sends — the caller must explicitly
# pass the magic string, which acts as a code-level gate.
#
# Drafts are NOT gated (they don't leave the inbox).
# ============================================================

SEND_CONFIRM_TOKEN = "SEND"
SEND_TOKEN_FILE = "/tmp/claude-send-authorized"

# Workspace-level lock: if this file exists, ALL sending is blocked (draft-only mode).
# Path: .claude/skills/email/gmail_write.py → 4 parents up = workspace root.
_WORKSPACE_ROOT = Path(__file__).parent.parent.parent.parent
SEND_LOCK_FILE = _WORKSPACE_ROOT / "storage" / "lock" / "email"


def _check_workspace_lock(action: str = "send email"):
    """Check if workspace-level email lock is active (draft-only mode)."""
    if SEND_LOCK_FILE.exists():
        raise ValueError(
            f"🔒 BLOCKED: {action} — workspace in draft-only mode. "
            f"File lock attivo: {SEND_LOCK_FILE}. "
            f"Rimuovi storage/lock/email per abilitare l'invio."
        )


def _require_send_confirmation(confirm: Optional[str], action: str = "send email"):
    """Gate check: workspace lock + confirm='SEND' + valid /send token file."""
    # Gate 0: workspace-level lock (draft-only mode)
    _check_workspace_lock(action)

    # Gate 1: confirm parameter
    if confirm != SEND_CONFIRM_TOKEN:
        raise ValueError(
            f"❌ BLOCKED: {action} requires confirm=\"SEND\" parameter. "
            f"Got: {confirm!r}. Usa /send per inviare email."
        )
    # Gate 2: token file created by /send command — expires after 5 min
    if not os.path.exists(SEND_TOKEN_FILE):
        raise ValueError(
            f"❌ BLOCKED: {action} — nessun token /send attivo. "
            f"send_draft() può essere chiamato SOLO dal command /send."
        )
    import time
    token_age = time.time() - os.path.getmtime(SEND_TOKEN_FILE)
    if token_age > 300:
        os.remove(SEND_TOKEN_FILE)
        raise ValueError(
            f"❌ BLOCKED: {action} — token /send scaduto ({int(token_age)}s). Rilancia /send."
        )


def _attach_files(message: MIMEMultipart, attachments: List[str]) -> None:
    """Attach files to a MIME message."""
    for filepath in attachments:
        if not os.path.exists(filepath):
            print(f"⚠️  Attachment not found: {filepath}")
            continue

        content_type, _ = mimetypes.guess_type(filepath)
        if content_type is None:
            content_type = 'application/octet-stream'

        maintype, subtype = content_type.split('/', 1)
        with open(filepath, 'rb') as f:
            part = MIMEBase(maintype, subtype)
            part.set_payload(f.read())

        encoders.encode_base64(part)
        part.add_header(
            'Content-Disposition', 'attachment',
            filename=os.path.basename(filepath)
        )
        message.attach(part)


def create_draft(
    to: str,
    subject: str,
    body: str,
    body_html: Optional[str] = None,
    sender: Optional[str] = None,
    thread_id: Optional[str] = None,
    in_reply_to: Optional[str] = None,
    cc: Optional[str] = None,
    bcc: Optional[str] = None,
    require_thread: bool = False,
    attachments: Optional[List[str]] = None
) -> Optional[Dict]:
    """
    Create Gmail draft

    Args:
        to: Recipient email
        subject: Email subject
        body: Plain text body
        body_html: Optional HTML body
        sender: Optional From address (e.g. "Anacleto <anacleto@giobi.com>")
                Must be a configured alias in Gmail settings
        thread_id: Optional thread ID to attach draft to existing thread
        in_reply_to: Optional Message-ID header for threading (adds In-Reply-To and References)
        cc: Optional CC recipients (comma-separated)
        bcc: Optional BCC recipients (comma-separated)
        require_thread: If True, raises ValueError when thread_id is None
        attachments: Optional list of file paths to attach

    Returns:
        Draft object or None

    Raises:
        ValueError: If require_thread=True and thread_id is None
    """
    # Validation: require_thread mode
    if require_thread and not thread_id:
        raise ValueError(
            "❌ thread_id is required. "
            "This command can only create drafts attached to existing threads. "
            "Use /send for standalone drafts."
        )

    has_attachments = attachments and len(attachments) > 0

    # Create message - use mixed for attachments
    if has_attachments:
        message = MIMEMultipart('mixed')
        if body_html:
            text_part = MIMEMultipart('alternative')
            text_part.attach(MIMEText(body, 'plain'))
            text_part.attach(MIMEText(body_html, 'html'))
            message.attach(text_part)
        else:
            message.attach(MIMEText(body, 'plain'))
        _attach_files(message, attachments)
    elif body_html:
        message = MIMEMultipart('alternative')
        message.attach(MIMEText(body, 'plain'))
        message.attach(MIMEText(body_html, 'html'))
    else:
        message = MIMEText(body, 'plain')

    message['To'] = to
    message['Subject'] = subject
    message['Message-ID'] = make_msgid(domain='giobi.com')
    if sender:
        message['From'] = sender
    if cc:
        message['Cc'] = cc
    if bcc:
        message['Bcc'] = bcc

    # Add threading headers if replying
    if in_reply_to:
        message['In-Reply-To'] = in_reply_to
        message['References'] = in_reply_to

    # Encode message
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()

    # Create draft - include threadId if provided
    draft_body = {
        'message': {
            'raw': raw
        }
    }
    if thread_id:
        draft_body['message']['threadId'] = thread_id

    response = _make_request(
        'POST',
        'https://gmail.googleapis.com/gmail/v1/users/me/drafts',
        json=draft_body
    )

    if response.status_code != 200:
        print(f"❌ Error creating draft: {response.status_code}")
        print(response.text)
        return None

    return response.json()


def send_message(
    to: str,
    subject: str,
    body: str,
    body_html: Optional[str] = None,
    sender: Optional[str] = None,
    cc: Optional[str] = None,
    bcc: Optional[str] = None,
    thread_id: Optional[str] = None,
    confirm: Optional[str] = None
) -> Optional[Dict]:
    """
    Send email directly (not draft)

    Args:
        to: Recipient email
        subject: Email subject
        body: Plain text body
        body_html: Optional HTML body
        sender: Optional From address (e.g. "Anacleto <anacleto@giobi.com>")
                Must be a configured alias in Gmail settings
        cc: Optional CC recipients (comma-separated)
        bcc: Optional BCC recipients (comma-separated)
        thread_id: Optional thread ID to reply in existing thread
        confirm: REQUIRED safety gate — must be "SEND" to proceed

    Returns:
        Sent message object or None

    Raises:
        ValueError: If confirm != "SEND"
    """
    _require_send_confirmation(confirm, f"send_message to {to}")

    # Create message
    if body_html:
        message = MIMEMultipart('alternative')
        message.attach(MIMEText(body, 'plain'))
        message.attach(MIMEText(body_html, 'html'))
    else:
        message = MIMEText(body, 'plain')

    message['To'] = to
    message['Subject'] = subject
    message['Message-ID'] = make_msgid(domain='giobi.com')
    if sender:
        message['From'] = sender
    if cc:
        message['Cc'] = cc
    if bcc:
        message['Bcc'] = bcc

    # Encode message
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()

    # Prepare request body
    request_body = {'raw': raw}
    if thread_id:
        request_body['threadId'] = thread_id

    # Send
    response = _make_request(
        'POST',
        'https://gmail.googleapis.com/gmail/v1/users/me/messages/send',
        json=request_body
    )

    if response.status_code != 200:
        print(f"❌ Error sending message: {response.status_code}")
        print(response.text)
        return None

    return response.json()


def delete_draft(draft_id: str) -> bool:
    """
    Delete a Gmail draft

    Args:
        draft_id: Draft ID to delete

    Returns:
        True if deleted successfully, False otherwise
    """
    response = _make_request(
        'DELETE',
        f'https://gmail.googleapis.com/gmail/v1/users/me/drafts/{draft_id}'
    )

    if response.status_code == 204:
        return True

    print(f"❌ Error deleting draft: {response.status_code}")
    print(response.text)
    return False


def send_draft(draft_id: str, confirm: Optional[str] = None) -> Optional[Dict]:
    """
    Send an existing Gmail draft

    Args:
        draft_id: Draft ID to send
        confirm: REQUIRED safety gate — must be "SEND" to proceed

    Returns:
        Sent message object or None

    Raises:
        ValueError: If confirm != "SEND"
    """
    _require_send_confirmation(confirm, f"send_draft {draft_id}")

    response = _make_request(
        'POST',
        'https://gmail.googleapis.com/gmail/v1/users/me/drafts/send',
        json={'id': draft_id}
    )

    if response.status_code != 200:
        print(f"❌ Error sending draft: {response.status_code}")
        print(response.text)
        return None

    return response.json()


def update_draft_in_thread(
    thread_id: str,
    to: str,
    subject: str,
    body: str,
    body_html: Optional[str] = None,
    sender: Optional[str] = None,
    cc: Optional[str] = None,
    bcc: Optional[str] = None
) -> Optional[Dict]:
    """
    Update draft in a thread (delete existing + create new)

    This is the SAFE way to "edit" a draft - Gmail API doesn't support PATCH,
    so we delete the old draft and create a new one in the same thread.

    Args:
        thread_id: Gmail thread ID (REQUIRED)
        to: Recipient email
        subject: Email subject
        body: Plain text body
        body_html: Optional HTML body
        sender: Optional From address
        cc: Optional CC recipients
        bcc: Optional BCC recipients

    Returns:
        New draft object with URL, or None if failed
    """
    if not thread_id:
        raise ValueError("❌ thread_id is required for update_draft_in_thread()")

    # 1. Find existing draft in thread
    existing_draft = get_draft_by_thread(thread_id)

    # 2. Delete old draft if exists
    if existing_draft:
        success = delete_draft(existing_draft['id'])
        if not success:
            print(f"⚠️  Warning: Failed to delete old draft {existing_draft['id']}")
            # Continue anyway - we'll create new draft

    # 3. Create new draft in thread
    new_draft = create_draft(
        to=to,
        subject=subject,
        body=body,
        body_html=body_html,
        sender=sender,
        thread_id=thread_id,
        cc=cc,
        bcc=bcc
    )

    if new_draft:
        # Add action metadata for user feedback
        new_draft['action'] = 'replaced' if existing_draft else 'created'
        if existing_draft:
            new_draft['old_draft_id'] = existing_draft['id']

    return new_draft


def reply_to_message(
    message_id: str,
    body: str,
    body_html: Optional[str] = None,
    send_immediately: bool = False,
    sender: Optional[str] = None,
    confirm: Optional[str] = None
) -> Optional[Dict]:
    """
    Reply to a message with proper threading

    Args:
        message_id: Original message ID to reply to
        body: Reply text (plain)
        body_html: Optional HTML reply
        send_immediately: If True, send directly; if False, create draft
        sender: Optional From address (e.g. "Anacleto <anacleto@giobi.com>")
                Must be a configured alias in Gmail settings
        confirm: REQUIRED when send_immediately=True — must be "SEND"

    Returns:
        Draft/sent message object or None

    Raises:
        ValueError: If send_immediately=True and confirm != "SEND"
    """
    if send_immediately:
        _require_send_confirmation(confirm, f"reply_to_message {message_id}")
    # Get original message for headers
    original = get_message(message_id)
    if not original:
        return None

    # Extract headers
    headers_list = original['payload']['headers']
    original_headers = {}

    for header in headers_list:
        name = header['name'].lower()
        value = header['value']
        if name in ['from', 'to', 'subject', 'message-id', 'references']:
            original_headers[name] = value

    # Check if this is a SENT email (I sent it) or RECEIVED email
    labels = original.get('labelIds', [])
    is_sent_by_me = 'SENT' in labels

    # Build reply - recipient depends on whether I sent or received the original
    if is_sent_by_me:
        # I sent this email, reply goes to original recipient (to)
        to = original_headers.get('to', '')
    else:
        # I received this email, reply goes to sender (from)
        to = original_headers.get('from', '')

    subject = original_headers.get('subject', '')

    if not subject.startswith('Re: '):
        subject = f"Re: {subject}"

    # Build References header for threading
    references = original_headers.get('references', '')
    message_id_header = original_headers.get('message-id', '')

    if references:
        references = f"{references} {message_id_header}"
    else:
        references = message_id_header

    # Create reply message
    if body_html:
        message = MIMEMultipart('alternative')
        message.attach(MIMEText(body, 'plain'))
        message.attach(MIMEText(body_html, 'html'))
    else:
        message = MIMEText(body, 'plain')

    message['To'] = to
    message['Subject'] = subject
    message['In-Reply-To'] = message_id_header
    message['References'] = references
    if sender:
        message['From'] = sender

    # Encode
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()

    # Send or draft
    if send_immediately:
        endpoint = 'https://gmail.googleapis.com/gmail/v1/users/me/messages/send'
        body_data = {
            'raw': raw,
            'threadId': original.get('threadId')
        }
    else:
        endpoint = 'https://gmail.googleapis.com/gmail/v1/users/me/drafts'
        body_data = {
            'message': {
                'raw': raw,
                'threadId': original.get('threadId')
            }
        }

    response = _make_request('POST', endpoint, json=body_data)

    if response.status_code != 200:
        print(f"❌ Error: {response.status_code}")
        print(response.text)
        return None

    return response.json()


def reply_to_thread(
    thread_id: str,
    body: str,
    body_html: Optional[str] = None,
    send_immediately: bool = False,
    sender: Optional[str] = None,
    confirm: Optional[str] = None
) -> Optional[Dict]:
    """
    Reply to a thread (finds last message automatically)

    This is the PREFERRED way to reply - just pass thread_id and it handles the rest.

    Args:
        thread_id: Gmail thread ID
        body: Reply text (plain)
        body_html: Optional HTML reply
        send_immediately: If True, send directly; if False, create draft
        sender: Optional From address (e.g. "Anacleto <anacleto@giobi.com>")
                Must be a configured alias in Gmail settings
        confirm: REQUIRED when send_immediately=True — must be "SEND"

    Returns:
        Draft/sent message object or None

    Raises:
        ValueError: If send_immediately=True and confirm != "SEND"
    """
    # Get thread to find last message
    thread = get_thread(thread_id)
    if not thread:
        print(f"❌ Thread {thread_id} not found")
        return None

    messages = thread.get('messages', [])
    if not messages:
        print(f"❌ Thread {thread_id} has no messages")
        return None

    # Last message in thread
    last_message_id = messages[-1]['id']

    return reply_to_message(
        message_id=last_message_id,
        body=body,
        body_html=body_html,
        send_immediately=send_immediately,
        sender=sender,
        confirm=confirm
    )


def trash_message(message_id: str) -> bool:
    """
    Move a message to trash

    Args:
        message_id: Message ID to trash

    Returns:
        True if trashed successfully, False otherwise
    """
    response = _make_request(
        'POST',
        f'https://gmail.googleapis.com/gmail/v1/users/me/messages/{message_id}/trash'
    )

    if response.status_code == 200:
        return True

    print(f"❌ Error trashing message: {response.status_code}")
    print(response.text)
    return False


def archive_message(message_id: str) -> bool:
    """
    Archive a message (remove INBOX label)

    Args:
        message_id: Message ID to archive

    Returns:
        True if archived successfully, False otherwise
    """
    response = _make_request(
        'POST',
        f'https://gmail.googleapis.com/gmail/v1/users/me/messages/{message_id}/modify',
        json={'removeLabelIds': ['INBOX']}
    )

    if response.status_code == 200:
        return True

    print(f"❌ Error archiving message: {response.status_code}")
    print(response.text)
    return False


def batch_trash_messages(message_ids: list) -> Dict:
    """
    Trash multiple messages.

    Args:
        message_ids: List of message IDs to trash

    Returns:
        Dict with 'trashed' count and 'failed' list
    """
    trashed = 0
    failed = []
    for mid in message_ids:
        if trash_message(mid):
            trashed += 1
        else:
            failed.append(mid)
    return {'trashed': trashed, 'failed': failed}


def batch_archive_messages(message_ids: list) -> Dict:
    """
    Archive multiple messages (remove INBOX label).

    Args:
        message_ids: List of message IDs to archive

    Returns:
        Dict with 'archived' count and 'failed' list
    """
    archived = 0
    failed = []
    for mid in message_ids:
        if archive_message(mid):
            archived += 1
        else:
            failed.append(mid)
    return {'archived': archived, 'failed': failed}


def batch_trash_threads(thread_ids: list) -> Dict:
    """
    Trash entire threads (all messages in each thread).

    Gmail API works on messages, not threads. This helper:
    1. Fetches all message IDs for each thread
    2. Calls batch_trash_messages with all message IDs

    Args:
        thread_ids: List of thread IDs to trash

    Returns:
        Dict with 'threads_processed', 'messages_trashed', 'failed_threads'
    """
    from gmail_read import get_thread

    all_msg_ids = []
    failed_threads = []
    threads_processed = 0

    for tid in thread_ids:
        try:
            thread = get_thread(tid)
            if thread and 'messages' in thread:
                msg_ids = [msg['id'] for msg in thread['messages']]
                all_msg_ids.extend(msg_ids)
                threads_processed += 1
            else:
                failed_threads.append(tid)
        except Exception as e:
            print(f"❌ Error fetching thread {tid}: {e}")
            failed_threads.append(tid)

    # Trash all messages
    result = batch_trash_messages(all_msg_ids)

    return {
        'threads_processed': threads_processed,
        'messages_trashed': result['trashed'],
        'failed_threads': failed_threads,
        'failed_messages': result['failed']
    }


def batch_archive_threads(thread_ids: list) -> Dict:
    """
    Archive entire threads (remove INBOX label from all messages in each thread).

    Gmail API works on messages, not threads. This helper:
    1. Fetches all message IDs for each thread
    2. Calls batch_archive_messages with all message IDs

    Args:
        thread_ids: List of thread IDs to archive

    Returns:
        Dict with 'threads_processed', 'messages_archived', 'failed_threads'
    """
    from gmail_read import get_thread

    all_msg_ids = []
    failed_threads = []
    threads_processed = 0

    for tid in thread_ids:
        try:
            thread = get_thread(tid)
            if thread and 'messages' in thread:
                msg_ids = [msg['id'] for msg in thread['messages']]
                all_msg_ids.extend(msg_ids)
                threads_processed += 1
            else:
                failed_threads.append(tid)
        except Exception as e:
            print(f"❌ Error fetching thread {tid}: {e}")
            failed_threads.append(tid)

    # Archive all messages
    result = batch_archive_messages(all_msg_ids)

    return {
        'threads_processed': threads_processed,
        'messages_archived': result['archived'],
        'failed_threads': failed_threads,
        'failed_messages': result['failed']
    }


def get_or_create_label(label_name: str) -> Optional[str]:
    """
    Get label ID by name, creating it if it doesn't exist.

    Args:
        label_name: Label name (e.g. "transactional")

    Returns:
        Label ID string or None on error
    """
    # List existing labels
    response = _make_request('GET', 'https://gmail.googleapis.com/gmail/v1/users/me/labels')
    if response.status_code != 200:
        print(f"Error listing labels: {response.status_code}")
        return None

    labels = response.json().get('labels', [])
    for label in labels:
        if label['name'].lower() == label_name.lower():
            return label['id']

    # Create label
    response = _make_request(
        'POST',
        'https://gmail.googleapis.com/gmail/v1/users/me/labels',
        json={
            'name': label_name,
            'labelListVisibility': 'labelShow',
            'messageListVisibility': 'show'
        }
    )
    if response.status_code == 200:
        label_id = response.json()['id']
        print(f"Created label '{label_name}' (id: {label_id})")
        return label_id

    print(f"Error creating label: {response.status_code} {response.text}")
    return None


def label_message(message_id: str, label_id: str) -> bool:
    """Add a label to a message."""
    response = _make_request(
        'POST',
        f'https://gmail.googleapis.com/gmail/v1/users/me/messages/{message_id}/modify',
        json={'addLabelIds': [label_id]}
    )
    return response.status_code == 200


def batch_label_and_archive_threads(thread_ids: list, label_name: str) -> Dict:
    """
    Add a label to all messages in threads and archive them.

    Args:
        thread_ids: List of thread IDs
        label_name: Label to add (e.g. "transactional")

    Returns:
        Dict with counts
    """
    from gmail_read import get_thread

    label_id = get_or_create_label(label_name)
    if not label_id:
        return {'error': f'Could not get/create label {label_name}'}

    all_msg_ids = []
    failed_threads = []
    threads_processed = 0

    for tid in thread_ids:
        try:
            thread = get_thread(tid)
            if thread and 'messages' in thread:
                msg_ids = [msg['id'] for msg in thread['messages']]
                all_msg_ids.extend(msg_ids)
                threads_processed += 1
            else:
                failed_threads.append(tid)
        except Exception as e:
            print(f"Error fetching thread {tid}: {e}")
            failed_threads.append(tid)

    # Label + archive each message
    labeled = 0
    archived = 0
    failed = []
    for mid in all_msg_ids:
        try:
            response = _make_request(
                'POST',
                f'https://gmail.googleapis.com/gmail/v1/users/me/messages/{mid}/modify',
                json={'addLabelIds': [label_id], 'removeLabelIds': ['INBOX']}
            )
            if response.status_code == 200:
                labeled += 1
                archived += 1
            else:
                failed.append(mid)
        except Exception as e:
            failed.append(mid)

    return {
        'threads_processed': threads_processed,
        'messages_labeled': labeled,
        'messages_archived': archived,
        'failed_threads': failed_threads,
        'failed_messages': failed
    }
