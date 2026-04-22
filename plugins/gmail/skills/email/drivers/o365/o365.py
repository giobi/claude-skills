#!/usr/bin/env python3
"""
Microsoft O365/Outlook API Library

Provides reusable functions for Microsoft 365 email operations via Microsoft Graph API.
Used by agents and cron jobs for Outlook/Exchange email access.

Supports multi-tenant pattern: auto-detect .env or explicit env_file parameter.
"""

import os
import requests
import base64
from pathlib import Path
from typing import Optional, Dict, List
from datetime import datetime, timedelta


def find_env_file(start_path: Optional[str] = None) -> Optional[Path]:
    """
    Search for .env file starting from start_path and moving up to parent directories.

    Args:
        start_path: Starting directory (defaults to cwd)

    Returns:
        Path to .env file or None if not found
    """
    current = Path(start_path or os.getcwd()).resolve()

    # Search up to 5 levels
    for _ in range(5):
        env_file = current / '.env'
        if env_file.exists():
            return env_file

        if current.parent == current:  # Reached root
            break
        current = current.parent

    # Fallback to brain root
    brain_env = Path('/home/claude/brain/.env')
    if brain_env.exists():
        return brain_env

    return None


def _get_env(key: str, env_file: Optional[Path] = None) -> Optional[str]:
    """
    Get environment variable from .env file or os.environ.

    Args:
        key: Environment variable name
        env_file: Path to .env file (auto-detected if None)

    Returns:
        Value from .env file or os.environ, or None if not found
    """
    if not env_file:
        env_file = find_env_file()

    if env_file and env_file.exists():
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    k, v = line.split('=', 1)
                    if k.strip() == key:
                        return v.strip().strip('"').strip("'")

    return os.getenv(key)


def _refresh_access_token(env_file: Optional[Path] = None) -> Optional[str]:
    """
    Refresh the Microsoft access token using the refresh token.

    Args:
        env_file: Path to .env file (auto-detected if None)

    Returns:
        New access token or None if refresh failed
    """
    tenant_id = _get_env('O365_TENANT_ID', env_file) or 'common'
    client_id = _get_env('O365_CLIENT_ID', env_file)
    client_secret = _get_env('O365_CLIENT_SECRET', env_file)
    refresh_token = _get_env('O365_REFRESH_TOKEN', env_file)

    if not all([client_id, refresh_token]):
        print("❌ Missing O365 OAuth credentials (O365_CLIENT_ID, O365_REFRESH_TOKEN)")
        return None

    token_url = f'https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token'

    data = {
        'client_id': client_id,
        'refresh_token': refresh_token,
        'grant_type': 'refresh_token',
        'scope': 'https://graph.microsoft.com/.default offline_access'
    }

    if client_secret:
        data['client_secret'] = client_secret

    response = requests.post(token_url, data=data)

    if response.status_code != 200:
        print(f"❌ Token refresh failed: {response.status_code}")
        print(response.text)
        return None

    token_data = response.json()
    new_access_token = token_data.get('access_token')

    # Update .env file with new tokens if available
    if new_access_token and env_file:
        _update_env_token(env_file, 'O365_ACCESS_TOKEN', new_access_token)

        new_refresh_token = token_data.get('refresh_token')
        if new_refresh_token:
            _update_env_token(env_file, 'O365_REFRESH_TOKEN', new_refresh_token)

    return new_access_token


def _update_env_token(env_file: Path, key: str, value: str):
    """Update or add a token in .env file."""
    if not env_file.exists():
        return

    lines = []
    found = False

    with open(env_file, 'r') as f:
        for line in f:
            if line.strip().startswith(f'{key}='):
                lines.append(f'{key}={value}\n')
                found = True
            else:
                lines.append(line)

    if not found:
        lines.append(f'\n{key}={value}\n')

    with open(env_file, 'w') as f:
        f.writelines(lines)


def _get_access_token(env_file: Optional[Path] = None) -> Optional[str]:
    """
    Get valid Microsoft access token (refresh if needed).

    Args:
        env_file: Path to .env file (auto-detected if None)

    Returns:
        Valid access token or None if unavailable
    """
    access_token = _get_env('O365_ACCESS_TOKEN', env_file)

    if not access_token:
        # Try refresh
        access_token = _refresh_access_token(env_file)

    return access_token


def get_messages(
    max_results: int = 10,
    folder: str = 'inbox',
    unread_only: bool = False,
    env_file: Optional[str] = None
) -> List[Dict]:
    """
    Retrieve messages from Microsoft 365/Outlook mailbox.

    Args:
        max_results: Maximum number of messages to retrieve
        folder: Folder name ('inbox', 'sentitems', 'drafts', etc.)
        unread_only: If True, only return unread messages
        env_file: Path to .env file (auto-detected if None)

    Returns:
        List of message dictionaries
    """
    env_path = Path(env_file) if env_file else find_env_file()
    access_token = _get_access_token(env_path)

    if not access_token:
        return []

    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }

    # Build API URL
    url = 'https://graph.microsoft.com/v1.0/me/mailFolders'

    if folder.lower() == 'inbox':
        url = f'https://graph.microsoft.com/v1.0/me/messages'
    else:
        url = f'{url}/{folder}/messages'

    params = {
        '$top': max_results,
        '$orderby': 'receivedDateTime DESC',
        '$orderby': 'receivedDateTime DESC'
    }

    if unread_only:
        params['$filter'] = 'isRead eq false'

    response = requests.get(url, headers=headers, params=params)

    if response.status_code == 401:
        # Token expired, refresh and retry
        access_token = _refresh_access_token(env_path)
        if access_token:
            headers['Authorization'] = f'Bearer {access_token}'
            response = requests.get(url, headers=headers, params=params)

    if response.status_code != 200:
        print(f"❌ Failed to get messages: {response.status_code}")
        print(response.text)
        return []

    messages = response.json().get('value', [])

    # Format messages
    formatted = []
    for msg in messages:
        formatted.append({
            'id': msg.get('id'),
            'subject': msg.get('subject', '(No subject)'),
            'from': msg.get('from', {}).get('emailAddress', {}).get('address', 'Unknown'),
            'from_name': msg.get('from', {}).get('emailAddress', {}).get('name', ''),
            'to': [r.get('emailAddress', {}).get('address') for r in msg.get('toRecipients', [])],
            'date': msg.get('receivedDateTime'),
            'is_read': msg.get('isRead', False),
            'preview': msg.get('bodyPreview', ''),
            'body': msg.get('body', {}).get('content', '')
        })

    return formatted


def send_message(
    to: str,
    subject: str,
    body: str,
    cc: Optional[str] = None,
    body_type: str = 'HTML',
    env_file: Optional[str] = None
) -> bool:
    """
    Send email via Microsoft 365/Outlook.

    Args:
        to: Recipient email address
        subject: Email subject
        body: Email body (HTML or text)
        cc: CC recipient(s) (comma-separated)
        body_type: 'HTML' or 'Text'
        env_file: Path to .env file (auto-detected if None)

    Returns:
        True if sent successfully, False otherwise
    """
    env_path = Path(env_file) if env_file else find_env_file()
    access_token = _get_access_token(env_path)

    if not access_token:
        print("❌ No valid O365 access token")
        return False

    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }

    # Build recipients
    to_recipients = [{'emailAddress': {'address': addr.strip()}} for addr in to.split(',')]

    cc_recipients = []
    if cc:
        cc_recipients = [{'emailAddress': {'address': addr.strip()}} for addr in cc.split(',')]

    # Build message
    message = {
        'message': {
            'subject': subject,
            'body': {
                'contentType': body_type,
                'content': body
            },
            'toRecipients': to_recipients
        }
    }

    if cc_recipients:
        message['message']['ccRecipients'] = cc_recipients

    # Send
    url = 'https://graph.microsoft.com/v1.0/me/sendMail'
    response = requests.post(url, headers=headers, json=message)

    if response.status_code == 401:
        # Token expired, refresh and retry
        access_token = _refresh_access_token(env_path)
        if access_token:
            headers['Authorization'] = f'Bearer {access_token}'
            response = requests.post(url, headers=headers, json=message)

    if response.status_code not in [200, 202]:
        print(f"❌ Failed to send message: {response.status_code}")
        print(response.text)
        return False

    return True


def search_messages(
    query: str,
    max_results: int = 20,
    env_file: Optional[str] = None
) -> List[Dict]:
    """
    Search messages in mailbox.

    Args:
        query: Search query (searches subject, body, from, to)
        max_results: Maximum number of results
        env_file: Path to .env file (auto-detected if None)

    Returns:
        List of matching messages
    """
    env_path = Path(env_file) if env_file else find_env_file()
    access_token = _get_access_token(env_path)

    if not access_token:
        return []

    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }

    url = 'https://graph.microsoft.com/v1.0/me/messages'
    params = {
        '$search': f'"{query}"',
        '$top': max_results,
        '$orderby': 'receivedDateTime DESC'
    }

    response = requests.get(url, headers=headers, params=params)

    if response.status_code == 401:
        access_token = _refresh_access_token(env_path)
        if access_token:
            headers['Authorization'] = f'Bearer {access_token}'
            response = requests.get(url, headers=headers, params=params)

    if response.status_code != 200:
        print(f"❌ Search failed: {response.status_code}")
        return []

    messages = response.json().get('value', [])

    # Format messages
    formatted = []
    for msg in messages:
        formatted.append({
            'id': msg.get('id'),
            'subject': msg.get('subject', '(No subject)'),
            'from': msg.get('from', {}).get('emailAddress', {}).get('address', 'Unknown'),
            'date': msg.get('receivedDateTime'),
            'preview': msg.get('bodyPreview', '')
        })

    return formatted


# Convenience aliases
get_recent = get_messages
search = search_messages


if __name__ == '__main__':
    # Test
    print("Testing O365 wrapper...")
    messages = get_messages(max_results=5)
    print(f"Found {len(messages)} messages")

    for msg in messages[:3]:
        print(f"- {msg['subject']} (from: {msg['from']})")
