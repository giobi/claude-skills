#!/usr/bin/env python3
"""
Email Adapter — Unified interface for Gmail and O365.

Auto-detects driver from .env, exposes common operations,
handles workspace lock centrally.

Usage:
    from adapter import EmailAdapter
    mail = EmailAdapter()  # auto-detect driver
    mail.search("from:david")
    mail.draft(to="x@y.com", subject="Test", body="Hello")
    mail.send(to="x@y.com", subject="Test", body="Hello", confirm="SEND")
"""

import os
import sys
from pathlib import Path
from typing import Optional, Dict, List, Tuple


def _find_workspace_root(start: Optional[Path] = None) -> Path:
    """Find workspace root by searching upward for boot/ directory (brain marker)."""
    current = (start or Path(__file__)).resolve().parent
    for _ in range(10):
        if (current / 'boot').is_dir() and (current / '.env').exists():
            return current
        if current.parent == current:
            break
        current = current.parent
    # Fallback: .env-only search (non-brain workspaces)
    current = (start or Path(__file__)).resolve().parent
    for _ in range(10):
        if (current / '.env').exists() and not (current / '.claude').is_dir():
            return current
        if current.parent == current:
            break
        current = current.parent
    return Path.cwd()


WORKSPACE_ROOT = _find_workspace_root()
LOCK_FILE = WORKSPACE_ROOT / "storage" / "lock" / "email"
SEND_TOKEN_FILE = Path("/tmp/claude-send-authorized")
SEND_CONFIRM_TOKEN = "SEND"


def _detect_driver() -> str:
    """Detect email driver from .env file. Returns 'gmail' or 'o365'."""
    env_file = WORKSPACE_ROOT / '.env'
    if not env_file.exists():
        raise RuntimeError(f"No .env found at {env_file}")

    content = env_file.read_text()

    # O365 takes priority if both exist (more specific)
    if 'O365_CLIENT_ID' in content or 'O365_REFRESH_TOKEN' in content:
        return 'o365'
    if 'GMAIL_CLIENT_ID' in content or 'GMAIL_REFRESH_TOKEN' in content:
        return 'gmail'

    raise RuntimeError(
        f"No email credentials found in {env_file}. "
        "Need GMAIL_* or O365_* variables."
    )


def _check_lock(action: str = "send email"):
    """Check workspace-level email lock (draft-only mode)."""
    if LOCK_FILE.exists():
        raise ValueError(
            f"🔒 BLOCKED: {action} — workspace in draft-only mode. "
            f"Lock: {LOCK_FILE}. Rimuovi storage/lock/email per abilitare."
        )


def _check_send_gate(confirm: Optional[str], action: str = "send email"):
    """Full send gate: lock + confirm token + token file."""
    _check_lock(action)

    if confirm != SEND_CONFIRM_TOKEN:
        raise ValueError(
            f"❌ BLOCKED: {action} requires confirm=\"SEND\". "
            f"Got: {confirm!r}. Usa /send."
        )
    if not SEND_TOKEN_FILE.exists():
        raise ValueError(
            f"❌ BLOCKED: {action} — nessun token /send attivo."
        )
    import time
    age = time.time() - SEND_TOKEN_FILE.stat().st_mtime
    if age > 300:
        SEND_TOKEN_FILE.unlink(missing_ok=True)
        raise ValueError(
            f"❌ BLOCKED: {action} — token scaduto ({int(age)}s). Rilancia /send."
        )


class EmailAdapter:
    """Unified email interface. Auto-detects Gmail or O365."""

    def __init__(self, driver: Optional[str] = None):
        self.driver_name = driver or _detect_driver()
        self._load_driver()

    def _load_driver(self):
        """Load the appropriate driver module."""
        drivers_dir = Path(__file__).parent / "drivers" / self.driver_name
        if not drivers_dir.exists():
            raise RuntimeError(f"Driver not found: {drivers_dir}")

        sys.path.insert(0, str(drivers_dir))

        if self.driver_name == 'gmail':
            import gmail_read as _read
            import gmail_write as _write
            self._read = _read
            self._write = _write
        elif self.driver_name == 'o365':
            import o365 as _o365
            self._o365 = _o365
        else:
            raise RuntimeError(f"Unknown driver: {self.driver_name}")

    @property
    def is_locked(self) -> bool:
        return LOCK_FILE.exists()

    # ── READ ──────────────────────────────────────────────

    def search(self, query: str, max_results: int = 10) -> List[Dict]:
        if self.driver_name == 'gmail':
            return self._read.search_messages(query, max_results=max_results)
        else:
            return self._o365.search_messages(query, max_results=max_results)

    def get_messages(self, max_results: int = 20, **kwargs) -> List[Dict]:
        if self.driver_name == 'gmail':
            return self._read.search_messages("in:inbox", max_results=max_results)
        else:
            return self._o365.get_messages(max_results=max_results, **kwargs)

    def get_message(self, message_id: str) -> Optional[Dict]:
        if self.driver_name == 'gmail':
            return self._read.get_message(message_id)
        else:
            # O365 doesn't have single message fetch in shared wrapper
            results = self._o365.search_messages(f"id:{message_id}", max_results=1)
            return results[0] if results else None

    def get_thread(self, thread_id: str) -> Optional[Dict]:
        if self.driver_name == 'gmail':
            return self._read.get_thread(thread_id)
        else:
            # O365: threads = conversation chains, not natively supported the same way
            return None

    # ── DRAFT (no gate) ───────────────────────────────────

    def draft(
        self,
        to: str,
        subject: str,
        body: str,
        body_html: Optional[str] = None,
        cc: Optional[str] = None,
        bcc: Optional[str] = None,
        thread_id: Optional[str] = None,
        sender: Optional[str] = None,
        **kwargs
    ) -> Optional[Dict]:
        """Create draft. No lock check — drafts are always allowed."""
        if self.driver_name == 'gmail':
            return self._write.create_draft(
                to=to, subject=subject, body=body, body_html=body_html,
                cc=cc, bcc=bcc, thread_id=thread_id, sender=sender, **kwargs
            )
        else:
            # O365: use the draft staging mechanism
            from o365 import send_message as _raw
            # O365 doesn't have native draft API in our wrapper — stage locally
            import json
            draft_file = WORKSPACE_ROOT / "storage" / "email-draft.json"
            draft_file.parent.mkdir(parents=True, exist_ok=True)
            draft_data = {
                'to': to, 'subject': subject, 'body': body or body_html,
                'cc': cc, 'body_type': 'HTML' if body_html else 'Text',
                'status': 'PENDING_APPROVAL'
            }
            draft_file.write_text(json.dumps(draft_data, indent=2))
            return {'id': str(draft_file), 'status': 'staged', **draft_data}

    # ── SEND (gated) ─────────────────────────────────────

    def send(
        self,
        to: str,
        subject: str,
        body: str,
        body_html: Optional[str] = None,
        cc: Optional[str] = None,
        bcc: Optional[str] = None,
        sender: Optional[str] = None,
        confirm: Optional[str] = None,
        **kwargs
    ) -> Optional[Dict]:
        """Send email. Requires confirm='SEND' + token + no lock."""
        _check_send_gate(confirm, f"send to {to}")

        if self.driver_name == 'gmail':
            return self._write.send_message(
                to=to, subject=subject, body=body, body_html=body_html,
                cc=cc, bcc=bcc, sender=sender, confirm=confirm, **kwargs
            )
        else:
            result = self._o365.send_message(
                to=to, subject=subject, body=body_html or body,
                cc=cc, body_type='HTML' if body_html else 'Text'
            )
            return {'sent': result, 'to': to, 'subject': subject}

    def send_draft(self, draft_id: str, confirm: Optional[str] = None) -> Optional[Dict]:
        """Send existing draft. Gated."""
        _check_send_gate(confirm, f"send_draft {draft_id}")

        if self.driver_name == 'gmail':
            return self._write.send_draft(draft_id, confirm=confirm)
        else:
            # O365: read staged draft and send
            import json
            draft_file = Path(draft_id) if '/' in draft_id else WORKSPACE_ROOT / "storage" / "email-draft.json"
            if not draft_file.exists():
                raise ValueError(f"Draft not found: {draft_file}")
            d = json.loads(draft_file.read_text())
            if d.get('status') != 'PENDING_APPROVAL':
                raise ValueError("Draft already sent or invalid")
            result = self._o365.send_message(
                to=d['to'], subject=d['subject'], body=d['body'],
                cc=d.get('cc'), body_type=d.get('body_type', 'HTML')
            )
            d['status'] = 'SENT' if result else 'FAILED'
            draft_file.write_text(json.dumps(d, indent=2))
            return {'sent': result, **d}

    # ── REPLY ─────────────────────────────────────────────

    def reply(
        self,
        thread_id: Optional[str] = None,
        message_id: Optional[str] = None,
        body: str = "",
        body_html: Optional[str] = None,
        send_immediately: bool = False,
        sender: Optional[str] = None,
        confirm: Optional[str] = None,
    ) -> Optional[Dict]:
        """Reply to thread or message. Draft by default, send if send_immediately=True."""
        if send_immediately:
            _check_send_gate(confirm, "reply")

        if self.driver_name == 'gmail':
            if thread_id:
                return self._write.reply_to_thread(
                    thread_id=thread_id, body=body, body_html=body_html,
                    send_immediately=send_immediately, sender=sender, confirm=confirm
                )
            elif message_id:
                return self._write.reply_to_message(
                    message_id=message_id, body=body, body_html=body_html,
                    send_immediately=send_immediately, sender=sender, confirm=confirm
                )
        else:
            # O365: reply = new message in conversation (simplified)
            if send_immediately:
                return self.send(to="", subject="", body=body, body_html=body_html, confirm=confirm)
            else:
                return self.draft(to="", subject="", body=body, body_html=body_html)

    # ── UTILITY ───────────────────────────────────────────

    def info(self) -> Dict:
        """Return adapter info."""
        return {
            'driver': self.driver_name,
            'workspace': str(WORKSPACE_ROOT),
            'locked': self.is_locked,
            'lock_file': str(LOCK_FILE),
        }

    def __repr__(self):
        lock = " LOCKED" if self.is_locked else ""
        return f"<EmailAdapter driver={self.driver_name}{lock} ws={WORKSPACE_ROOT.name}>"
