#!/usr/bin/env python3
"""
Auto-responder for a configured email address (AUTORESPONDER_EMAIL)

Checks for unreplied emails received at AUTORESPONDER_EMAIL
Se thread non ha risposta → genera risposta AI e invia

Usage:
    python3 anacleto-autoresponder.py           # Run normally
    python3 anacleto-autoresponder.py --dry-run # Show what would happen
"""
import sys
import argparse
import requests
import base64
import re
import glob
from pathlib import Path
from datetime import datetime, timedelta

BRAIN = Path(__file__).resolve().parent.parent.parent.parent
SKILLS = BRAIN / '.claude' / 'skills'
sys.path.insert(0, str(SKILLS / 'discord'))
sys.path.insert(0, str(SKILLS / 'brain-writer'))

# Load .env and configure
import os
from pathlib import Path as _P
_env = BRAIN / '.env'
if _env.exists():
    for _line in _env.read_text().splitlines():
        if '=' in _line and not _line.startswith('#'):
            _k, _v = _line.split('=', 1)
            os.environ.setdefault(_k.strip(), _v.strip().strip('"').strip("'"))

# Load non-secret config from wiki/skills/autoresponder.yaml (with env fallback)
_cfg = {}
_cfg_file = BRAIN / 'wiki' / 'skills' / 'autoresponder.yaml'
if _cfg_file.exists():
    import yaml as _yaml
    _cfg = _yaml.safe_load(_cfg_file.read_text()) or {}

AUTORESPONDER_EMAIL = _cfg.get('email') or os.getenv('AUTORESPONDER_EMAIL', 'autoresponder@example.com')
AUTORESPONDER_NAME  = _cfg.get('name') or os.getenv('AUTORESPONDER_NAME', 'AI Assistant')
BRAIN_URL           = _cfg.get('brain_url') or os.getenv('BRAIN_URL', 'https://brain.local')
AUTORESPONDER_OWNER_EMAIL = _cfg.get('owner_email') or os.getenv('AUTORESPONDER_OWNER_EMAIL', AUTORESPONDER_EMAIL)

def get_access_token():
    """Load Gmail token"""
    env_file = BRAIN / '.env'
    with open(env_file) as f:
        for line in f:
            if line.strip().startswith('GMAIL_ACCESS_TOKEN='):
                return line.split('=', 1)[1].strip().strip('"').strip("'")
    return None

def get_openrouter_key():
    """Load OpenRouter API key"""
    env_file = BRAIN / '.env'
    with open(env_file) as f:
        for line in f:
            if line.strip().startswith('OPENROUTER_API_KEY='):
                return line.split('=', 1)[1].strip().strip('"').strip("'")
    return None

def extract_email_address(from_header):
    """Extract email address from From header

    Handles formats like:
    - "Name <email@domain.com>"
    - "email@domain.com"
    - "Name Surname <email@domain.com>"
    """
    # Try to extract email from angle brackets first
    match = re.search(r'<(.+?)>', from_header)
    if match:
        return match.group(1).lower().strip()

    # Otherwise try to find email pattern
    match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', from_header)
    if match:
        return match.group(0).lower().strip()

    return None

def get_sender_context(from_header):
    """Get context about sender from brain database

    Args:
        from_header: Full "From" email header (e.g., "John Doe <john@example.com>")

    Returns:
        dict: {
            'name': str,
            'email': str,
            'tags': list,
            'projects': list,
            'relationship': str,
            'tone_notes': str,  # From "Stile Comunicazione" section
            'found': bool
        }
    """
    email = extract_email_address(from_header)
    if not email:
        return {'found': False}

    # Search all person files for this email
    people_dir = BRAIN / 'wiki' / 'people'
    if not people_dir.exists():
        return {'found': False}

    for person_file in people_dir.glob('*.md'):
        try:
            content = person_file.read_text()

            # Check if email is in file (frontmatter or content)
            if email.lower() not in content.lower():
                continue

            # Found a match! Parse YAML frontmatter
            frontmatter_match = re.search(r'^---\s*\n(.*?)\n---', content, re.DOTALL | re.MULTILINE)
            if not frontmatter_match:
                continue

            frontmatter = frontmatter_match.group(1)

            # Extract fields from frontmatter
            name = None
            name_match = re.search(r'^name:\s*(.+)$', frontmatter, re.MULTILINE)
            if name_match:
                name = name_match.group(1).strip().strip('"').strip("'")

            # Extract tags
            tags = []
            tags_match = re.search(r'^tags:\s*\n((?:- .+\n)+)', frontmatter, re.MULTILINE)
            if tags_match:
                tag_lines = tags_match.group(1)
                tags = [line.strip('- ').strip() for line in tag_lines.split('\n') if line.strip()]

            # Extract relationship type from tags (cliente, collaboratore, friend, etc)
            relationship_keywords = ['cliente', 'collaboratore', 'friend', 'consulenza', 'partner']
            relationship = next((tag for tag in tags if tag in relationship_keywords), 'sconosciuto')

            # Extract projects from tags (filter out generic tags like 'person', 'technical')
            generic_tags = ['person', 'technical', 'schema', 'project', 'assessment', 'hr']
            projects = [tag for tag in tags if tag not in generic_tags and tag not in relationship_keywords]

            # Extract tone/style from "Stile Comunicazione" section
            tone_notes = None
            tone_match = re.search(r'## Stile Comunicazione\s*\n(.+?)(?=\n##|\Z)', content, re.DOTALL)
            if tone_match:
                tone_notes = tone_match.group(1).strip()

            return {
                'found': True,
                'name': name,
                'email': email,
                'tags': tags,
                'projects': projects,
                'relationship': relationship,
                'tone_notes': tone_notes
            }

        except Exception as e:
            # Skip files that can't be parsed
            continue

    # Not found in database
    return {'found': False, 'email': email}

def get_unreplied_threads():
    """Get threads to AUTORESPONDER_EMAIL without reply"""
    token = get_access_token()
    if not token:
        return []

    # Search for ALL emails TO/CC anacleto (no time limit)
    url = 'https://gmail.googleapis.com/gmail/v1/users/me/threads'
    params = {
        'q': f'{{to:{AUTORESPONDER_EMAIL} OR cc:{AUTORESPONDER_EMAIL}}}',
        'maxResults': 20
    }
    headers = {'Authorization': f'Bearer {token}'}

    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        if response.status_code != 200:
            print(f"❌ Gmail API error: {response.status_code}")
            return []

        threads = response.json().get('threads', [])
        unreplied = []

        for thread in threads:
            # Get thread details
            thread_url = f"https://gmail.googleapis.com/gmail/v1/users/me/threads/{thread['id']}"
            thread_response = requests.get(thread_url, headers=headers, timeout=10)

            if thread_response.status_code == 200:
                thread_data = thread_response.json()
                messages = thread_data.get('messages', [])

                if not messages:
                    continue

                # Check if last message is FROM anacleto
                # If yes, we already replied → skip
                last_msg = messages[-1]
                last_headers = last_msg.get('payload', {}).get('headers', [])
                last_from = next((h['value'] for h in last_headers if h['name'] == 'From'), '')

                if AUTORESPONDER_EMAIL in last_from.lower():
                    # Last message is from Anacleto → already replied
                    continue

                # Get subject from first message
                first_msg = messages[0]
                first_headers = first_msg.get('payload', {}).get('headers', [])
                subject = next((h['value'] for h in first_headers if h['name'] == 'Subject'), '(No subject)')

                # Get sender from LAST message that's NOT from Anacleto
                # This is who we need to reply to and look up in database
                from_email = 'Unknown'
                for msg in reversed(messages):
                    msg_headers = msg.get('payload', {}).get('headers', [])
                    msg_from = next((h['value'] for h in msg_headers if h['name'] == 'From'), '')
                    if AUTORESPONDER_EMAIL not in msg_from.lower() and AUTORESPONDER_OWNER_EMAIL not in msg_from.lower():
                        from_email = msg_from
                        break

                # Skip automated/system emails (no-reply, notifications, etc)
                from_lower = from_email.lower()
                skip_patterns = _cfg.get('skip_patterns') or ['noreply', 'no-reply', 'notifications@', 'mailer-daemon', 'postmaster@']
                if any(pattern in from_lower for pattern in skip_patterns):
                    continue

                # BUILD FULL THREAD CONTEXT (all messages in chronological order)
                thread_context = []
                for msg in messages:
                    msg_headers = msg.get('payload', {}).get('headers', [])
                    msg_from = next((h['value'] for h in msg_headers if h['name'] == 'From'), 'Unknown')
                    msg_date = next((h['value'] for h in msg_headers if h['name'] == 'Date'), 'Unknown')
                    msg_body = extract_body(msg)

                    # Determine if message is from Anacleto or external
                    is_anacleto = AUTORESPONDER_EMAIL in msg_from.lower()

                    thread_context.append({
                        'from': msg_from,
                        'date': msg_date,
                        'body': msg_body,
                        'is_anacleto': is_anacleto
                    })

                unreplied.append({
                    'thread_id': thread['id'],
                    'subject': subject,
                    'from': from_email,  # Original sender (for context lookup)
                    'thread_context': thread_context,  # FULL thread
                    'message_id': first_msg['id']
                })

        return unreplied
    except Exception as e:
        print(f"❌ Error getting threads: {e}")
        return []

def extract_body(message):
    """Extract email body from message"""
    payload = message.get('payload', {})

    # Try plain text first
    if 'parts' in payload:
        for part in payload['parts']:
            if part.get('mimeType') == 'text/plain':
                data = part.get('body', {}).get('data', '')
                if data:
                    return base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')

    # Fallback to body data
    data = payload.get('body', {}).get('data', '')
    if data:
        return base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')

    return "(No body)"

def generate_reply(email_data):
    """Generate AI reply using OpenRouter"""
    api_key = get_openrouter_key()
    if not api_key:
        return None

    # Get sender context from brain database
    context = get_sender_context(email_data['from'])

    # Detect work context from thread
    work_keywords = ['progetto', 'preventivo', 'rendering', 'development', 'task', 'deadline',
                     'cliente', 'deliverable', 'fattura', 'invoice', 'payment', 'sviluppo',
                     'sito', 'website', 'app', 'wordpress', 'laravel', 'deploy', 'bug', 'fix',
                     'meeting', 'call', 'riunione', 'consegna']

    thread_text = ' '.join([msg['body'].lower() for msg in email_data.get('thread_context', [])])
    is_work_context = any(keyword in thread_text for keyword in work_keywords)

    # Build context-aware prompt
    context_section = ""
    if context.get('found'):
        relationship = context.get('relationship', 'sconosciuto')
        is_business = relationship in ['cliente', 'collaboratore', 'consulenza', 'partner']

        context_section = f"""
CONTESTO MITTENTE (dal brain database):
- Nome: {context.get('name', 'N/A')}
- Relazione: {relationship}
- Progetti comuni: {', '.join(context.get('projects', [])) if context.get('projects') else 'nessuno'}
- Tags: {', '.join(context.get('tags', [])) if context.get('tags') else 'nessuno'}
"""
        if context.get('tone_notes'):
            context_section += f"- Stile comunicazione: {context['tone_notes'][:200]}\n"

        # CRITICAL: Tone adaptation - TONE NOTES OVERRIDE EVERYTHING
        has_tone_notes = context.get('tone_notes') is not None

        if has_tone_notes:
            # Person has specific tone preferences → FOLLOW THEM
            context_section += """
⚠️ SEGUIRE STILE COMUNICAZIONE PREFERITO (vedi sopra):
- Le note sopra indicano ESATTAMENTE come questa persona preferisce comunicare
- IGNORA regole default, segui le preferenze specifiche
- Menziona progetti comuni se rilevanti
"""
        elif is_business or is_work_context:
            # No specific notes, but business context → professional
            context_section += """
⚠️ TONO PROFESSIONALE RICHIESTO:
- Relazione: Cliente/Collaboratore o argomento di LAVORO rilevato
- SWITCH A TONO PROFESSIONALE: competente, preciso, utile
- Ironia: LEGGERA e sottile (NON caustico/sarcastico)
- Obiettivo: Essere UTILE, non divertente
- Se non hai info: chiedi educatamente, NON prendere in giro
- Menziona progetti comuni se rilevanti
- Esempi tono OK: "Controllo e ti aggiorno", "Serve qualche dettaglio in più"
- Esempi tono VIETATI: "sfera di cristallo", "indovina tu", "domanda rivoluzionaria"
"""
        else:
            # No notes, no business → full sarcasm
            context_section += """
ADATTA LA RISPOSTA:
- Relazione: Amico/Informale
- Tono: Sarcastico, caustico, ironico (piena libertà)
- Menziona progetti comuni se rilevanti
"""
    else:
        if is_work_context:
            context_section = """
CONTESTO MITTENTE: NON TROVATO in database ma argomento LAVORO rilevato
- TONO PROFESSIONALE: prudente, educato, utile
- Ironia: minima (mittente sconosciuto + lavoro = massima professionalità)
"""
        else:
            context_section = """
CONTESTO MITTENTE: NON TROVATO in database (mittente sconosciuto)
- Usa tono default: sarcastico ma prudente
- Non fare riferimenti a progetti o relazioni (non abbiamo info)
"""

    # BUILD THREAD CONVERSATION (full context)
    thread_conversation = ""
    for i, msg in enumerate(email_data.get('thread_context', []), 1):
        sender_label = "ANACLETO" if msg['is_anacleto'] else "MITTENTE"
        # Limit body to 500 chars per message to avoid token overflow
        body_preview = msg['body'][:500] + ('...' if len(msg['body']) > 500 else '')
        thread_conversation += f"""
MESSAGE {i} - {sender_label} ({msg['date']}):
{body_preview}

"""

    prompt = f"""
Sei Anacleto, l'assistente AI di Giobi. Hai ricevuto un thread di email.

OGGETTO: {email_data['subject']}
MITTENTE ORIGINALE: {email_data['from']}

=== THREAD COMPLETO (in ordine cronologico) ===
{thread_conversation}
=== FINE THREAD ===

{context_section}

ISTRUZIONI:
- CONSIDERA TUTTO IL THREAD come contesto della conversazione, non solo l'ultimo messaggio
- Dai più peso all'ultimo messaggio (a quello devi rispondere), ma NON ignorare il resto del thread
- La tua risposta deve dimostrare che hai capito l'intera conversazione, non solo l'ultima riga
- Tono BASE: Sarcastico, ironico, caustico, punzecchiante
- Se richiesta banale: rispondi con sarcasmo sottile
- Se richiesta tecnica: competente ma con ironia
- Max 100 parole (brevità = più punch)
- NO firma (verrà aggiunta automaticamente)
- NO volgarità (mai parolacce o bestemmie nelle email)

Scrivi SOLO il testo della risposta:
"""

    try:
        response = requests.post(
            'https://openrouter.ai/api/v1/chat/completions',
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json',
                'HTTP-Referer': BRAIN_URL,
                'X-Title': 'Anacleto Autoresponder'
            },
            json={
                'model': 'anthropic/claude-3.5-sonnet',
                'messages': [{'role': 'user', 'content': prompt}],
                'max_tokens': 500
            },
            timeout=30
        )

        if response.status_code == 200:
            reply_text = response.json()['choices'][0]['message']['content'].strip()
            
            # Add signature (yaml config > env > default)
            signature = _cfg.get('signature') or os.getenv("AUTORESPONDER_SIGNATURE", f"\n\n---\n{AUTORESPONDER_NAME}\n{AUTORESPONDER_EMAIL}")
            
            return reply_text + signature
        else:
            print(f"❌ OpenRouter error: {response.status_code}")
            return None
    except Exception as e:
        print(f"❌ Error generating reply: {e}")
        return None

def create_draft(thread_id, to_address, subject, reply_text):
    """Create draft via Gmail API with FROM: AUTORESPONDER_EMAIL (NOT sending)"""
    token = get_access_token()
    if not token:
        return False

    # Create email message with proper headers
    from email.mime.text import MIMEText
    msg = MIMEText(reply_text)
    msg['From'] = f'{AUTORESPONDER_NAME} <{AUTORESPONDER_EMAIL}>'
    msg['To'] = to_address
    msg['Subject'] = f'Re: {subject}' if not subject.startswith('Re:') else subject

    raw_message = base64.urlsafe_b64encode(msg.as_bytes()).decode('utf-8')

    # CREATE DRAFT instead of sending
    url = 'https://gmail.googleapis.com/gmail/v1/users/me/drafts'
    headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}

    try:
        response = requests.post(
            url,
            headers=headers,
            json={
                'message': {
                    'threadId': thread_id,
                    'raw': raw_message
                }
            },
            timeout=10
        )

        return response.status_code == 200
    except Exception as e:
        print(f"❌ Error creating draft: {e}")
        return False

def send_notification(message):
    """Send notification to Discord #info"""
    from discord import send_to_channel
    send_to_channel(message, channel="info")

def update_sender_preferences(email_data):
    """
    Update sender's database file with preferences/requests from email

    If sender asks to be remembered, treated differently, or expresses
    preferences, update their wiki/people/*.md file.

    Only updates if person explicitly requests changes via email.
    """
    api_key = get_openrouter_key()
    if not api_key:
        return

    # Get sender email
    from_email = email_data.get('from', '')
    sender_email = extract_email_address(from_email)

    # Build thread text (only sender messages)
    thread_text = ""
    for msg in email_data.get('thread_context', []):
        if not msg['is_anacleto']:
            thread_text += f"{msg['body']}\n\n"

    if not thread_text.strip():
        return

    # Ask LLM to detect preference requests
    prompt = f"""
Analizza questa email e determina se il mittente chiede di essere ricordato o trattato in modo diverso.

EMAIL:
{thread_text[:1000]}

CERCA:
1. Richieste esplicite: "ricordati che...", "chiamami...", "preferisco...", "trattami..."
2. Preferenze comunicazione: "dammi del tu/lei", "usa tono formale/informale", "no sarcasmo", "puoi essere volgare"
3. Info personali da ricordare: "sono vegetariano", "lavoro in...", "mi piace..."
4. Correzioni: "in realtà il mio nome è...", "mi chiamo..."

RISPONDI IN JSON:
{{
  "has_preferences": true/false,
  "update_note": "breve nota da aggiungere al file database (max 100 parole) - null se niente"
}}

Se NO preferenze: {{"has_preferences": false, "update_note": null}}
"""

    try:
        response = requests.post(
            'https://openrouter.ai/api/v1/chat/completions',
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json',
                'HTTP-Referer': BRAIN_URL,
                'X-Title': 'Anacleto Preference Detector'
            },
            json={
                'model': 'anthropic/claude-3.5-sonnet',
                'messages': [{'role': 'user', 'content': prompt}],
                'max_tokens': 300
            },
            timeout=30
        )

        if response.status_code != 200:
            return

        result_text = response.json()['choices'][0]['message']['content'].strip()

        # Extract JSON
        import json
        json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
        if not json_match:
            return

        analysis = json.loads(json_match.group(0))

        if not analysis.get('has_preferences') or not analysis.get('update_note'):
            return

        # Find person file
        people_dir = BRAIN / 'wiki' / 'people'
        person_file = None

        for file in people_dir.glob('*.md'):
            content = file.read_text()
            if sender_email and sender_email.lower() in content.lower():
                person_file = file
                break

        if not person_file:
            # Create new person file
            from brain_writer import create_entity

            # Extract name from From header
            name_match = re.search(r'^(.+?)\s*<', from_email)
            sender_name = name_match.group(1).strip() if name_match else sender_email.split('@')[0]

            person_file = create_entity(
                entity_type='person',
                name=sender_name,
                tags=['unknown'],
                metadata={'email': sender_email}
            )
            print(f"   📝 Created new person: {person_file.name}")

        # Update file with preferences
        content = person_file.read_text()
        update_note = analysis.get('update_note', '')
        date_stamp = datetime.now().strftime('%Y-%m-%d')

        # Add update to appropriate section
        if '## Stile Comunicazione' in content:
            # Append to existing section
            content = content.replace(
                '## Stile Comunicazione\n',
                f'## Stile Comunicazione\n\n**Update {date_stamp}**: {update_note}\n\n'
            )
        elif '## Note' in content:
            # Append to notes
            content = content.replace(
                '## Note\n',
                f'## Note\n\n**Preference {date_stamp}**: {update_note}\n\n'
            )
        else:
            # Add new section at end
            content += f"\n\n## Note\n\n**Preference {date_stamp}**: {update_note}\n"

        # Write updated content
        person_file.write_text(content)
        print(f"   ✅ Updated {person_file.name} with preferences")

    except Exception as e:
        print(f"   ⚠️  Preference update error: {e}")

def analyze_and_log_thread(email_data, reply_sent):
    """
    Analyze thread and create wiki/log/diary entries

    After Anacleto sends a reply, analyze the conversation to:
    - Extract new people mentioned → create wiki/people/*.md
    - Log significant work conversations → log/YYYY/*.md
    - Record personal events → diary/YYYY/*.md
    """
    api_key = get_openrouter_key()
    if not api_key:
        return

    # Build thread summary
    thread_summary = f"Subject: {email_data['subject']}\n\n"
    for i, msg in enumerate(email_data.get('thread_context', []), 1):
        sender = "ANACLETO" if msg['is_anacleto'] else "SENDER"
        thread_summary += f"[{i}] {sender}: {msg['body'][:300]}\n\n"

    thread_summary += f"ANACLETO REPLY: {reply_sent[:300]}"

    # Ask LLM to analyze and extract info
    prompt = f"""
Analizza questa conversazione email e decidi cosa registrare nel brain database.

THREAD:
{thread_summary}

ESTRAI (se rilevante):

1. NUOVE PERSONE menzionate (non Anacleto/Giobi):
   - Nome completo
   - Email (se presente)
   - Ruolo/Azienda
   - Relazione (cliente/collaboratore/friend/altro)
   - Progetti menzionati

2. LOG (eventi di LAVORO significativi):
   - Progetto discusso
   - Task/Milestone raggiunto
   - Decisioni tecniche prese
   - Bug fix/Deploy/Feature completata

3. DIARY (eventi PERSONALI significativi):
   - Eventi vita privata
   - Relazioni personali
   - Emozioni/Riflessioni

RISPONDI IN JSON:
{{
  "people": [
    {{"name": "Nome Cognome", "email": "email@domain.com", "role": "ruolo", "relationship": "cliente/friend/etc", "notes": "contesto"}}
  ],
  "log": {{
    "should_create": true/false,
    "title": "Titolo breve",
    "project": "nome-progetto",
    "tags": ["tag1", "tag2"],
    "summary": "Riassunto conversazione (max 200 parole)"
  }},
  "diary": {{
    "should_create": true/false,
    "tags": ["tag1", "tag2"],
    "summary": "Riassunto evento personale (max 200 parole)"
  }}
}}

Se niente da registrare, usa: {{"people": [], "log": {{"should_create": false}}, "diary": {{"should_create": false}}}}
"""

    try:
        response = requests.post(
            'https://openrouter.ai/api/v1/chat/completions',
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json',
                'HTTP-Referer': BRAIN_URL,
                'X-Title': 'Anacleto Thread Analyzer'
            },
            json={
                'model': 'anthropic/claude-3.5-sonnet',
                'messages': [{'role': 'user', 'content': prompt}],
                'max_tokens': 1000
            },
            timeout=30
        )

        if response.status_code != 200:
            print(f"⚠️  Thread analysis failed: {response.status_code}")
            return

        result_text = response.json()['choices'][0]['message']['content'].strip()

        # Extract JSON from response (might have markdown code blocks)
        import json
        import re
        json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
        if not json_match:
            print(f"⚠️  No JSON found in analysis")
            return

        analysis = json.loads(json_match.group(0))

        # Import brain_writer
        from brain_writer import create_entity, create_log, create_diary
        from datetime import datetime

        # Create people entries
        for person in analysis.get('people', []):
            try:
                create_entity(
                    entity_type='person',
                    name=person['name'],
                    tags=[person.get('relationship', 'unknown')],
                    metadata={
                        'email': person.get('email'),
                        'role': person.get('role'),
                        'notes': person.get('notes')
                    }
                )
                print(f"✅ Created person: {person['name']}")
            except FileExistsError:
                print(f"⚠️  Person already exists: {person['name']}")
            except Exception as e:
                print(f"⚠️  Failed to create person {person.get('name')}: {e}")

        # Create log entry
        log_data = analysis.get('log', {})
        if log_data.get('should_create'):
            try:
                today = datetime.now().strftime('%Y-%m-%d')
                create_log(
                    date=today,
                    title=log_data['title'],
                    content=log_data['summary'],
                    tags=log_data.get('tags', []),
                    project=log_data.get('project')
                )
                print(f"✅ Created log: {log_data['title']}")
            except Exception as e:
                print(f"⚠️  Failed to create log: {e}")

        # Create diary entry
        diary_data = analysis.get('diary', {})
        if diary_data.get('should_create'):
            try:
                today = datetime.now().strftime('%Y-%m-%d')
                create_diary(
                    date=today,
                    content=diary_data['summary'],
                    tags=diary_data.get('tags', []),
                    source='autoresponder'
                )
                print(f"✅ Created diary entry")
            except Exception as e:
                print(f"⚠️  Failed to create diary: {e}")

    except Exception as e:
        print(f"⚠️  Thread analysis error: {e}")

def main(dry_run=False):
    """Check and auto-reply to emails"""
    if dry_run:
        print("🔍 DRY RUN MODE - No emails will be sent\n")

    print(f"📧 Checking {AUTORESPONDER_EMAIL} for unreplied emails...")

    unreplied = get_unreplied_threads()

    if not unreplied:
        print("✅ No unreplied emails found")
        return 0

    print(f"📬 Found {len(unreplied)} unreplied email(s)\n")

    for email_data in unreplied:
        print(f"{'─' * 80}")
        print(f"📨 {email_data['subject']}")
        print(f"   FROM: {email_data['from']}")

        # Show thread context
        thread_ctx = email_data.get('thread_context', [])
        print(f"   📜 THREAD: {len(thread_ctx)} message(s)")
        for i, msg in enumerate(thread_ctx, 1):
            sender_label = "🦉 ANACLETO" if msg['is_anacleto'] else "👤 MITTENTE"
            print(f"      [{i}] {sender_label}: {msg['body'][:100]}...")

        # Get and display sender context
        context = get_sender_context(email_data['from'])
        if context.get('found'):
            print(f"   🧠 CONTEXT: {context.get('name')} ({context.get('relationship')})")
            if context.get('projects'):
                print(f"      Projects: {', '.join(context['projects'])}")
        else:
            print(f"   ⚠️  CONTEXT: Not found in database (unknown sender)")
        print()

        # Generate reply
        reply = generate_reply(email_data)

        if not reply:
            print(f"   ⚠️  Failed to generate reply")
            continue

        print(f"   🦉 ANACLETO WOULD REPLY ({len(reply)} chars):")
        print(f"   {reply}")
        print()

        if dry_run:
            print(f"   [DRY-RUN] Would create draft reply to: {email_data['from']}")
            print(f"   [DRY-RUN] Would notify Discord")
            print(f"   [DRY-RUN] Would analyze thread and create wiki/log/diary entries")
        else:
            # Create draft (NOT sending)
            if create_draft(email_data['thread_id'], email_data['from'], email_data['subject'], reply):
                print(f"   ✅ Draft created successfully (FROM: {AUTORESPONDER_EMAIL})")

                # Notify on Discord
                discord_msg = f"""📧 Anacleto Draft Created

DA: {email_data['from']}
OGGETTO: {email_data['subject']}

BOZZA PREPARATA (da revisionare e inviare manualmente):
{reply[:300]}..."""

                send_notification(discord_msg)

                # Analyze thread and create wiki/log/diary entries
                print(f"   🧠 Analyzing thread for wiki/log/diary...")
                analyze_and_log_thread(email_data, reply)

                # Update sender preferences if they requested changes
                print(f"   📝 Checking for preference updates...")
                update_sender_preferences(email_data)

            else:
                print(f"   ❌ Failed to create draft")

    return 0

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Anacleto auto-responder')
    parser.add_argument('--dry-run', action='store_true', help='Show what would happen without sending')
    args = parser.parse_args()

    sys.exit(main(dry_run=args.dry_run))
