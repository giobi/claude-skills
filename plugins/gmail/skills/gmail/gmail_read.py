#!/usr/bin/env python3
"""
Gmail API Library - READ Operations

Provides read-only functions for Gmail operations.
Used by agents and commands for fetching emails, threads, drafts.
"""

import os
import requests
import base64
from pathlib import Path
from typing import Optional, Dict, List


def _get_env(key: str, prefer_file: bool = True) -> Optional[str]:
    """
    Get environment variable from .env or os.environ

    Args:
        key: Environment variable name
        prefer_file: If True, .env file takes precedence over os.environ
                     This prevents stale environment variables from shadowing fresh tokens

    Returns:
        Value from .env file or os.environ, or None if not found
    """
    env_file = Path(__file__).parent.parent.parent / '.env'
    file_value = None

    # Read from .env file
    if env_file.exists():
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    k, v = line.split('=', 1)
                    if k.strip() == key:
                        file_value = v.strip().strip('"').strip("'")
                        break

    # Get from os.environ
    env_value = os.getenv(key)

    # Return based on preference
    if prefer_file and file_value:
        return file_value
    return env_value or file_value


def _refresh_access_token() -> Optional[str]:
    """
    Refresh the Gmail access token using the refresh token.
    Updates .env file with new access token.

    Returns:
        New access token or None if refresh failed
    """
    client_id = _get_env('GMAIL_CLIENT_ID')
    client_secret = _get_env('GMAIL_CLIENT_SECRET')
    refresh_token = _get_env('GMAIL_REFRESH_TOKEN')

    if not all([client_id, client_secret, refresh_token]):
        print("❌ Missing OAuth credentials for token refresh")
        return None

    response = requests.post(
        'https://oauth2.googleapis.com/token',
        data={
            'client_id': client_id,
            'client_secret': client_secret,
            'refresh_token': refresh_token,
            'grant_type': 'refresh_token'
        }
    )

    if response.status_code != 200:
        print(f"❌ Token refresh failed: {response.status_code} - {response.text}")
        return None

    new_token = response.json().get('access_token')
    if not new_token:
        print("❌ No access_token in refresh response")
        return None

    # Update .env file
    env_file = Path(__file__).parent.parent.parent / '.env'
    if env_file.exists():
        content = env_file.read_text()
        import re
        new_content = re.sub(
            r'GMAIL_ACCESS_TOKEN=.*',
            f'GMAIL_ACCESS_TOKEN={new_token}',
            content
        )
        env_file.write_text(new_content)

    return new_token


def _get_headers(retry_on_401: bool = True) -> Dict[str, str]:
    """Get Gmail API headers with access token, auto-refreshing if needed"""
    access_token = _get_env('GMAIL_ACCESS_TOKEN')
    if not access_token:
        # Try to refresh
        access_token = _refresh_access_token()
        if not access_token:
            raise ValueError("GMAIL_ACCESS_TOKEN not found and refresh failed")

    return {'Authorization': f'Bearer {access_token}'}


def _make_request(method: str, url: str, headers: Dict = None, **kwargs) -> requests.Response:
    """Make API request with automatic token refresh on 401"""
    if headers is None:
        headers = _get_headers()

    response = requests.request(method, url, headers=headers, **kwargs)

    # If 401, refresh token and retry once
    if response.status_code == 401:
        new_token = _refresh_access_token()
        if new_token:
            headers = {'Authorization': f'Bearer {new_token}'}
            response = requests.request(method, url, headers=headers, **kwargs)

    return response


def search_messages(query: str, max_results: int = 10, parse: bool = True) -> List[Dict]:
    """
    Search Gmail messages

    Args:
        query: Gmail search query (e.g., "from:example@gmail.com")
        max_results: Maximum number of results
        parse: If True, fetch and parse full message details. If False, return only id/threadId.

    Returns:
        List of message objects (parsed if parse=True, raw id/threadId if parse=False)
    """
    response = _make_request(
        'GET',
        'https://gmail.googleapis.com/gmail/v1/users/me/messages',
        params={'q': query, 'maxResults': max_results}
    )

    if response.status_code != 200:
        print(f"❌ Gmail API error: {response.status_code} - {response.text}")
        return []

    data = response.json()
    messages = data.get('messages', [])

    if parse and messages:
        # Fetch full details for each message
        parsed_messages = []
        for msg in messages:
            full_msg = get_message(msg['id'], parse=True)
            if full_msg:
                parsed_messages.append(full_msg)
        return parsed_messages
    else:
        return messages


def _parse_message(message: Dict) -> Dict:
    """
    Parse Gmail API message into readable format

    Args:
        message: Raw message from Gmail API

    Returns:
        Dict with from, to, subject, date, body, id, threadId, labelIds, payload,
        list_unsubscribe
    """
    # Extract headers
    headers_dict = {}
    if 'payload' in message and 'headers' in message['payload']:
        for header in message['payload']['headers']:
            headers_dict[header['name'].lower()] = header['value']

    # Extract body
    body = _extract_body(message) if 'payload' in message else ''

    return {
        'id': message.get('id'),
        'threadId': message.get('threadId'),
        'from': headers_dict.get('from', ''),
        'to': headers_dict.get('to', ''),
        'subject': headers_dict.get('subject', ''),
        'date': headers_dict.get('date', ''),
        'body': body,
        'labelIds': message.get('labelIds', []),
        'list_unsubscribe': headers_dict.get('list-unsubscribe', ''),
        'payload': message.get('payload', {})  # Keep full payload for advanced use
    }


def get_message(message_id: str, format: str = 'full', parse: bool = True) -> Optional[Dict]:
    """
    Get full message details

    Args:
        message_id: Gmail message ID
        format: Response format (full, metadata, minimal)
        parse: If True, return parsed dict with from/to/subject/body. If False, return raw Gmail API response.

    Returns:
        Message object or None
    """
    response = _make_request(
        'GET',
        f'https://gmail.googleapis.com/gmail/v1/users/me/messages/{message_id}',
        params={'format': format}
    )

    if response.status_code != 200:
        print(f"❌ Error fetching message: {response.status_code}")
        return None

    raw_message = response.json()

    if parse:
        return _parse_message(raw_message)
    else:
        return raw_message


def get_thread_id_from_message(message_id: str) -> Optional[str]:
    """
    Get threadId from a message ID

    Args:
        message_id: Gmail message ID

    Returns:
        Thread ID or None if message not found
    """
    msg = get_message(message_id, format='metadata')
    return msg.get('threadId') if msg else None


def get_thread(thread_id: str) -> Optional[Dict]:
    """
    Get full thread with all messages

    Args:
        thread_id: Gmail thread ID

    Returns:
        Thread object with all messages or None
    """
    response = _make_request(
        'GET',
        f'https://gmail.googleapis.com/gmail/v1/users/me/threads/{thread_id}',
        params={'format': 'full'}
    )

    if response.status_code != 200:
        print(f"❌ Error fetching thread: {response.status_code}")
        return None

    return response.json()


def list_drafts(max_results: int = 50) -> List[Dict]:
    """
    List Gmail drafts with their thread IDs

    Args:
        max_results: Maximum number of drafts to fetch

    Returns:
        List of draft objects with id, threadId, and subject
    """
    response = _make_request(
        'GET',
        'https://gmail.googleapis.com/gmail/v1/users/me/drafts',
        params={'maxResults': max_results}
    )

    if response.status_code != 200:
        print(f"❌ Error listing drafts: {response.status_code}")
        return []

    drafts = response.json().get('drafts', [])
    result = []

    for draft in drafts:
        # Get draft details for threadId
        draft_detail = _make_request(
            'GET',
            f"https://gmail.googleapis.com/gmail/v1/users/me/drafts/{draft['id']}",
            params={'format': 'metadata', 'metadataHeaders': ['Subject']}
        )

        if draft_detail.status_code == 200:
            data = draft_detail.json()
            msg = data.get('message', {})
            thread_id = msg.get('threadId')

            # Extract subject
            subject = ''
            for h in msg.get('payload', {}).get('headers', []):
                if h['name'] == 'Subject':
                    subject = h['value']
                    break

            result.append({
                'id': draft['id'],
                'threadId': thread_id,
                'subject': subject
            })

    return result


def get_draft_by_thread(thread_id: str) -> Optional[Dict]:
    """
    Find existing draft in a specific thread

    Args:
        thread_id: Gmail thread ID

    Returns:
        Draft object if found in thread, None otherwise
    """
    drafts = list_drafts(max_results=50)

    for draft in drafts:
        if draft.get('threadId') == thread_id:
            return draft

    return None


def find_draft_by_recipient(to: str, subject_contains: Optional[str] = None) -> Optional[Dict]:
    """
    Find existing draft by recipient (and optionally subject)

    Args:
        to: Recipient email to match
        subject_contains: Optional substring to match in subject

    Returns:
        First matching draft or None
    """
    drafts = list_drafts(max_results=20)

    for draft in drafts:
        # Get full draft to check recipient
        response = _make_request(
            'GET',
            f"https://gmail.googleapis.com/gmail/v1/users/me/drafts/{draft['id']}",
            params={'format': 'metadata', 'metadataHeaders': ['To', 'Subject']}
        )

        if response.status_code != 200:
            continue

        data = response.json()
        headers = data.get('message', {}).get('payload', {}).get('headers', [])

        draft_to = ''
        draft_subject = ''
        for h in headers:
            if h['name'] == 'To':
                draft_to = h['value'].lower()
            if h['name'] == 'Subject':
                draft_subject = h['value']

        # Match recipient
        if to.lower() in draft_to:
            # If subject filter provided, check it too
            if subject_contains:
                if subject_contains.lower() in draft_subject.lower():
                    return {'id': draft['id'], 'subject': draft_subject, 'to': draft_to}
            else:
                return {'id': draft['id'], 'subject': draft_subject, 'to': draft_to}

    return None


def _extract_body(message: Dict) -> str:
    """Extract body from message (prefers plain text, falls back to HTML)"""
    import re
    payload = message.get('payload', {})

    def find_part(payload: Dict, mime_type: str) -> Optional[str]:
        """Recursively find part by mime type"""
        if payload.get('mimeType') == mime_type:
            data = payload.get('body', {}).get('data', '')
            if data:
                return base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')

        for part in payload.get('parts', []):
            result = find_part(part, mime_type)
            if result:
                return result
        return None

    # Try plain text first
    text = find_part(payload, 'text/plain')
    if text:
        return text

    # Fall back to HTML, strip tags
    html = find_part(payload, 'text/html')
    if html:
        # Basic HTML to text conversion
        text = re.sub(r'<br\s*/?>', '\n', html, flags=re.IGNORECASE)
        text = re.sub(r'<p[^>]*>', '\n', text, flags=re.IGNORECASE)
        text = re.sub(r'</p>', '\n', text, flags=re.IGNORECASE)
        text = re.sub(r'<[^>]+>', '', text)
        text = re.sub(r'&nbsp;', ' ', text)
        text = re.sub(r'&amp;', '&', text)
        text = re.sub(r'&lt;', '<', text)
        text = re.sub(r'&gt;', '>', text)
        text = re.sub(r'&#\d+;', '', text)
        text = re.sub(r'\n\s*\n', '\n\n', text)
        return text.strip()

    # Last resort: direct body
    if 'body' in payload and payload['body'].get('data'):
        return base64.urlsafe_b64decode(payload['body']['data']).decode('utf-8', errors='ignore')

    return ''


def _format_message(message: Dict, show_body: bool = False) -> str:
    """Format message for display"""
    headers = {h['name']: h['value'] for h in message['payload']['headers']}
    lines = [
        f"From: {headers.get('From', 'N/A')}",
        f"To: {headers.get('To', 'N/A')}",
        f"Subject: {headers.get('Subject', 'N/A')}",
        f"Date: {headers.get('Date', 'N/A')}",
        f"ID: {message['id']}",
        f"Thread: {message.get('threadId', 'N/A')}"
    ]

    if show_body:
        body = _extract_body(message)
        if body:
            lines.append(f"\n--- Body ---\n{body}")

    return '\n'.join(lines)


def search_all_messages(query: str, parse: bool = True, page_size: int = 100) -> List[Dict]:
    """
    Search Gmail messages with full pagination (fetches ALL results).

    Args:
        query: Gmail search query
        parse: If True, fetch and parse full message details
        page_size: Results per page (max 500)

    Returns:
        Complete list of matching messages
    """
    all_messages = []
    page_token = None

    while True:
        params = {'q': query, 'maxResults': min(page_size, 500)}
        if page_token:
            params['pageToken'] = page_token

        response = _make_request(
            'GET',
            'https://gmail.googleapis.com/gmail/v1/users/me/messages',
            params=params
        )

        if response.status_code != 200:
            print(f"❌ Gmail API error: {response.status_code} - {response.text}")
            break

        data = response.json()
        messages = data.get('messages', [])
        all_messages.extend(messages)

        page_token = data.get('nextPageToken')
        if not page_token:
            break

    if parse and all_messages:
        parsed = []
        for msg in all_messages:
            full_msg = get_message(msg['id'], parse=True)
            if full_msg:
                parsed.append(full_msg)
        return parsed

    return all_messages


def list_attachments(message_id: str) -> List[Dict]:
    """
    List all attachments in a message.

    Args:
        message_id: Gmail message ID

    Returns:
        List of dicts with filename, mimeType, size, attachmentId
    """
    msg = get_message(message_id, parse=True)
    if not msg:
        return []

    attachments = []
    payload = msg.get('payload', {})

    def _scan_parts(parts):
        for part in parts:
            fn = part.get('filename', '')
            if fn:
                attachments.append({
                    'filename': fn,
                    'mimeType': part.get('mimeType', ''),
                    'size': part.get('body', {}).get('size', 0),
                    'attachmentId': part.get('body', {}).get('attachmentId', ''),
                })
            _scan_parts(part.get('parts', []))

    _scan_parts(payload.get('parts', []))
    return attachments


def download_attachment(message_id: str, attachment_id: str) -> Optional[bytes]:
    """
    Download an attachment by its ID.

    Args:
        message_id: Gmail message ID
        attachment_id: Attachment ID from list_attachments()

    Returns:
        Raw bytes of the attachment, or None on error
    """
    response = _make_request(
        'GET',
        f'https://gmail.googleapis.com/gmail/v1/users/me/messages/{message_id}/attachments/{attachment_id}'
    )

    if response.status_code != 200:
        print(f"❌ Error downloading attachment: {response.status_code}")
        return None

    data = response.json().get('data', '')
    if not data:
        return None

    return base64.urlsafe_b64decode(data)


def download_attachments(message_id: str, dest_dir: str, filter_ext: str = None) -> List[str]:
    """
    Download all attachments from a message to a directory.

    Args:
        message_id: Gmail message ID
        dest_dir: Directory to save files to
        filter_ext: Optional extension filter (e.g. '.docx', '.pdf')

    Returns:
        List of saved file paths
    """
    import os
    os.makedirs(dest_dir, exist_ok=True)

    attachments = list_attachments(message_id)
    saved = []

    for att in attachments:
        fn = att['filename']
        att_id = att['attachmentId']

        if not fn or not att_id:
            continue
        if filter_ext and not fn.lower().endswith(filter_ext.lower()):
            continue

        data = download_attachment(message_id, att_id)
        if data:
            filepath = os.path.join(dest_dir, fn)
            with open(filepath, 'wb') as f:
                f.write(data)
            saved.append(filepath)
            print(f"✅ {fn} ({len(data)} bytes)")
        else:
            print(f"❌ {fn}: download failed")

    return saved


def get_unsubscribe_info(message_id: str) -> Optional[Dict]:
    """
    Extract unsubscribe information from an email message.

    Checks List-Unsubscribe and List-Unsubscribe-Post headers.

    Args:
        message_id: Gmail message ID

    Returns:
        Dict with 'url' (http link), 'mailto' (email), 'one_click' (bool)
        or None if no unsubscribe info found
    """
    import re

    raw_msg = get_message(message_id, format='metadata', parse=False)
    if not raw_msg:
        return None

    headers_dict = {}
    for header in raw_msg.get('payload', {}).get('headers', []):
        headers_dict[header['name'].lower()] = header['value']

    unsub = headers_dict.get('list-unsubscribe', '')
    unsub_post = headers_dict.get('list-unsubscribe-post', '')

    if not unsub:
        return None

    result = {
        'url': None,
        'mailto': None,
        'one_click': bool(unsub_post),
        'raw': unsub
    }

    # Extract HTTP URL
    http_match = re.search(r'<(https?://[^>]+)>', unsub)
    if http_match:
        result['url'] = http_match.group(1)

    # Extract mailto
    mailto_match = re.search(r'<mailto:([^>]+)>', unsub)
    if mailto_match:
        result['mailto'] = mailto_match.group(1)

    return result
