#!/usr/bin/env python3
"""
WordPress Publisher Agent

Publishes posts to WordPress via REST API with:
- Markdown → HTML conversion
- Auto-generated images (hero + mid-article)
- Topic-aware image styling
- Featured image upload

Usage:
  python wordpress_publisher.py --url https://blog.giobi.com --file post.md --status draft
  python wordpress_publisher.py --url https://blog.giobi.com --title "Title" --content "Content" --status publish
"""

import argparse
import requests
import sys
import os
import re
import subprocess
import tempfile
from pathlib import Path

def load_credentials(site_key='WORDPRESS'):
    """Load WordPress credentials from .env

    Args:
        site_key: Prefix for credentials (WORDPRESS, BLOG_WORDPRESS, etc.)
    """
    env_path = Path(__file__).parent.parent.parent / '.env'

    creds = {}
    with open(env_path) as f:
        for line in f:
            if line.startswith(site_key):
                key, val = line.strip().split('=', 1)
                creds[key] = val.strip('"')

    url_key = f'{site_key}_URL'
    user_key = f'{site_key}_USERNAME'
    pass_key = f'{site_key}_APP_PASSWORD'

    return creds.get(url_key), creds.get(user_key), creds.get(pass_key)

def parse_markdown_frontmatter(content):
    """Parse Jekyll-style frontmatter from markdown"""
    if not content.startswith('---'):
        return {}, content

    parts = content.split('---', 2)
    if len(parts) < 3:
        return {}, content

    frontmatter = {}
    for line in parts[1].strip().split('\n'):
        if ':' in line:
            key, val = line.split(':', 1)
            frontmatter[key.strip()] = val.strip().strip('"\'')

    return frontmatter, parts[2].strip()

def markdown_to_html(markdown_text):
    """Convert markdown to HTML

    Basic conversion for common patterns. For complex markdown,
    consider using 'markdown' or 'markdown2' library.
    """
    html = markdown_text

    # Headers
    html = re.sub(r'^### (.*?)$', r'<h3>\1</h3>', html, flags=re.MULTILINE)
    html = re.sub(r'^## (.*?)$', r'<h2>\1</h2>', html, flags=re.MULTILINE)
    html = re.sub(r'^# (.*?)$', r'<h1>\1</h1>', html, flags=re.MULTILINE)

    # Bold and italic
    html = re.sub(r'\*\*\*(.+?)\*\*\*', r'<strong><em>\1</em></strong>', html)
    html = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html)
    html = re.sub(r'\*(.+?)\*', r'<em>\1</em>', html)
    html = re.sub(r'__(.+?)__', r'<strong>\1</strong>', html)
    html = re.sub(r'_(.+?)_', r'<em>\1</em>', html)

    # Links
    html = re.sub(r'\[([^\]]+)\]\(([^\)]+)\)', r'<a href="\2">\1</a>', html)

    # Code blocks
    html = re.sub(r'```(\w+)?\n(.*?)```', r'<pre><code>\2</code></pre>', html, flags=re.DOTALL)
    html = re.sub(r'`([^`]+)`', r'<code>\1</code>', html)

    # Lists
    html = re.sub(r'^\- (.+)$', r'<li>\1</li>', html, flags=re.MULTILINE)
    html = re.sub(r'(<li>.*</li>)', r'<ul>\1</ul>', html, flags=re.DOTALL)

    # Paragraphs (split by double newline)
    paragraphs = html.split('\n\n')
    html_paragraphs = []
    for p in paragraphs:
        p = p.strip()
        if p and not p.startswith('<'):
            html_paragraphs.append(f'<p>{p}</p>')
        else:
            html_paragraphs.append(p)
    html = '\n\n'.join(html_paragraphs)

    return html

def detect_topic(title, content):
    """Detect post topic from title and content

    Returns topic keyword for image style selection
    """
    text = (title + ' ' + content).lower()

    # Tech/Dev keywords
    if any(word in text for word in ['code', 'programming', 'developer', 'api', 'framework', 'database', 'algorithm', 'git', 'design system', 'frontend', 'backend']):
        return 'tech'

    # Art/Creative keywords
    if any(word in text for word in ['arte', 'pittura', 'musica', 'film', 'creatività', 'design', 'estetica', 'artista']):
        return 'art'

    # Science/Brain keywords
    if any(word in text for word in ['brain', 'neuroscience', 'sogni', 'cervello', 'ai', 'neural', 'cognition', 'psicologia']):
        return 'science'

    # Personal/Lifestyle keywords
    if any(word in text for word in ['life', 'personal', 'viaggio', 'storia', 'esperienza', 'riflessione']):
        return 'personal'

    # Default
    return 'general'

def get_image_style_prompt(topic, position='hero'):
    """Get image style prompt based on topic

    Args:
        topic: Topic keyword (tech, art, science, personal, general)
        position: 'hero' or 'mid' (hero = more dramatic, mid = more subtle)
    """
    styles = {
        'tech': {
            'hero': 'Modern tech illustration, geometric shapes, vibrant gradients, code snippets floating, clean minimal design, professional',
            'mid': 'Abstract tech pattern, grid lines, subtle geometric shapes, modern color palette, minimalist'
        },
        'art': {
            'hero': 'Abstract artistic composition, bold colors, creative energy, paint strokes, modern art style, expressive',
            'mid': 'Artistic texture, watercolor effect, soft gradients, creative mood, subtle abstract shapes'
        },
        'science': {
            'hero': 'Scientific illustration, neural networks, brain synapses, cosmic patterns, blue purple palette, futuristic',
            'mid': 'Abstract scientific pattern, molecules, connections, subtle tech overlay, clean modern style'
        },
        'personal': {
            'hero': 'Warm illustration, human-centered, friendly colors, approachable style, life scenes, cozy atmosphere',
            'mid': 'Gentle illustration, warm tones, simple shapes, friendly mood, subtle details'
        },
        'general': {
            'hero': 'Modern abstract illustration, balanced composition, professional style, clean design, versatile mood',
            'mid': 'Simple abstract pattern, neutral colors, clean minimal design, professional look'
        }
    }

    return styles.get(topic, styles['general'])[position]

def generate_image(prompt, output_path):
    """Generate image using image_generator.py agent"""
    agent_path = Path(__file__).parent / 'image_generator.py'

    result = subprocess.run(
        ['python3', str(agent_path), '--prompt', prompt, '--output', str(output_path)],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        raise Exception(f"Image generation failed: {result.stderr}")

    return output_path

def upload_image_to_wordpress(url, username, password, image_path):
    """Upload image to WordPress media library

    Returns media ID and URL
    """
    api_url = f"{url}/wp-json/wp/v2/media"

    filename = Path(image_path).name

    with open(image_path, 'rb') as f:
        files = {
            'file': (filename, f, 'image/png')
        }

        response = requests.post(
            api_url,
            files=files,
            auth=(username, password)
        )

    if response.status_code in [200, 201]:
        result = response.json()
        return result['id'], result['source_url']
    else:
        raise Exception(f"Image upload failed {response.status_code}: {response.text}")

def create_post_with_images(url, username, password, title, content, status='draft', categories=None, generate_images=True):
    """Create WordPress post with generated images

    Args:
        url: WordPress site URL
        username: WordPress username
        password: WordPress app password
        title: Post title
        content: Post content (markdown)
        status: Post status (draft/publish/private)
        categories: List of category IDs
        generate_images: Whether to generate images (default True)

    Returns:
        Post data dict
    """
    # Detect topic
    topic = detect_topic(title, content)
    print(f"📊 Topic detected: {topic}")

    # Convert markdown to HTML
    html_content = markdown_to_html(content)

    # Generate images if enabled
    hero_id = None
    mid_url = None

    if generate_images:
        print(f"🎨 Generating images with {topic} style...")

        # Create temp dir for images
        temp_dir = Path(tempfile.mkdtemp())

        # Generate hero image
        hero_prompt = f"{get_image_style_prompt(topic, 'hero')}, related to: {title[:100]}"
        hero_path = temp_dir / 'hero.png'
        generate_image(hero_prompt, hero_path)
        print(f"   Hero image generated: {hero_path}")

        # Upload hero
        hero_id, hero_url = upload_image_to_wordpress(url, username, password, hero_path)
        print(f"   Hero uploaded: ID {hero_id}")

        # Generate mid-article image
        mid_prompt = f"{get_image_style_prompt(topic, 'mid')}, context: {title[:100]}"
        mid_path = temp_dir / 'mid.png'
        generate_image(mid_prompt, mid_path)
        print(f"   Mid image generated: {mid_path}")

        # Upload mid
        mid_id, mid_url = upload_image_to_wordpress(url, username, password, mid_path)
        print(f"   Mid uploaded: ID {mid_id}")

        # Insert mid image in HTML (roughly at 50% position)
        html_lines = html_content.split('\n')
        mid_point = len(html_lines) // 2
        mid_img_html = f'\n<figure class="wp-block-image"><img src="{mid_url}" alt="{title}" /></figure>\n'
        html_lines.insert(mid_point, mid_img_html)
        html_content = '\n'.join(html_lines)

    # Create post
    api_url = f"{url}/wp-json/wp/v2/posts"

    data = {
        'title': title,
        'content': html_content,
        'status': status
    }

    if categories:
        data['categories'] = categories

    if hero_id:
        data['featured_media'] = hero_id

    response = requests.post(
        api_url,
        json=data,
        auth=(username, password)
    )

    if response.status_code in [200, 201]:
        result = response.json()
        return result
    else:
        raise Exception(f"WordPress API error {response.status_code}: {response.text}")

def main():
    parser = argparse.ArgumentParser(description='Publish to WordPress with auto-generated images')
    parser.add_argument('--url', required=True, help='WordPress site URL (e.g., https://blog.giobi.com)')
    parser.add_argument('--title', help='Post title')
    parser.add_argument('--content', help='Post content (markdown)')
    parser.add_argument('--file', help='Markdown file with content')
    parser.add_argument('--status', default='draft', choices=['draft', 'publish', 'private'], help='Post status (default: draft)')
    parser.add_argument('--categories', help='Comma-separated category IDs')
    parser.add_argument('--no-images', action='store_true', help='Skip image generation')

    args = parser.parse_args()

    # Detect which credentials to use based on URL
    if 'blog.giobi.com' in args.url:
        site_key = 'BLOG_WORDPRESS'
    elif 'dev.giobi.com' in args.url:
        site_key = 'DEV_WORDPRESS'
    else:
        site_key = 'WORDPRESS'

    # Load credentials
    wp_url, wp_user, wp_pass = load_credentials(site_key)

    if not all([wp_url, wp_user, wp_pass]):
        print(f"❌ WordPress credentials not found in .env for {site_key}")
        sys.exit(1)

    # Get content
    if args.file:
        with open(args.file) as f:
            file_content = f.read()

        frontmatter, content = parse_markdown_frontmatter(file_content)
        title = args.title or frontmatter.get('title', 'Untitled')
        categories_str = args.categories or frontmatter.get('categories')
    elif args.content and args.title:
        title = args.title
        content = args.content
        categories_str = args.categories
    else:
        print("❌ Provide either --file or both --title and --content")
        sys.exit(1)

    # Parse categories
    categories = None
    if categories_str:
        categories = [int(c.strip()) for c in str(categories_str).split(',') if c.strip().isdigit()]

    try:
        print(f"📝 Publishing to {args.url}...")
        result = create_post_with_images(
            args.url,
            wp_user,
            wp_pass,
            title,
            content,
            args.status,
            categories,
            generate_images=not args.no_images
        )

        print(f"\n✅ Post created successfully!")
        print(f"   ID: {result['id']}")
        print(f"   Status: {result['status']}")
        print(f"   URL: {result['link']}")

    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
