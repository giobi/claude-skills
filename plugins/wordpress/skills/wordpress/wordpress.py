#!/usr/bin/env python3
"""
WordPress REST API Helper Library

Provides post CRUD for multiple WordPress sites.
Site configs are loaded dynamically from wiki/projects/*.md files.

Usage:
    from wordpress import create_draft, get_posts, update_post, get_sites

    # Create draft on blog.giobi.com (default)
    post = create_draft(
        title="My Post",
        content="<p>Hello world</p>",
        tags=["test"]
    )

    # Create draft on specific site
    post = create_draft(
        title="My Post",
        content="<p>Hello world</p>",
        site="blog.giobi.com"
    )

    # Get recent posts
    posts = get_posts(limit=10)

    # List configured sites
    sites = get_sites()

Site Configuration:
    Sites are configured in wiki/projects/*.md with wordpress frontmatter:

    ```yaml
    wordpress:
      url: https://blog.giobi.com
      env_prefix: BLOG_WORDPRESS
    ```

    This expects these env vars in .env:
    - {env_prefix}_USERNAME
    - {env_prefix}_APP_PASSWORD
    - {env_prefix}_URL (optional, uses wordpress.url as default)

Auth:
    Uses Application Passwords (not regular passwords!)
    Generate at: WordPress Admin > Users > Profile > Application Passwords
"""

import requests
import base64
import os
import yaml
from pathlib import Path
from typing import Optional, Dict, Any, List

_BRAIN_ROOT = Path(__file__).parent.parent.parent.resolve()
ENV_PATH = str(_BRAIN_ROOT / '.env')
PROJECTS_PATH = str(_BRAIN_ROOT / 'wiki/projects')

# Cache for loaded sites
_sites_cache: Optional[Dict[str, Dict[str, str]]] = None

DEFAULT_SITE = None  # Set in wiki/skills/wordpress.md or pass site= explicitly


def _load_sites_from_projects() -> Dict[str, Dict[str, str]]:
    """
    Scan wiki/projects/*.md for WordPress configs.

    Returns:
        dict: Site configs keyed by project name
    """
    global _sites_cache
    if _sites_cache is not None:
        return _sites_cache

    sites = {}
    projects_dir = Path(PROJECTS_PATH)

    if not projects_dir.exists():
        return sites

    for md_file in projects_dir.glob('*.md'):
        try:
            content = md_file.read_text()
            if not content.startswith('---'):
                continue

            # Parse YAML frontmatter
            parts = content.split('---', 2)
            if len(parts) < 3:
                continue

            frontmatter = yaml.safe_load(parts[1])
            if not frontmatter or 'wordpress' not in frontmatter:
                continue

            wp_config = frontmatter['wordpress']
            if not isinstance(wp_config, dict):
                continue

            # Extract config
            site_name = frontmatter.get('name', md_file.stem)
            env_prefix = wp_config.get('env_prefix', '')
            default_url = wp_config.get('url', '')

            if not env_prefix:
                continue

            sites[site_name] = {
                'url_var': f'{env_prefix}_URL',
                'user_var': f'{env_prefix}_USERNAME',
                'pass_var': f'{env_prefix}_APP_PASSWORD',
                'default_url': default_url
            }

        except Exception:
            # Skip files with parsing errors
            continue

    _sites_cache = sites
    return sites


def get_all_sites() -> Dict[str, Dict[str, str]]:
    """Get all WordPress site configurations from projects."""
    return _load_sites_from_projects()


def load_env() -> Dict[str, str]:
    """Load environment variables from .env file"""
    env = {}
    if not os.path.exists(ENV_PATH):
        raise FileNotFoundError(f".env not found at {ENV_PATH}")

    with open(ENV_PATH) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                env[key] = value.strip('"')

    return env


def get_site_config(site: str = DEFAULT_SITE) -> Dict[str, str]:
    """
    Get configuration for a WordPress site.

    Args:
        site: Site key (e.g., 'blog.giobi.com')

    Returns:
        dict: Configuration with url, username, password

    Raises:
        ValueError: If site not configured or credentials missing
    """
    sites = _load_sites_from_projects()

    if site not in sites:
        available = ', '.join(sites.keys()) if sites else 'none'
        raise ValueError(
            f"Unknown site '{site}'. Available: {available}. "
            f"Add 'wordpress' config to wiki/projects/{site}.md"
        )

    config = sites[site]
    env = load_env()

    url = env.get(config['url_var'], config['default_url'])
    username = env.get(config['user_var'])
    password = env.get(config['pass_var'])

    if not username or not password:
        raise ValueError(
            f"Missing credentials for {site}. "
            f"Need {config['user_var']} and {config['pass_var']} in .env"
        )

    return {
        'url': url.rstrip('/'),
        'username': username,
        'password': password
    }


def get_sites() -> List[str]:
    """
    Get list of configured WordPress sites.

    Returns:
        list: Site keys that have valid credentials in .env
    """
    sites = _load_sites_from_projects()
    env = load_env()
    valid_sites = []

    for site, config in sites.items():
        if env.get(config['user_var']) and env.get(config['pass_var']):
            valid_sites.append(site)

    return valid_sites


def wp_api_call(
    method: str,
    endpoint: str,
    site: str = DEFAULT_SITE,
    params: Optional[Dict[str, Any]] = None,
    json_data: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Make authenticated WordPress REST API call.

    Args:
        method: HTTP method (GET, POST, PUT, DELETE)
        endpoint: API endpoint (e.g., '/wp/v2/posts')
        site: Site key
        params: Query parameters
        json_data: JSON body for POST/PUT

    Returns:
        dict: JSON response from API

    Raises:
        requests.HTTPError: If request fails
    """
    config = get_site_config(site)

    # Basic auth with application password
    credentials = f"{config['username']}:{config['password']}"
    token = base64.b64encode(credentials.encode()).decode()

    headers = {
        'Authorization': f'Basic {token}',
        'Content-Type': 'application/json'
    }

    url = f"{config['url']}/wp-json{endpoint}"

    response = requests.request(
        method=method,
        url=url,
        headers=headers,
        params=params,
        json=json_data,
        timeout=30
    )

    response.raise_for_status()
    return response.json()


# === Posts ===

def create_draft(
    title: str,
    content: str,
    site: str = DEFAULT_SITE,
    excerpt: Optional[str] = None,
    categories: Optional[List[int]] = None,
    tags: Optional[List[str]] = None,
    featured_media: Optional[int] = None
) -> Dict[str, Any]:
    """
    Create a draft post.

    Args:
        title: Post title
        content: Post content (HTML)
        site: WordPress site key
        excerpt: Post excerpt
        categories: List of category IDs
        tags: List of tag names (will be created if don't exist)
        featured_media: Featured image attachment ID

    Returns:
        dict: Created post object with id, link, etc.

    Example:
        post = create_draft(
            title="My Post",
            content="<p>Hello world</p>",
            tags=["test", "example"]
        )
        print(f"Draft created: {post['id']}")
        print(f"Edit: {site}/wp-admin/post.php?post={post['id']}&action=edit")
    """
    data = {
        'title': title,
        'content': content,
        'status': 'draft'
    }

    if excerpt:
        data['excerpt'] = excerpt
    if categories:
        data['categories'] = categories
    if tags:
        data['tags'] = tags
    if featured_media:
        data['featured_media'] = featured_media

    return wp_api_call('POST', '/wp/v2/posts', site=site, json_data=data)


def create_post(
    title: str,
    content: str,
    site: str = DEFAULT_SITE,
    status: str = 'publish',
    **kwargs
) -> Dict[str, Any]:
    """
    Create a post with specified status.

    Args:
        title: Post title
        content: Post content (HTML)
        site: WordPress site key
        status: Post status (draft, publish, pending, private)
        **kwargs: Additional fields (excerpt, categories, tags, featured_media)

    Returns:
        dict: Created post object
    """
    data = {
        'title': title,
        'content': content,
        'status': status,
        **kwargs
    }

    return wp_api_call('POST', '/wp/v2/posts', site=site, json_data=data)


def get_posts(
    site: str = DEFAULT_SITE,
    limit: int = 10,
    status: str = 'any',
    search: Optional[str] = None,
    categories: Optional[List[int]] = None,
    tags: Optional[List[int]] = None
) -> List[Dict[str, Any]]:
    """
    Get posts from WordPress.

    Args:
        site: WordPress site key
        limit: Number of posts to fetch
        status: Post status filter (any, publish, draft, pending, private)
        search: Search query
        categories: Filter by category IDs
        tags: Filter by tag IDs

    Returns:
        list: Post objects
    """
    params = {
        'per_page': min(limit, 100),
        'status': status
    }

    if search:
        params['search'] = search
    if categories:
        params['categories'] = ','.join(map(str, categories))
    if tags:
        params['tags'] = ','.join(map(str, tags))

    return wp_api_call('GET', '/wp/v2/posts', site=site, params=params)


def get_post(post_id: int, site: str = DEFAULT_SITE) -> Dict[str, Any]:
    """
    Get single post by ID.

    Args:
        post_id: WordPress post ID
        site: WordPress site key

    Returns:
        dict: Post object
    """
    return wp_api_call('GET', f'/wp/v2/posts/{post_id}', site=site)


def update_post(
    post_id: int,
    site: str = DEFAULT_SITE,
    title: Optional[str] = None,
    content: Optional[str] = None,
    status: Optional[str] = None,
    excerpt: Optional[str] = None,
    categories: Optional[List[int]] = None,
    tags: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Update an existing post.

    Args:
        post_id: WordPress post ID
        site: WordPress site key
        title: New title
        content: New content
        status: New status
        excerpt: New excerpt
        categories: New category IDs
        tags: New tag names

    Returns:
        dict: Updated post object
    """
    data = {}

    if title is not None:
        data['title'] = title
    if content is not None:
        data['content'] = content
    if status is not None:
        data['status'] = status
    if excerpt is not None:
        data['excerpt'] = excerpt
    if categories is not None:
        data['categories'] = categories
    if tags is not None:
        data['tags'] = tags

    return wp_api_call('POST', f'/wp/v2/posts/{post_id}', site=site, json_data=data)


def delete_post(post_id: int, site: str = DEFAULT_SITE, force: bool = False) -> Dict[str, Any]:
    """
    Delete a post.

    Args:
        post_id: WordPress post ID
        site: WordPress site key
        force: If True, permanently delete. If False, move to trash.

    Returns:
        dict: Deleted post object
    """
    params = {'force': force}
    return wp_api_call('DELETE', f'/wp/v2/posts/{post_id}', site=site, params=params)


# === Categories & Tags ===

def get_categories(site: str = DEFAULT_SITE) -> List[Dict[str, Any]]:
    """Get all categories."""
    return wp_api_call('GET', '/wp/v2/categories', site=site, params={'per_page': 100})


def get_tags_wp(site: str = DEFAULT_SITE, search: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Get tags from WordPress.

    Args:
        site: WordPress site key
        search: Search query

    Returns:
        list: Tag objects
    """
    params = {'per_page': 100}
    if search:
        params['search'] = search
    return wp_api_call('GET', '/wp/v2/tags', site=site, params=params)


# === Media ===

def get_media(site: str = DEFAULT_SITE, limit: int = 10) -> List[Dict[str, Any]]:
    """Get media items."""
    params = {'per_page': min(limit, 100)}
    return wp_api_call('GET', '/wp/v2/media', site=site, params=params)


if __name__ == '__main__':
    # Quick test
    print("🧪 Testing WordPress API...")

    try:
        sites = get_sites()
        print(f"✅ Configured sites: {sites}")

        for site in sites:
            print(f"\n--- {site} ---")
            try:
                posts = get_posts(site=site, limit=3, status='any')
                print(f"✅ Posts: {len(posts)}")
                for post in posts[:3]:
                    title = post['title']['rendered'][:50]
                    status = post['status']
                    print(f"   [{status}] {title}")
            except Exception as e:
                print(f"❌ Error: {e}")

    except Exception as e:
        print(f"❌ Error: {e}")
