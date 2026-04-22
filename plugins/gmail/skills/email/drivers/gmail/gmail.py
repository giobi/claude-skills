#!/usr/bin/env python3
"""
⚠️  DEPRECATED COMPATIBILITY LAYER ⚠️

This module is DEPRECATED as of 2026-02-06.

The Gmail wrapper has been split into focused modules:
  - gmail_read.py  → Read operations (search, get_thread, get_message, list_drafts)
  - gmail_write.py → Write operations (send_message, create_draft, update_draft_in_thread)

MIGRATION REQUIRED:
  OLD: from gmail import send_message, get_thread
  NEW: from gmail_read import get_thread
       from gmail_write import send_message

WHY THE SPLIT:
  - Separation of concerns (read vs write)
  - Validation logic (require_thread for /email command)
  - Safe helper functions (update_draft_in_thread)
  - Approval-first protocol for email commands

This compatibility wrapper will be REMOVED in a future version.
Migrate your code now!

---

For backward compatibility, this module re-exports all functions from the new modules.
You'll see this warning every time you import from gmail.py.
"""

import sys
import warnings

# LOUD deprecation warning
_WARNING = """
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️  DEPRECATION WARNING: gmail.py is DEPRECATED! ⚠️
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

This file imports from a deprecated module.

MIGRATE TO:
  from gmail_read import search_messages, get_thread, get_message, list_drafts
  from gmail_write import send_message, create_draft, update_draft_in_thread

The Gmail wrapper was split on 2026-02-06 to support:
  - /email command (orchestrator, in-thread drafts only)
  - /send command (direct actions, standalone drafts)
  - Approval-first protocol (show → confirm → execute)

This compatibility layer will be REMOVED soon.
See: /home/claude/brain/TOOLS.md for migration guide

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

# Print to stderr so it's visible even if stdout is captured
print(_WARNING, file=sys.stderr)

# Also use warnings module for proper Python deprecation
warnings.warn(
    "gmail.py is deprecated. Use gmail_read.py and gmail_write.py instead.",
    DeprecationWarning,
    stacklevel=2
)

# Re-export everything from new modules for backward compatibility
# This allows existing code to continue working while showing the warning
try:
    from gmail_read import *  # noqa: F401,F403
    from gmail_write import *  # noqa: F401,F403
except ImportError as e:
    print(f"❌ Error importing new Gmail modules: {e}", file=sys.stderr)
    print("Falling back to gmail_legacy.py...", file=sys.stderr)
    from gmail_legacy import *  # noqa: F401,F403
