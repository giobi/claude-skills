"""
Discord API Library for Brain

Simple REST API wrapper for Discord bot operations.
No websocket/gateway - just REST calls.

CRITICAL: MAI usare DM! Sempre canale #anacleto del server:
- #anacleto (1444847905331740815) per TUTTE le comunicazioni
- Project channels per notifiche progetto specifiche

SECURITY: Tutte le operazioni di invio sono limitate ai canali del server giobi.com.
DM sono DISABILITATI a livello di codice.

Usage:
    from discord import send_to_channel, send_file, read_messages, create_channel

Environment:
    DISCORD_BOT_TOKEN - Bot token (required)

Project Channels:
    Reads discord_channel from project frontmatter in wiki/projects/*.md
    Caches the mapping for performance.
"""

import os
import re
import glob
import requests
from pathlib import Path
from typing import Optional, List, Dict
from dotenv import load_dotenv

try:
    import yaml
except ImportError:
    yaml = None

_BRAIN_ROOT = Path(__file__).parent.parent.parent.resolve()
load_dotenv(str(_BRAIN_ROOT / '.env'))

# Brain paths
BRAIN_PATH = str(_BRAIN_ROOT)
PROJECTS_PATH = f"{BRAIN_PATH}/wiki/projects"

# Constants
API_BASE = "https://discord.com/api/v10"
BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN')
GUILD_ID = "1051830434809516112"  # giobi.com server
GIOBI_USER_ID = "381038269376364544"
PROJECTS_CATEGORY_ID = "1442536595159908362"
ALERTS_CATEGORY_ID = "1442538533976801403"

# 3-tier log channel mapping — all go to #anacleto (unified)
LOG_CHANNELS = {
    "error": "1444847905331740815",     # 🦉︱anacleto (was 🔴︱error)
    "warning": "1444847905331740815",   # 🦉︱anacleto (was 🟡︱warning)
    "info": "1444847905331740815",      # 🦉︱anacleto (was 🟢︱info)
}

# Inbox channel for processing
INBOX_CHANNEL_ID = "1444066328091562017"  # 📥︱inbox

# Anacleto channel - canale principale per TUTTE le comunicazioni agent
MAIN_DISCORD_CHANNEL_ID = "1444847905331740815"  # 🦉︱anacleto
MAIN_DISCORD_CHANNEL_ID_LEGACY = MAIN_DISCORD_CHANNEL_ID  # Alias legacy (breve parentesi dragonesca)

# Legacy alert channels (DEPRECATED - do not use)
LEGACY_ALERT_CHANNELS = {
    "critical": "1442538542730313778",  # 🚨︱critical - DEPRECATED
    "alerts": "1442538535918768231",    # ⚠️︱alerts - DEPRECATED
}

# Webhooks for posting as Anacleto
PROJECT_WEBHOOKS = {
    "stresasalute-it": "https://discord.com/api/webhooks/1442554772673663047/xMUz21to-a9JBwQUshMXsJrdBhcwZDdKupwXkqmUya2q7l1KNwfDqj80uPPiVQ7xfSJ3",
}

# Cache for project channels (loaded from frontmatter)
_project_channels_cache: Optional[Dict[str, str]] = None


def _parse_frontmatter(content: str) -> dict:
    """Extract YAML frontmatter from markdown content"""
    match = re.match(r'^---\n(.*?)\n---', content, re.DOTALL)
    if not match:
        return {}

    if yaml:
        try:
            return yaml.safe_load(match.group(1)) or {}
        except:
            return {}
    else:
        # Fallback: simple regex for discord_channel
        ch_match = re.search(r'discord_channel:\s*([^\n]+)', match.group(1))
        if ch_match:
            return {'discord_channel': ch_match.group(1).strip()}
        return {}


def _load_project_channels() -> Dict[str, str]:
    """Load discord_channel mappings from project frontmatter files"""
    global _project_channels_cache

    if _project_channels_cache is not None:
        return _project_channels_cache

    channels = {}

    for filepath in glob.glob(f"{PROJECTS_PATH}/**/*.md", recursive=True) + glob.glob(f"{PROJECTS_PATH}/*.md"):
        filename = os.path.basename(filepath)
        parent_dir = os.path.basename(os.path.dirname(filepath))
        is_root_index = filename == 'index.md' and parent_dir == 'projects'

        if is_root_index or 'OLD' in filename:
            continue

        try:
            with open(filepath, 'r') as f:
                content = f.read()

            fm = _parse_frontmatter(content)
            discord_channel = fm.get('discord_channel')

            if discord_channel:
                # Map both the channel name and normalized project name
                channels[discord_channel] = discord_channel

                # For index.md in subdirectory, use the directory name as project name
                if filename == 'index.md':
                    project_name = parent_dir.lower()
                else:
                    project_name = filename.replace('.md', '').lower()

                channels[project_name] = discord_channel

                # And the normalized version
                normalized = project_name.replace('.', '-')
                channels[normalized] = discord_channel

        except Exception:
            continue

    _project_channels_cache = channels
    return channels


def get_project_channel(project: str) -> Optional[str]:
    """Get Discord channel name for a project (reads from frontmatter)"""
    channels = _load_project_channels()

    # Normalize input
    normalized = project.lower().replace('.', '-').replace('_', '-')

    # Try exact match first
    if normalized in channels:
        return channels[normalized]

    # Try original name
    if project.lower() in channels:
        return channels[project.lower()]

    return None


def clear_project_channels_cache():
    """Clear the project channels cache (call after modifying project files)"""
    global _project_channels_cache
    _project_channels_cache = None


def list_configured_projects() -> Dict[str, str]:
    """List all projects that have discord_channel configured"""
    channels = _load_project_channels()
    # Return unique channel names (deduplicated)
    unique = {}
    for key, value in channels.items():
        if value not in unique.values() or key == value:
            unique[key] = value
    return {k: v for k, v in unique.items() if k == v}


def _headers() -> dict:
    return {
        "Authorization": f"Bot {BOT_TOKEN}",
        "Content-Type": "application/json"
    }


def send_dm(message: str, user_id: str = GIOBI_USER_ID) -> dict:
    """DISABLED - DM are not allowed. Use send_to_channel() instead."""
    return {"error": "DM disabled. Use send_to_channel() with a server channel instead."}


def _split_message(text: str, max_len: int = 2000) -> List[str]:
    """Split a message into chunks that fit Discord's 2000 char limit.

    Tries to split at natural boundaries (newlines, then spaces).
    """
    if len(text) <= max_len:
        return [text]

    chunks = []
    while text:
        if len(text) <= max_len:
            chunks.append(text)
            break

        # Find a good split point
        split_at = max_len

        # Try to split at double newline (paragraph)
        last_para = text.rfind('\n\n', 0, max_len)
        if last_para > max_len // 2:
            split_at = last_para + 2
        else:
            # Try single newline
            last_nl = text.rfind('\n', 0, max_len)
            if last_nl > max_len // 2:
                split_at = last_nl + 1
            else:
                # Try space
                last_space = text.rfind(' ', 0, max_len)
                if last_space > max_len // 2:
                    split_at = last_space + 1

        chunks.append(text[:split_at])
        text = text[split_at:]

    return chunks


def _validate_channel_guild(channel_id: str) -> Optional[str]:
    """Validate that a channel belongs to the giobi.com server.

    Returns None if valid, error message if not.
    """
    try:
        r = requests.get(
            f"{API_BASE}/channels/{channel_id}",
            headers=_headers()
        )
        if r.status_code != 200:
            return f"Channel {channel_id} not found or not accessible"

        channel_data = r.json()
        channel_guild = channel_data.get('guild_id')

        # DM channels have no guild_id - block them
        if not channel_guild:
            return f"Channel {channel_id} is a DM channel - DMs are disabled"

        if channel_guild != GUILD_ID:
            return f"Channel {channel_id} belongs to guild {channel_guild}, not giobi.com ({GUILD_ID})"

        return None  # Valid
    except Exception as e:
        return f"Failed to validate channel {channel_id}: {e}"


# Cache validated channels to avoid repeated API calls
_validated_channels: set = set()

# Deduplication: prevent sending same message twice within DEDUP_WINDOW_SECONDS
import hashlib
from datetime import datetime, timedelta

DEDUP_WINDOW_SECONDS = 600  # 10 minutes
_sent_messages: Dict[str, datetime] = {}  # hash -> timestamp


def _dedup_check(channel_id: str, content: str) -> Optional[str]:
    """Check if this message was already sent recently.

    Returns None if OK to send, error message if duplicate.
    """
    # Clean old entries
    now = datetime.now()
    cutoff = now - timedelta(seconds=DEDUP_WINDOW_SECONDS)
    expired = [k for k, v in _sent_messages.items() if v < cutoff]
    for k in expired:
        del _sent_messages[k]

    # Hash channel + content (normalize whitespace)
    normalized = ' '.join(content.split()).strip()
    key = hashlib.md5(f"{channel_id}:{normalized}".encode()).hexdigest()

    if key in _sent_messages:
        age = (now - _sent_messages[key]).seconds
        return f"Duplicate message blocked (same content sent {age}s ago to same channel)"

    _sent_messages[key] = now
    return None


def send_to_channel(channel_id: str, message: str = "", embed: Optional[dict] = None, embeds: Optional[List[dict]] = None) -> dict:
    """Send a message to a specific channel. Supports text, single embed, or multiple embeds.

    Long messages (>2000 chars) are automatically split into multiple messages.
    SECURITY: Only channels in the giobi.com server (GUILD_ID) are allowed.
    """
    # Validate channel belongs to giobi.com server
    if channel_id not in _validated_channels:
        error = _validate_channel_guild(channel_id)
        if error:
            return {"error": f"BLOCKED: {error}"}
        _validated_channels.add(channel_id)

    # Deduplication check (prevent double responses)
    dedup_content = message or ""
    if embed:
        dedup_content += str(embed.get('description', ''))
    if embeds:
        dedup_content += ''.join(e.get('description', '') for e in embeds)
    if dedup_content:
        dedup_error = _dedup_check(channel_id, dedup_content)
        if dedup_error:
            return {"error": f"DEDUP: {dedup_error}"}

    # Handle message splitting for long text
    if message and len(message) > 2000 and not embeds and not embed:
        chunks = _split_message(message)
        results = []
        for chunk in chunks:
            result = send_to_channel(channel_id, message=chunk)
            results.append(result)
            if "error" in result:
                return {"error": result["error"], "partial_results": results}
        return {"success": True, "chunks_sent": len(chunks), "results": results}

    payload = {}

    if message:
        payload["content"] = message[:2000]  # Safety truncate

    if embeds:
        payload["embeds"] = embeds[:10]  # Discord max 10 embeds
    elif embed:
        payload["embeds"] = [embed]

    if not payload:
        return {"error": "No content to send"}

    r = requests.post(
        f"{API_BASE}/channels/{channel_id}/messages",
        headers=_headers(),
        json=payload
    )

    if r.status_code == 200:
        return {"success": True, "message_id": r.json()['id']}
    return {"error": r.text}


def send_file(channel_id: str, file_path: str, message: str = "") -> dict:
    """Send a file (image, document, etc.) to a specific channel.

    SECURITY: Only channels in the giobi.com server (GUILD_ID) are allowed.

    Args:
        channel_id: Discord channel ID
        file_path: Path to the file to send
        message: Optional message text to accompany the file

    Returns:
        dict with success/error status
    """
    # Validate channel belongs to giobi.com server
    if channel_id not in _validated_channels:
        error = _validate_channel_guild(channel_id)
        if error:
            return {"error": f"BLOCKED: {error}"}
        _validated_channels.add(channel_id)

    import os.path
    import mimetypes

    if not os.path.exists(file_path):
        return {"error": f"File not found: {file_path}"}

    filename = os.path.basename(file_path)
    mime_type = mimetypes.guess_type(file_path)[0] or "application/octet-stream"

    with open(file_path, "rb") as f:
        files = {"file": (filename, f, mime_type)}
        data = {}
        if message:
            data["content"] = message[:2000]

        r = requests.post(
            f"{API_BASE}/channels/{channel_id}/messages",
            headers={"Authorization": f"Bot {BOT_TOKEN}"},  # No Content-Type for multipart
            data=data,
            files=files
        )

    if r.status_code == 200:
        return {"success": True, "message_id": r.json()['id']}
    return {"error": r.text}


def send_files(channel_id: str, file_paths: List[str], message: str = "") -> dict:
    """Send multiple files to a channel in a single message.

    SECURITY: Only channels in the giobi.com server (GUILD_ID) are allowed.

    Args:
        channel_id: Discord channel ID
        file_paths: List of file paths to send
        message: Optional message text to accompany the files

    Returns:
        dict with success/error status
    """
    # Validate channel belongs to giobi.com server
    if channel_id not in _validated_channels:
        error = _validate_channel_guild(channel_id)
        if error:
            return {"error": f"BLOCKED: {error}"}
        _validated_channels.add(channel_id)

    import os.path
    import mimetypes

    # Validate all files exist
    for fp in file_paths:
        if not os.path.exists(fp):
            return {"error": f"File not found: {fp}"}

    # Open all files and prepare multipart data
    files_data = []
    file_handles = []

    try:
        for idx, fp in enumerate(file_paths):
            filename = os.path.basename(fp)
            mime_type = mimetypes.guess_type(fp)[0] or "application/octet-stream"
            fh = open(fp, "rb")
            file_handles.append(fh)
            files_data.append((f"file{idx}", (filename, fh, mime_type)))

        data = {}
        if message:
            data["content"] = message[:2000]

        r = requests.post(
            f"{API_BASE}/channels/{channel_id}/messages",
            headers={"Authorization": f"Bot {BOT_TOKEN}"},
            data=data,
            files=files_data
        )

        if r.status_code == 200:
            return {"success": True, "message_id": r.json()['id']}
        return {"error": r.text}

    finally:
        # Close all file handles
        for fh in file_handles:
            fh.close()


def send_to_project(project: str, message: str) -> dict:
    """Send a message to a project channel (reads channel from frontmatter)"""
    channel_name = get_project_channel(project)

    if not channel_name:
        return {"error": f"Unknown project channel: {project}. Add discord_channel to project frontmatter."}

    # Get channel ID from Discord API (by name)
    channel = get_channel_by_name(channel_name)
    if not channel:
        return {"error": f"Discord channel not found: {channel_name}"}

    return send_to_channel(channel['id'], message)


def read_messages(channel_id: str, limit: int = 50) -> List[dict]:
    """Read messages from a channel.

    SECURITY: Only channels in the giobi.com server (GUILD_ID) are allowed.
    """
    # Validate channel belongs to giobi.com server
    if channel_id not in _validated_channels:
        error = _validate_channel_guild(channel_id)
        if error:
            return []
        _validated_channels.add(channel_id)

    r = requests.get(
        f"{API_BASE}/channels/{channel_id}/messages?limit={limit}",
        headers=_headers()
    )

    if r.status_code == 200:
        return r.json()
    return []


def read_project_messages(project: str, limit: int = 50) -> List[dict]:
    """Read messages from a project channel (reads channel from frontmatter)"""
    channel_name = get_project_channel(project)

    if not channel_name:
        return []

    channel = get_channel_by_name(channel_name)
    if not channel:
        return []

    return read_messages(channel['id'], limit)


def create_channel(name: str, category_id: Optional[str] = None, topic: str = "") -> dict:
    """Create a new text channel"""
    payload = {
        "name": name,
        "type": 0,  # text channel
        "topic": topic
    }
    if category_id:
        payload["parent_id"] = category_id

    r = requests.post(
        f"{API_BASE}/guilds/{GUILD_ID}/channels",
        headers=_headers(),
        json=payload
    )

    if r.status_code in [200, 201]:
        return {"success": True, "channel": r.json()}
    return {"error": r.text}


def delete_channel(channel_id: str) -> dict:
    """Delete a channel"""
    r = requests.delete(
        f"{API_BASE}/channels/{channel_id}",
        headers=_headers()
    )

    if r.status_code == 200:
        return {"success": True}
    return {"error": r.text}


def list_channels() -> List[dict]:
    """List all channels in the server"""
    r = requests.get(
        f"{API_BASE}/guilds/{GUILD_ID}/channels",
        headers=_headers()
    )

    if r.status_code == 200:
        return r.json()
    return []


def send_webhook(webhook_url: str, message: str = "", embeds: Optional[List[dict]] = None,
                 username: str = "Anacleto 🦉", avatar_url: str = None) -> dict:
    """Send message via Discord webhook (posts as custom user)"""
    payload = {}

    if message:
        payload["content"] = message
    if embeds:
        payload["embeds"] = embeds[:10]
    if username:
        payload["username"] = username
    if avatar_url:
        payload["avatar_url"] = avatar_url

    if not payload:
        return {"error": "No content"}

    r = requests.post(webhook_url, json=payload)

    if r.status_code in [200, 204]:
        return {"success": True}
    return {"error": r.text}


def send_to_project_webhook(project: str, message: str = "", embeds: Optional[List[dict]] = None) -> dict:
    """Send message to project channel via webhook"""
    channel_name = project.lower().replace('.', '-').replace('_', '-')

    if channel_name not in PROJECT_WEBHOOKS:
        return {"error": f"No webhook for project: {project}"}

    return send_webhook(PROJECT_WEBHOOKS[channel_name], message, embeds)


def get_channel_by_name(name: str) -> Optional[dict]:
    """Find a channel by name (handles emoji prefixes like '🎛️︱nexum-estendo-it')"""
    channels = list_channels()
    name_lower = name.lower().replace('.', '-')

    for ch in channels:
        ch_name = ch['name'].lower()
        # Exact match
        if ch_name == name_lower:
            return ch
        # Match after emoji separator (︱)
        if '︱' in ch_name:
            clean_name = ch_name.split('︱')[-1]
            if clean_name == name_lower:
                return ch
    return None


def add_reaction(channel_id: str, message_id: str, emoji: str) -> dict:
    """Add a reaction to a message"""
    r = requests.put(
        f"{API_BASE}/channels/{channel_id}/messages/{message_id}/reactions/{emoji}/@me",
        headers=_headers()
    )

    if r.status_code == 204:
        return {"success": True}
    return {"error": r.text}


def pin_message(channel_id: str, message_id: str) -> dict:
    """Pin a message in a channel"""
    r = requests.put(
        f"{API_BASE}/channels/{channel_id}/pins/{message_id}",
        headers=_headers()
    )

    if r.status_code == 204:
        return {"success": True}
    return {"error": r.text}


# Quick helpers
def dm(message: str) -> dict:
    """DISABLED - DM are not allowed. Redirects to #anacleto channel."""
    return send_to_channel(MAIN_DISCORD_CHANNEL_ID, message)


def notify_project(project: str, message: str) -> dict:
    """Notify about something in a project channel"""
    return send_to_project(project, f"📢 {message}")


# === NEW LOGGING SYSTEM ===

"""
Discord Markdown Reference:
---------------------------
**bold**                    Bold text
*italic* or _italic_        Italic text
__underline__               Underlined text
~~strikethrough~~           Strikethrough
||spoiler||                 Spoiler tag
`inline code`               Inline code
```code block```            Multi-line code block
```python                   Syntax highlighted block
code here
```
> quote                     Block quote
# Header                    Large header
## Header                   Medium header
### Header                  Small header
-# subtext                  Subtext (small gray)
[text](url)                 Masked link

Color tricks (in code blocks):
```diff
- red text (with minus)
+ green text (with plus)
```
```ini
[blue text in brackets]
```
```fix
yellow/orange text
```
"""


def notify(level: str, message: str, source: str, embed: Optional[dict] = None) -> dict:
    """
    Main logging function with process signature.

    Args:
        level: error, warning, info (or aliases)
        message: The message to send (use Discord Markdown!)
        source: Script/process name (e.g., "emergency-check.py", "anacleto-autoresponder")
        embed: Optional Discord embed

    Returns:
        dict with success status

    Discord Markdown tips:
        **bold**, *italic*, __underline__, ~~strike~~
        `code`, ```code block```, > quote
        # Header, ## Subheader, ### Small header
        -# subtext (small gray text)

    Usage:
        from discord import notify
        notify("info", "Task completed", "daily-digest.py")
        notify("error", "**Database** connection failed!", "worker.py")
    """
    from datetime import datetime

    level = level.lower()

    # ALL notifications go to #anacleto (unified channel)
    # Keep emoji prefix for visual level indication
    if level in ("critical", "crit", "error", "err", "emergency", "alert"):
        prefix = "🔴"
    elif level in ("warn", "warning"):
        prefix = "🟡"
    else:  # info, notice, debug, informational
        prefix = "🟢"

    # Format message with prefix and signature (compact)
    timestamp = datetime.now().strftime("%H:%M")
    signed_message = f"{prefix} `{source}` • {timestamp}\n{message}"

    return send_to_channel(MAIN_DISCORD_CHANNEL_ID, signed_message, embed)


# Convenience wrappers (legacy, prefer notify() for new code)
def log_error(message: str, source: str = "unknown", embed: Optional[dict] = None) -> dict:
    """Log error to 🔴︱error channel"""
    return notify("error", message, source, embed)


def log_warning(message: str, source: str = "unknown", embed: Optional[dict] = None) -> dict:
    """Log warning to 🟡︱warning channel"""
    return notify("warning", message, source, embed)


def log_info(message: str, source: str = "unknown", embed: Optional[dict] = None) -> dict:
    """Log info to 🟢︱info channel"""
    return notify("info", message, source, embed)


def log(level: str, message: str, source: str = "unknown", embed: Optional[dict] = None) -> dict:
    """Generic logging function (alias for notify)"""
    return notify(level, message, source, embed)


def send_to_inbox(message: str = "", embed: Optional[dict] = None) -> dict:
    """Send to inbox channel for processing"""
    return send_to_channel(INBOX_CHANNEL_ID, message, embed)


# ============================================
# FORMATTING HELPERS
# ============================================

def html_to_markdown(text: str) -> str:
    """Convert HTML formatting to Discord Markdown"""
    # Bold: <b>text</b> → **text**
    text = re.sub(r'<b>(.*?)</b>', r'**\1**', text, flags=re.DOTALL)
    text = re.sub(r'<strong>(.*?)</strong>', r'**\1**', text, flags=re.DOTALL)

    # Italic: <i>text</i> → *text*
    text = re.sub(r'<i>(.*?)</i>', r'*\1*', text, flags=re.DOTALL)
    text = re.sub(r'<em>(.*?)</em>', r'*\1*', text, flags=re.DOTALL)

    # Code: <code>text</code> → `text`
    text = re.sub(r'<code>(.*?)</code>', r'`\1`', text, flags=re.DOTALL)

    # Links: <a href="url">text</a> → [text](url)
    text = re.sub(r'<a href=["\']([^"\']+)["\']>(.*?)</a>', r'[\2](\1)', text, flags=re.DOTALL)

    # Line breaks
    text = re.sub(r'<br\s*/?>', '\n', text)

    # Remove any remaining HTML tags
    text = re.sub(r'<[^>]+>', '', text)

    return text


def message_to_embeds(message: str) -> list:
    """
    Convert a message with sections into Discord embeds.
    Splits on headers (bold text on its own line).
    Returns list of embed dicts.
    """
    from datetime import datetime

    # Convert HTML to markdown first
    text = html_to_markdown(message)

    # Color mapping based on keywords in title
    def get_color(title: str) -> int:
        title_lower = title.lower()
        if "🔴" in title or "urgenz" in title_lower or "critic" in title_lower:
            return 0xFF0000  # Red
        if "📧" in title or "mail" in title_lower or "email" in title_lower:
            return 0x4285F4  # Blue
        if "📅" in title or "calendar" in title_lower or "event" in title_lower:
            return 0x34A853  # Green
        if "💡" in title or "riflession" in title_lower or "insight" in title_lower:
            return 0xFBBC04  # Yellow
        if "✅" in title or "azioni" in title_lower or "complet" in title_lower:
            return 0x00FF00  # Bright green
        if "📖" in title or "memoria" in title_lower or "storico" in title_lower:
            return 0xE67E22  # Orange
        if "🎙️" in title or "meeting" in title_lower:
            return 0x1ABC9C  # Teal
        if "top" in title_lower:
            return 0x4285F4  # Blue for TOP MAIL
        return 0x9B59B6  # Purple default

    # Split on bold headers: **SOMETHING:** or **SOMETHING**
    # Match lines that are primarily a bold header
    lines = text.split('\n')
    embeds = []
    current_title = None
    current_content = []

    for line in lines:
        # Check if line is a section header (starts with emoji and/or bold text)
        header_match = re.match(r'^((?:[🔴📧📅💡✅📊📖🎙️⚡🔍]\s*)?\*\*[^*]+\*\*:?)\s*$', line.strip())

        if header_match or re.match(r'^\*\*[A-Z][^*]+\*\*:?\s*$', line.strip()):
            # Save previous section
            if current_title and current_content:
                embeds.append({
                    "title": current_title.replace("**", "").strip().rstrip(':'),
                    "description": "\n".join(current_content).strip()[:4096],
                    "color": get_color(current_title),
                })
            # Start new section
            current_title = line.strip()
            current_content = []
        elif line.strip():
            current_content.append(line)

    # Don't forget last section
    if current_title and current_content:
        embeds.append({
            "title": current_title.replace("**", "").strip().rstrip(':'),
            "description": "\n".join(current_content).strip()[:4096],
            "color": get_color(current_title),
        })

    # If no sections found, create single embed
    if not embeds:
        embeds = [{
            "title": "📊 Notification",
            "description": text[:4096],
            "color": 0x9B59B6,
        }]

    # Add timestamp to last embed
    if embeds:
        embeds[-1]["timestamp"] = datetime.utcnow().isoformat()

    return embeds


# ============================================
# CONVENIENCE FUNCTIONS - 3-tier log system
# ============================================

def error(message: str) -> dict:
    """
    🔴 ERROR - Send to error log channel

    Use for: production down, security issues, data loss, system failures
    """
    embeds = message_to_embeds(f"🔴 {message}")
    return send_to_channel(LOG_CHANNELS["error"], embeds=embeds)


def warning(message: str) -> dict:
    """
    🟡 WARNING - Send to warning log channel

    Use for: anomalies, potential issues, items needing review
    """
    embeds = message_to_embeds(f"🟡 {message}")
    return send_to_channel(LOG_CHANNELS["warning"], embeds=embeds)


def info(message: str) -> dict:
    """
    🟢 INFO - Send to info log channel

    Use for: completed tasks, daily summaries, non-urgent info
    """
    embeds = message_to_embeds(f"🟢 {message}")
    return send_to_channel(LOG_CHANNELS["info"], embeds=embeds)


def discord_main(message: str) -> dict:
    """
    Send message to main Discord channel (default channel for proactive notifications).

    Use for: digests, autonomous updates, morning reports, proactive notifications.
    """
    embeds = message_to_embeds(message)
    return send_to_channel(MAIN_DISCORD_CHANNEL_ID, embeds=embeds)


if __name__ == "__main__":
    # Test - sends to #anacleto channel (NOT DM)
    result = send_to_channel(MAIN_DISCORD_CHANNEL_ID, "🦉 Discord library test!")
    print(result)
