"""
Telegram Bot API Wrapper - Webhook Edition

Wrapper for Telegram Bot API with webhook-based message retrieval.

Architecture:
    - Telegram webhooks → telegram.abchat.it → local SQLite database
    - Each workspace has its own bot, filtered by TELEGRAM_BOT_TOKEN
    - Messages are retrieved from local DB (no polling)

Usage:
    from tools.lib.telegram import send_message, get_messages, get_chat_id

    # Send message
    send_message(chat_id="123456", text="Hello")

    # Get unread messages for this bot
    messages = get_messages(unread_only=True)

    # Get chat_id from first message
    chat_info = get_chat_id()
    if chat_info:
        send_message(chat_id=chat_info['chat_id'], text="Hi!")

    # Multi-tenant: explicit .env
    messages = get_messages(env_file="/path/to/.env")

Required .env keys:
    TELEGRAM_BOT_TOKEN=your_bot_token
    TELEGRAM_CHAT_ID=your_chat_id (optional, can be auto-discovered)
"""

import os
import re
import requests
from typing import Optional, Dict, Any, List
from pathlib import Path
from dotenv import load_dotenv


def sanitize_html(text: str) -> str:
    """
    Escape HTML special characters to prevent breaking Telegram HTML formatting.

    Only escapes characters that are not part of valid HTML tags.
    """
    # Don't escape if text is empty
    if not text:
        return text

    # Escape &, <, > that are NOT part of valid HTML tags
    # Preserve valid HTML tags: <b>, <i>, <u>, <s>, <code>, <pre>, <a>
    valid_tags_pattern = r'</?(?:b|strong|i|em|u|ins|s|strike|del|code|pre|a(?:\s+href="[^"]*")?)>'

    # Split text into parts: HTML tags and regular text
    parts = re.split(f'({valid_tags_pattern})', text, flags=re.IGNORECASE)

    sanitized_parts = []
    for part in parts:
        # If it's a valid HTML tag, keep it as-is
        if re.match(valid_tags_pattern, part, re.IGNORECASE):
            sanitized_parts.append(part)
        else:
            # Escape special characters in regular text
            part = part.replace('&', '&amp;')
            part = part.replace('<', '&lt;')
            part = part.replace('>', '&gt;')
            sanitized_parts.append(part)

    return ''.join(sanitized_parts)


def markdown_to_html(text: str) -> str:
    """
    Convert markdown formatting to Telegram HTML.

    Supports:
    - **bold** or __bold__ → <b>bold</b>
    - *italic* or _italic_ → <i>italic</i>
    - `code` → <code>code</code>
    - ```code block``` → <pre>code block</pre>
    - [link](url) → <a href="url">link</a>
    - # Title → <b>Title</b>
    - ## Subtitle → <b>Subtitle</b>

    Args:
        text: Text with markdown formatting

    Returns:
        Text with HTML formatting
    """
    if not text:
        return text

    # Code blocks (must be before inline code)
    text = re.sub(r'```([^`]+)```', r'<pre>\1</pre>', text)

    # Inline code
    text = re.sub(r'`([^`]+)`', r'<code>\1</code>', text)

    # Bold (** or __)
    text = re.sub(r'\*\*([^\*]+)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'__([^_]+)__', r'<b>\1</b>', text)

    # Italic (* or _) - must be after bold
    text = re.sub(r'\*([^\*]+)\*', r'<i>\1</i>', text)
    text = re.sub(r'_([^_]+)_', r'<i>\1</i>', text)

    # Links [text](url)
    text = re.sub(r'\[([^\]]+)\]\(([^\)]+)\)', r'<a href="\2">\1</a>', text)

    # Headers (convert to bold)
    text = re.sub(r'^#+\s+(.+)$', r'<b>\1</b>', text, flags=re.MULTILINE)

    return text


def prepare_telegram_text(text: str, convert_markdown: bool = True) -> str:
    """
    Prepare text for Telegram HTML formatting.

    1. Convert markdown to HTML (if enabled)
    2. Sanitize HTML special characters

    Args:
        text: Input text (markdown or plain)
        convert_markdown: Whether to convert markdown to HTML

    Returns:
        Sanitized HTML-formatted text ready for Telegram
    """
    if not text:
        return text

    # Convert markdown to HTML
    if convert_markdown:
        text = markdown_to_html(text)

    # Sanitize HTML (preserves valid tags, escapes rest)
    text = sanitize_html(text)

    return text


def find_env_file() -> Optional[str]:
    """Find .env file from current directory upwards."""
    current = Path.cwd()
    for parent in [current] + list(current.parents):
        env_path = parent / ".env"
        if env_path.exists():
            return str(env_path)
    return None


def send_message(
    chat_id: str,
    text: str,
    parse_mode: str = "HTML",
    disable_web_page_preview: bool = False,
    convert_markdown: bool = True,
    env_file: Optional[str] = None
) -> Dict[str, Any]:
    """
    Send message via Telegram Bot API.

    Automatically converts markdown to HTML and sanitizes text.

    Args:
        chat_id: Chat ID or username (@channel)
        text: Message text (supports markdown if convert_markdown=True)
        parse_mode: Formatting mode (HTML, Markdown, MarkdownV2)
        disable_web_page_preview: Disable link previews
        convert_markdown: Convert markdown to HTML (default: True)
        env_file: Path to .env file

    Returns:
        API response dict
    """
    if not env_file:
        env_file = find_env_file()

    if env_file:
        load_dotenv(env_file)

    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN not found in environment")

    # Prepare text: markdown → HTML + sanitization
    if parse_mode == "HTML":
        text = prepare_telegram_text(text, convert_markdown=convert_markdown)

    url = f"https://api.telegram.org/bot{token}/sendMessage"

    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": disable_web_page_preview
    }

    response = requests.post(url, json=payload, timeout=30)
    response.raise_for_status()

    return response.json()


def get_me(env_file: Optional[str] = None) -> Dict[str, Any]:
    """
    Get bot info (useful for testing token validity).

    Args:
        env_file: Path to .env file

    Returns:
        Bot info dict
    """
    if not env_file:
        env_file = find_env_file()

    if env_file:
        load_dotenv(env_file)

    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN not found in environment")

    url = f"https://api.telegram.org/bot{token}/getMe"

    response = requests.get(url, timeout=30)
    response.raise_for_status()

    return response.json()


def get_updates(
    offset: Optional[int] = None,
    limit: int = 100,
    timeout: int = 0,
    env_file: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Get incoming updates (messages, commands, etc.).

    DEPRECATED: Use get_messages() instead for webhook-based message retrieval.
    This function now calls get_messages() internally.

    Args:
        offset: Ignored (kept for compatibility)
        limit: Limits the number of updates to be retrieved (1-100)
        timeout: Ignored (kept for compatibility)
        env_file: Path to .env file

    Returns:
        List of update dicts (empty for webhook mode)
    """
    # For backward compatibility, call get_messages
    messages = get_messages(limit=limit, unread_only=False, env_file=env_file)
    return messages


def get_messages(
    limit: int = 50,
    unread_only: bool = True,
    env_file: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Get messages from local webhook database.

    This function retrieves messages that were stored by the webhook server.
    Each workspace only sees messages for their own bot (filtered by TELEGRAM_BOT_TOKEN).

    Args:
        limit: Maximum number of messages to retrieve
        unread_only: If True, only return unread messages
        env_file: Path to .env file

    Returns:
        List of message dicts with keys:
            - id: Message ID (internal)
            - update_id: Telegram update ID
            - chat_id: Chat ID
            - user_id: User ID
            - username: Username (without @)
            - first_name: First name
            - last_name: Last name
            - text: Message text
            - message_type: Type (text, photo, document, etc.)
            - received_at: Timestamp
            - read: Boolean
    """
    if not env_file:
        env_file = find_env_file()

    if env_file:
        load_dotenv(env_file)

    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN not found in environment")

    # Call local webhook API
    url = "http://127.0.0.1:9091/api/messages"

    params = {
        "bot_token": token,
        "limit": limit,
        "unread_only": str(unread_only).lower()
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()

        result = response.json()
        if result.get("ok"):
            return result.get("messages", [])
        else:
            raise Exception(f"API error: {result.get('error', 'Unknown')}")

    except requests.exceptions.RequestException as e:
        # Fallback: if webhook server not available, return empty
        print(f"Warning: Webhook server not available ({e}). Returning empty list.")
        return []


def get_chat_id(env_file: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Get chat ID from most recent message for this bot.

    Useful for discovering the chat_id after a user sends the first message.

    Args:
        env_file: Path to .env file

    Returns:
        Dict with keys: chat_id, username, first_name, last_name
        None if no messages found
    """
    if not env_file:
        env_file = find_env_file()

    if env_file:
        load_dotenv(env_file)

    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN not found in environment")

    url = "http://127.0.0.1:9091/api/chat_id"

    params = {"bot_token": token}

    try:
        response = requests.get(url, params=params, timeout=10)

        if response.status_code == 404:
            return None

        response.raise_for_status()

        result = response.json()
        if result.get("ok"):
            return {
                "chat_id": result.get("chat_id"),
                "username": result.get("username"),
                "first_name": result.get("first_name"),
                "last_name": result.get("last_name")
            }
        else:
            return None

    except requests.exceptions.RequestException as e:
        print(f"Warning: Webhook server not available ({e})")
        return None


def mark_messages_read(
    message_ids: Optional[List[int]] = None,
    env_file: Optional[str] = None
) -> bool:
    """
    Mark messages as read in the webhook database.

    Args:
        message_ids: List of message IDs to mark as read (None = mark all)
        env_file: Path to .env file

    Returns:
        True if successful, False otherwise
    """
    if not env_file:
        env_file = find_env_file()

    if env_file:
        load_dotenv(env_file)

    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN not found in environment")

    url = "http://127.0.0.1:9091/api/mark_read"

    payload = {
        "bot_token": token,
        "message_ids": message_ids or []
    }

    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()

        result = response.json()
        return result.get("ok", False)

    except requests.exceptions.RequestException as e:
        print(f"Warning: Failed to mark messages as read ({e})")
        return False


def is_authorized_user(
    username: Optional[str] = None,
    user_id: Optional[int] = None,
    env_file: Optional[str] = None
) -> bool:
    """
    Check if a Telegram user is authorized to interact with this bot.

    Authorization rules:
    1. @giobicom (username) is ALWAYS authorized (hardcoded superuser)
    2. user_id 791253342 (Giobi) is ALWAYS authorized (hardcoded superuser)
    3. Username matching TELEGRAM_OWNER_USERNAME in .env is authorized
    4. user_id matching TELEGRAM_OWNER_USER_ID in .env is authorized
    5. All others are NOT authorized

    Args:
        username: Telegram username (with or without @)
        user_id: Telegram user_id (numeric)
        env_file: Path to .env file

    Returns:
        True if authorized, False otherwise

    Example:
        msg = get_messages()[0]
        if is_authorized_user(username=msg['username'], user_id=msg['user_id']):
            # Process and respond
        else:
            # Ignore or send unauthorized message
    """
    # Giobi is always authorized (superuser) - by username
    if username:
        username_clean = username.lstrip('@').lower()
        if username_clean == 'giobicom':
            return True

    # Giobi is always authorized (superuser) - by user_id
    if user_id == 791253342:
        return True

    # Check owner from env
    if not env_file:
        env_file = find_env_file()

    if env_file:
        load_dotenv(env_file)

    # Check owner username
    if username:
        owner_username = os.getenv("TELEGRAM_OWNER_USERNAME", "").lstrip('@').lower()
        if owner_username and username.lstrip('@').lower() == owner_username:
            return True

    # Check owner user_id
    if user_id:
        owner_user_id = os.getenv("TELEGRAM_OWNER_USER_ID", "")
        if owner_user_id and str(user_id) == owner_user_id:
            return True

    return False


def send_photo(
    chat_id: str,
    photo_url: str,
    caption: Optional[str] = None,
    parse_mode: str = "HTML",
    convert_markdown: bool = True,
    env_file: Optional[str] = None
) -> Dict[str, Any]:
    """
    Send photo via URL.

    Automatically converts markdown to HTML and sanitizes caption.

    Args:
        chat_id: Chat ID or username
        photo_url: Photo URL
        caption: Photo caption (optional, supports markdown)
        parse_mode: Formatting mode
        convert_markdown: Convert markdown to HTML in caption (default: True)
        env_file: Path to .env file

    Returns:
        API response dict
    """
    if not env_file:
        env_file = find_env_file()

    if env_file:
        load_dotenv(env_file)

    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN not found in environment")

    # Prepare caption: markdown → HTML + sanitization
    if caption and parse_mode == "HTML":
        caption = prepare_telegram_text(caption, convert_markdown=convert_markdown)

    url = f"https://api.telegram.org/bot{token}/sendPhoto"

    payload = {
        "chat_id": chat_id,
        "photo": photo_url,
        "parse_mode": parse_mode
    }

    if caption:
        payload["caption"] = caption

    response = requests.post(url, json=payload, timeout=30)
    response.raise_for_status()

    return response.json()


def set_message_reaction(
    chat_id: str,
    message_id: int,
    emoji: str = '\U0001f440',  # 👀
    env_file: Optional[str] = None
) -> Dict[str, Any]:
    """
    Set a reaction on a Telegram message.

    Args:
        chat_id: Chat ID
        message_id: Message ID to react to
        emoji: Emoji to react with (default: 👀)
        env_file: Path to .env file

    Returns:
        API response dict
    """
    if not env_file:
        env_file = find_env_file()
    if env_file:
        load_dotenv(env_file)

    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN not found in environment")

    url = f"https://api.telegram.org/bot{token}/setMessageReaction"

    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "reaction": [{"type": "emoji", "emoji": emoji}],
    }

    try:
        response = requests.post(url, json=payload, timeout=10)
        return response.json()
    except Exception as e:
        return {"ok": False, "error": str(e)}


if __name__ == "__main__":
    # CLI test
    import sys

    if len(sys.argv) < 3:
        print("Usage: python telegram.py <chat_id> <message>")
        sys.exit(1)

    chat_id = sys.argv[1]
    message = sys.argv[2]

    result = send_message(chat_id, message)
    print(f"✅ Message sent: {result.get('result', {}).get('message_id')}")
