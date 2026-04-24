"""
GitHub API wrapper for Brain Protocol skills.

Usage:
    from github import create_issue, list_issues, get_repo, list_repos
    from github import create_gist, list_gists, get_gist, update_gist, delete_gist

Environment:
    GITHUB_TOKEN - Personal access token with repo scope
"""

import os
import requests
from typing import Optional, List, Dict, Any
from pathlib import Path
from dotenv import load_dotenv

# Load .env from brain root
load_dotenv(Path(__file__).parent.parent.parent / '.env')


def _get_token(token_env: str = 'GITHUB_TOKEN') -> str:
    """Get GitHub token from env.

    Args:
        token_env: Environment variable name (default: GITHUB_TOKEN).
                   Use alternate env vars for multi-account setups
                   (e.g. bot accounts, org tokens).
    """
    token = os.getenv(token_env)
    if not token:
        raise ValueError(f"{token_env} not found in .env")
    return token


def _headers(token_env: str = 'GITHUB_TOKEN') -> Dict[str, str]:
    """Standard headers for GitHub API."""
    return {
        'Authorization': f'token {_get_token(token_env)}',
        'Accept': 'application/vnd.github.v3+json'
    }


def _api(method: str, endpoint: str, token_env: str = 'GITHUB_TOKEN', **kwargs) -> requests.Response:
    """Make API request to GitHub.

    Args:
        method: HTTP method (GET, POST, PUT, PATCH, DELETE)
        endpoint: API endpoint (e.g. '/repos/owner/repo')
        token_env: Environment variable name for authentication
        **kwargs: Passed to requests.request (json, params, etc.)
    """
    url = f'https://api.github.com{endpoint}'
    return requests.request(method, url, headers=_headers(token_env), **kwargs)


# =============================================================================
# REPOS
# =============================================================================

def list_repos(user: Optional[str] = None, org: Optional[str] = None,
               limit: int = 30) -> List[Dict[str, Any]]:
    """List repositories for user or org.

    Args:
        user: GitHub username (default: authenticated user)
        org: Organization name (overrides user)
        limit: Max repos to return
    """
    if org:
        endpoint = f'/orgs/{org}/repos'
    elif user:
        endpoint = f'/users/{user}/repos'
    else:
        endpoint = '/user/repos'

    resp = _api('GET', endpoint, params={'per_page': limit})
    if resp.status_code != 200:
        print(f"Error: {resp.status_code} - {resp.json().get('message', '')}")
        return []
    return resp.json()


def get_repo(repo: str) -> Optional[Dict[str, Any]]:
    """Get repository info.

    Args:
        repo: Full repo name (e.g., 'owner/repo')
    """
    resp = _api('GET', f'/repos/{repo}')
    if resp.status_code != 200:
        return None
    return resp.json()


def create_repo(name: str, description: str = '', private: bool = False,
                auto_init: bool = False, org: Optional[str] = None,
                homepage: str = '') -> Optional[Dict[str, Any]]:
    """Create a new repository.

    Args:
        name: Repository name
        description: Repository description
        private: Whether repo is private (default False)
        auto_init: Initialize with README (default False)
        org: Organization name (if None, creates under authenticated user)
        homepage: URL for the repository homepage
    """
    data = {
        'name': name,
        'description': description,
        'private': private,
        'auto_init': auto_init,
    }
    if homepage:
        data['homepage'] = homepage
    endpoint = f'/orgs/{org}/repos' if org else '/user/repos'
    resp = _api('POST', endpoint, json=data)
    if resp.status_code not in (200, 201):
        print(f"Error: {resp.status_code} - {resp.json().get('message', '')}")
        return None
    return resp.json()


def delete_repo(repo: str) -> bool:
    """Delete a repository.

    Args:
        repo: Full repo name (e.g., 'owner/repo')
    """
    resp = _api('DELETE', f'/repos/{repo}')
    if resp.status_code == 204:
        print(f"Repository {repo} deleted")
        return True
    print(f"Error: {resp.status_code} - {resp.json().get('message', '')}")
    return False


def set_repo_topics(repo: str, topics: List[str]) -> bool:
    """Replace all topics on a repository.

    Args:
        repo: Full repo name
        topics: List of topic strings (lowercase, hyphens allowed)
    """
    url = f'https://api.github.com/repos/{repo}/topics'
    headers = _headers()
    headers['Accept'] = 'application/vnd.github.mercy-preview+json'
    resp = requests.put(url, headers=headers, json={'names': topics})
    if resp.status_code == 200:
        return True
    print(f"Topics error: {resp.status_code} - {resp.json().get('message', '')}")
    return False


def search_repos(query: str, limit: int = 20) -> List[Dict[str, Any]]:
    """Search repositories by name/description."""
    r = _api('GET', '/search/repositories', params={'q': query, 'per_page': limit})
    if r.status_code == 200:
        return r.json().get('items', [])
    return []


# =============================================================================
# FILE CONTENTS
# =============================================================================

def get_file_contents(repo: str, path: str, ref: str = None,
                      token_env: str = 'GITHUB_TOKEN') -> Optional[str]:
    """Get the decoded content of a file from a repository.

    Args:
        repo: Full repo name
        path: File path in the repo
        ref: Branch/tag/commit (default: repo default branch)
        token_env: Environment variable name for the GitHub token
    """
    import base64
    params = {}
    if ref:
        params['ref'] = ref
    resp = _api('GET', f'/repos/{repo}/contents/{path}', token_env=token_env, params=params)
    if resp.status_code != 200:
        print(f"Error: {resp.status_code} - {resp.json().get('message', '')}")
        return None
    data = resp.json()
    if data.get('encoding') == 'base64':
        return base64.b64decode(data['content']).decode('utf-8')
    return data.get('content')


def get_file_sha(repo: str, path: str, ref: str = None,
                 token_env: str = 'GITHUB_TOKEN') -> Optional[str]:
    """Get the SHA of a file in a repository (needed for updates)."""
    params = {}
    if ref:
        params['ref'] = ref
    resp = _api('GET', f'/repos/{repo}/contents/{path}', token_env=token_env, params=params)
    if resp.status_code != 200:
        return None
    return resp.json().get('sha')


def create_or_update_file(repo: str, path: str, content: str, message: str,
                          branch: str = 'main') -> Optional[Dict[str, Any]]:
    """Create or update a file in a repository via Contents API.

    Args:
        repo: Full repo name
        path: File path in repo
        content: File content (plain text, will be base64-encoded)
        message: Commit message
        branch: Target branch (default 'main')
    """
    import base64

    b64_content = base64.b64encode(content.encode('utf-8')).decode('utf-8')

    existing = _api('GET', f'/repos/{repo}/contents/{path}', params={'ref': branch})
    data: Dict[str, Any] = {
        'message': message,
        'content': b64_content,
        'branch': branch,
    }
    if existing.status_code == 200:
        data['sha'] = existing.json()['sha']

    resp = _api('PUT', f'/repos/{repo}/contents/{path}', json=data)
    if resp.status_code in (200, 201):
        result = resp.json()
        print(f"File '{path}' written: {result['content']['html_url']}")
        return result
    else:
        print(f"Error writing file: {resp.status_code} - {resp.json().get('message', '')}")
        return None


def update_repo_readme(repo: str, content: str, message: str = 'Update README') -> bool:
    """Create or update the README.md in a repository."""
    result = create_or_update_file(repo, 'README.md', content, message)
    return result is not None


# =============================================================================
# ISSUES
# =============================================================================

def create_issue(repo: str, title: str, body: str = '',
                 labels: Optional[List[str]] = None,
                 assignees: Optional[List[str]] = None,
                 token_env: str = 'GITHUB_TOKEN') -> Optional[Dict[str, Any]]:
    """Create an issue.

    Args:
        repo: Full repo name
        title: Issue title
        body: Issue body (markdown)
        labels: List of label names
        assignees: List of usernames to assign
        token_env: Environment variable name for the GitHub token
    """
    data = {'title': title, 'body': body}
    if labels:
        data['labels'] = labels
    if assignees:
        data['assignees'] = assignees

    resp = _api('POST', f'/repos/{repo}/issues', token_env=token_env, json=data)
    if resp.status_code == 201:
        issue = resp.json()
        print(f"Issue created: {issue['html_url']}")
        return issue
    else:
        print(f"Error creating issue: {resp.status_code} - {resp.json().get('message', '')}")
        return None


def list_issues(repo: str, state: str = 'open', labels: Optional[str] = None,
                limit: int = 100, token_env: str = 'GITHUB_TOKEN') -> List[Dict[str, Any]]:
    """List issues for a repo.

    Args:
        repo: Full repo name
        state: 'open', 'closed', or 'all'
        labels: Comma-separated label names to filter
        limit: Max issues to return
        token_env: Environment variable name for the GitHub token
    """
    params = {'state': state, 'per_page': limit}
    if labels:
        params['labels'] = labels

    resp = _api('GET', f'/repos/{repo}/issues', token_env=token_env, params=params)
    if resp.status_code != 200:
        print(f"Error {resp.status_code}: {resp.json().get('message', '')}")
        return []
    return resp.json()


def get_issue(repo: str, issue_number: int, token_env: str = 'GITHUB_TOKEN') -> Optional[Dict[str, Any]]:
    """Get a specific issue."""
    resp = _api('GET', f'/repos/{repo}/issues/{issue_number}', token_env=token_env)
    if resp.status_code != 200:
        return None
    return resp.json()


def get_issue_comments(repo: str, issue_number: int, token_env: str = 'GITHUB_TOKEN') -> List[Dict[str, Any]]:
    """Get all comments for a specific issue."""
    resp = _api('GET', f'/repos/{repo}/issues/{issue_number}/comments', token_env=token_env)
    if resp.status_code != 200:
        return []
    return resp.json()


def update_issue(repo: str, issue_number: int,
                 title: Optional[str] = None,
                 body: Optional[str] = None,
                 state: Optional[str] = None,
                 labels: Optional[List[str]] = None) -> Optional[Dict[str, Any]]:
    """Update an issue.

    Args:
        repo: Full repo name
        issue_number: Issue number
        title: New title (optional)
        body: New body (optional)
        state: 'open' or 'closed' (optional)
        labels: Replace labels (optional)
    """
    data = {}
    if title: data['title'] = title
    if body: data['body'] = body
    if state: data['state'] = state
    if labels is not None: data['labels'] = labels

    resp = _api('PATCH', f'/repos/{repo}/issues/{issue_number}', json=data)
    if resp.status_code == 200:
        print(f"Issue #{issue_number} updated")
        return resp.json()
    else:
        print(f"Error: {resp.status_code}")
        return None


def close_issue(repo: str, issue_number: int) -> bool:
    """Close an issue."""
    result = update_issue(repo, issue_number, state='closed')
    return result is not None


def add_comment(repo: str, issue_number: int, body: str, token_env: str = 'GITHUB_TOKEN') -> Optional[Dict[str, Any]]:
    """Add a comment to an issue."""
    resp = _api('POST', f'/repos/{repo}/issues/{issue_number}/comments',
                token_env=token_env, json={'body': body})
    if resp.status_code == 201:
        return resp.json()
    return None


# =============================================================================
# LABELS
# =============================================================================

def list_labels(repo: str, token_env: str = 'GITHUB_TOKEN') -> List[Dict[str, Any]]:
    """List all labels for a repo."""
    resp = _api('GET', f'/repos/{repo}/labels', token_env=token_env)
    if resp.status_code != 200:
        return []
    return resp.json()


def create_label(repo: str, name: str, color: str = 'ededed',
                 description: str = '') -> Optional[Dict[str, Any]]:
    """Create a label.

    Args:
        repo: Full repo name
        name: Label name
        color: Hex color without # (e.g., 'ff0000')
        description: Label description
    """
    data = {'name': name, 'color': color, 'description': description}
    resp = _api('POST', f'/repos/{repo}/labels', json=data)
    if resp.status_code == 201:
        return resp.json()
    return None


# =============================================================================
# PULL REQUESTS
# =============================================================================

def list_prs(repo: str, state: str = 'open', limit: int = 30) -> List[Dict[str, Any]]:
    """List pull requests."""
    params = {'state': state, 'per_page': limit}
    resp = _api('GET', f'/repos/{repo}/pulls', params=params)
    if resp.status_code != 200:
        return []
    return resp.json()


def get_pr(repo: str, pr_number: int) -> Optional[Dict[str, Any]]:
    """Get a specific pull request."""
    resp = _api('GET', f'/repos/{repo}/pulls/{pr_number}')
    if resp.status_code != 200:
        return None
    return resp.json()


def merge_pr(repo: str, pr_number: int, merge_method: str = 'merge',
             commit_title: Optional[str] = None,
             commit_message: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Merge a pull request.

    Args:
        repo: Full repo name
        pr_number: PR number
        merge_method: 'merge', 'squash', or 'rebase'
        commit_title: Custom commit title (optional)
        commit_message: Custom commit message (optional)
    """
    data = {'merge_method': merge_method}
    if commit_title:
        data['commit_title'] = commit_title
    if commit_message:
        data['commit_message'] = commit_message

    resp = _api('PUT', f'/repos/{repo}/pulls/{pr_number}/merge', json=data)
    if resp.status_code in (200, 201):
        return resp.json()
    else:
        print(f"Error merging PR: {resp.status_code} - {resp.json().get('message', '')}")
        return None


def create_pr(repo: str, title: str, body: str = '',
              head: str = '', base: str = 'main',
              draft: bool = False) -> Optional[Dict[str, Any]]:
    """Create a pull request.

    Args:
        repo: Full repo name
        title: PR title
        body: PR description (markdown)
        head: Head branch (e.g., 'fix/bug-123')
        base: Base branch (default 'main')
        draft: Whether PR is a draft
    """
    data = {
        'title': title,
        'body': body,
        'head': head,
        'base': base,
        'draft': draft
    }
    resp = _api('POST', f'/repos/{repo}/pulls', json=data)
    if resp.status_code == 201:
        pr = resp.json()
        print(f"PR created: {pr['html_url']}")
        return pr
    else:
        print(f"Error creating PR: {resp.status_code} - {resp.json().get('message', '')}")
        return None


# =============================================================================
# SEARCH
# =============================================================================

def search_issues(query: str, limit: int = 30) -> List[Dict[str, Any]]:
    """Search issues/PRs across GitHub.

    Args:
        query: Search query (e.g., 'repo:owner/repo is:issue is:open')
    """
    resp = _api('GET', '/search/issues', params={'q': query, 'per_page': limit})
    if resp.status_code != 200:
        return []
    return resp.json().get('items', [])


def search_code(query: str) -> List[Dict[str, Any]]:
    """Search code across GitHub repos.

    Args:
        query: GitHub code search query (e.g., 'class Foo repo:owner/repo')
    """
    resp = _api('GET', '/search/code', params={'q': query, 'per_page': 30})
    if resp.status_code != 200:
        print(f"Error {resp.status_code}: {resp.json().get('message', '')}")
        return []
    return resp.json().get('items', [])


# =============================================================================
# GISTS
# =============================================================================

def create_gist(files: Dict[str, str], description: str = '',
                public: bool = True) -> Optional[Dict[str, Any]]:
    """Create a new gist.

    Args:
        files: Dict of filename -> content
        description: Gist description
        public: Whether gist is public (default True)
    """
    data = {
        'description': description,
        'public': public,
        'files': {name: {'content': content} for name, content in files.items()}
    }
    resp = _api('POST', '/gists', json=data)
    if resp.status_code == 201:
        gist = resp.json()
        print(f"Gist created: {gist['html_url']}")
        return gist
    else:
        print(f"Error creating gist: {resp.status_code} - {resp.json().get('message', '')}")
        return None


def list_gists(user: Optional[str] = None, limit: int = 30) -> List[Dict[str, Any]]:
    """List gists for user.

    Args:
        user: GitHub username (default: authenticated user)
        limit: Max gists to return
    """
    endpoint = f'/users/{user}/gists' if user else '/gists'
    resp = _api('GET', endpoint, params={'per_page': limit})
    if resp.status_code != 200:
        return []
    return resp.json()


def get_gist(gist_id: str) -> Optional[Dict[str, Any]]:
    """Get a specific gist."""
    resp = _api('GET', f'/gists/{gist_id}')
    if resp.status_code != 200:
        return None
    return resp.json()


def update_gist(gist_id: str, files: Optional[Dict[str, str]] = None,
                description: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Update an existing gist.

    Args:
        gist_id: Gist ID
        files: Dict of filename -> new content (None value to delete a file)
        description: New description
    """
    data = {}
    if description is not None:
        data['description'] = description
    if files is not None:
        data['files'] = {name: {'content': content} if content else None
                        for name, content in files.items()}

    resp = _api('PATCH', f'/gists/{gist_id}', json=data)
    if resp.status_code == 200:
        return resp.json()
    else:
        print(f"Error: {resp.status_code}")
        return None


def delete_gist(gist_id: str) -> bool:
    """Delete a gist."""
    resp = _api('DELETE', f'/gists/{gist_id}')
    return resp.status_code == 204


# =============================================================================
# BRANCHES
# =============================================================================

def get_branch(repo: str, branch: str) -> Optional[Dict[str, Any]]:
    """Get branch info. Returns None if branch doesn't exist."""
    r = _api('GET', f'/repos/{repo}/branches/{branch}')
    if r.status_code == 200:
        return r.json()
    return None


def get_default_branch_sha(repo: str):
    """Get the SHA of the HEAD commit of the default branch.

    Returns:
        Tuple of (sha, branch_name) or (None, branch_name) on error
    """
    repo_data = get_repo(repo)
    if not repo_data:
        return None, 'main'
    default_branch = repo_data.get('default_branch', 'main')
    branch_data = get_branch(repo, default_branch)
    if branch_data:
        return branch_data['commit']['sha'], default_branch
    return None, default_branch


def create_branch(repo: str, branch: str, from_branch: str = None) -> Optional[Dict[str, Any]]:
    """Create a new branch in a repo.

    Args:
        repo: Full repo name
        branch: Name of the new branch
        from_branch: Source branch (default: repo's default branch)
    """
    repo_data = get_repo(repo)
    if not repo_data:
        return None

    source = from_branch or repo_data.get('default_branch', 'main')
    source_data = get_branch(repo, source)
    if not source_data:
        return None

    sha = source_data['commit']['sha']
    r = _api('POST', f'/repos/{repo}/git/refs', json={
        'ref': f'refs/heads/{branch}',
        'sha': sha
    })
    if r.status_code == 201:
        return r.json()
    return None


# =============================================================================
# GITHUB PAGES
# =============================================================================

def enable_pages(repo: str, branch: str = 'main', path: str = '/') -> Optional[Dict[str, Any]]:
    """Enable GitHub Pages for a repository.

    Args:
        repo: Full repo name
        branch: Branch to deploy from (default 'main')
        path: Path within branch ('/' for root, '/docs' for docs folder)
    """
    data = {'source': {'branch': branch, 'path': path}}
    resp = _api('POST', f'/repos/{repo}/pages', json=data)
    if resp.status_code not in (200, 201):
        resp = _api('GET', f'/repos/{repo}/pages')
        if resp.status_code == 200:
            return resp.json()
        print(f"Error: {resp.status_code} - {resp.text}")
        return None
    return resp.json()


def enable_pages_workflow(repo: str) -> Dict[str, Any]:
    """Enable GitHub Pages with GitHub Actions as build source."""
    resp = _api('POST', f'/repos/{repo}/pages', json={'build_type': 'workflow'})
    if resp.status_code in (200, 201):
        return resp.json()
    if resp.status_code in (409, 422):
        resp2 = _api('PUT', f'/repos/{repo}/pages', json={'build_type': 'workflow'})
        if resp2.status_code in (200, 201, 204):
            return resp2.json() if resp2.content else {'status': 'updated'}
        return {'error': f"{resp2.status_code} - {resp2.json().get('message', '')}"}
    return {'error': f"{resp.status_code} - {resp.json().get('message', '')}"}


def get_pages(repo: str) -> Optional[Dict[str, Any]]:
    """Get GitHub Pages configuration for a repo."""
    resp = _api('GET', f'/repos/{repo}/pages')
    if resp.status_code == 200:
        return resp.json()
    return None


def set_pages_custom_domain(repo: str, cname: str) -> bool:
    """Set custom domain for GitHub Pages."""
    resp = _api('PUT', f'/repos/{repo}/pages', json={'cname': cname})
    if resp.status_code in (200, 201, 204):
        return True
    print(f"Pages domain error: {resp.status_code} - {resp.json().get('message', '')}")
    return False


def enable_pages_https(repo: str) -> Optional[Dict[str, Any]]:
    """Enable HTTPS enforcement for GitHub Pages."""
    resp = _api('PUT', f'/repos/{repo}/pages', json={'https_enforced': True})
    if resp.status_code not in (200, 204):
        print(f"Error enabling HTTPS: {resp.status_code}")
        return None
    return get_pages(repo)


# =============================================================================
# DEPLOY KEYS
# =============================================================================

def add_deploy_key(repo: str, title: str, key: str, read_only: bool = True) -> Optional[Dict[str, Any]]:
    """Add a deploy key to a repository.

    Args:
        repo: Full repo name
        title: Descriptive name for the key
        key: SSH public key string
        read_only: If False, key gets write access (default True)
    """
    data = {'title': title, 'key': key, 'read_only': read_only}
    resp = _api('POST', f'/repos/{repo}/keys', json=data)
    if resp.status_code == 201:
        return resp.json()
    print(f"Error {resp.status_code}: {resp.json().get('message', resp.text)}")
    return None


def list_deploy_keys(repo: str) -> List[Dict[str, Any]]:
    """List all deploy keys for a repository."""
    resp = _api('GET', f'/repos/{repo}/keys')
    if resp.status_code == 200:
        return resp.json()
    return []


# =============================================================================
# USER & SSH KEYS
# =============================================================================

def get_authenticated_user() -> Optional[Dict[str, Any]]:
    """Get info about the authenticated user."""
    resp = _api('GET', '/user')
    if resp.status_code != 200:
        return None
    return resp.json()


def add_user_ssh_key(title: str, key: str) -> Optional[Dict[str, Any]]:
    """Add an SSH public key to the authenticated user's GitHub account."""
    resp = _api('POST', '/user/keys', json={'title': title, 'key': key})
    if resp.status_code == 201:
        return resp.json()
    print(f"Error {resp.status_code}: {resp.json().get('message', resp.text)}")
    return None


def list_user_ssh_keys() -> List[Dict[str, Any]]:
    """List all SSH public keys for the authenticated user."""
    resp = _api('GET', '/user/keys')
    if resp.status_code == 200:
        return resp.json()
    return []


# =============================================================================
# NOTIFICATIONS
# =============================================================================

def list_notifications(repo: Optional[str] = None, all: bool = False,
                       participating: bool = False, per_page: int = 50,
                       token_env: str = 'GITHUB_TOKEN') -> List[Dict[str, Any]]:
    """List GitHub notifications, optionally filtered by repo.

    Args:
        repo: Full repo name to filter (None = all repos)
        all: Include read notifications (default False = unread only)
        participating: Only participating (default False)
        per_page: Max results (default 50)
    """
    endpoint = f'/repos/{repo}/notifications' if repo else '/notifications'
    params = {'all': str(all).lower(), 'participating': str(participating).lower(), 'per_page': per_page}
    resp = _api('GET', endpoint, token_env=token_env, params=params)
    if resp.status_code == 200:
        return resp.json()
    return []


def mark_notification_read(thread_id: str, token_env: str = 'GITHUB_TOKEN') -> bool:
    """Mark a single notification thread as read."""
    resp = _api('PATCH', f'/notifications/threads/{thread_id}', token_env=token_env)
    return resp.status_code in (200, 205)


# =============================================================================
# WORKFLOWS
# =============================================================================

def list_workflow_runs(repo: str, workflow: str = None, limit: int = 5) -> List[Dict[str, Any]]:
    """List recent workflow runs for a repo.

    Args:
        repo: Full repo name
        workflow: Workflow file name (e.g., 'deploy.yml') or None for all
        limit: Max runs to return
    """
    if workflow:
        endpoint = f'/repos/{repo}/actions/workflows/{workflow}/runs'
    else:
        endpoint = f'/repos/{repo}/actions/runs'
    resp = _api('GET', endpoint, params={'per_page': limit})
    if resp.status_code == 200:
        return resp.json().get('workflow_runs', [])
    return []


# =============================================================================
# CONVENIENCE
# =============================================================================

def quick_issue(repo: str, title: str, body: str = '') -> str:
    """Create issue and return URL (or error message)."""
    issue = create_issue(repo, title, body)
    if issue:
        return issue['html_url']
    return "Failed to create issue"


if __name__ == '__main__':
    user = get_authenticated_user()
    if user:
        print(f"Authenticated as: {user['login']}")
        repos = list_repos(limit=5)
        print(f"First 5 repos: {[r['name'] for r in repos]}")
    else:
        print("Authentication failed")
