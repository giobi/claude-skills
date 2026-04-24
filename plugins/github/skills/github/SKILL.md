---
name: github
description: "GitHub — repos, issues, PRs, gists, Pages, branches via API"
user-invocable: true
argument-hint: "[repos | issues <repo> | pr <repo> | crea repo | crea issue | gist | pages <repo>]"
requires:
  env:
    - GITHUB_TOKEN
  packages:
    - requests
    - python-dotenv
---

# /github — GitHub Manager

Manage repositories, issues, pull requests, gists, GitHub Pages, branches, deploy keys, and notifications via GitHub API.

## Setup

```
GITHUB_TOKEN=ghp_xxxxxxxxxxxx  # Personal access token, scope: repo
```

For multi-account setups (e.g. bot accounts, org tokens), add additional env vars and pass `token_env='YOUR_OTHER_TOKEN'` to any function.

## Wrapper

```python
import sys
sys.path.insert(0, '.claude/skills/github')
from github import (
    # Repos
    list_repos, get_repo, create_repo, delete_repo,
    set_repo_topics, search_repos,
    # Files
    get_file_contents, get_file_sha, create_or_update_file, update_repo_readme,
    # Issues
    create_issue, list_issues, get_issue, get_issue_comments,
    update_issue, close_issue, add_comment,
    # Labels
    list_labels, create_label,
    # Pull Requests
    list_prs, get_pr, merge_pr, create_pr,
    # Search
    search_issues, search_code,
    # Gists
    create_gist, list_gists, get_gist, update_gist, delete_gist,
    # Branches
    get_branch, get_default_branch_sha, create_branch,
    # Pages
    enable_pages, enable_pages_workflow, get_pages,
    set_pages_custom_domain, enable_pages_https,
    # Deploy Keys
    add_deploy_key, list_deploy_keys,
    # User
    get_authenticated_user, add_user_ssh_key, list_user_ssh_keys,
    # Notifications
    list_notifications, mark_notification_read,
    # Workflows
    list_workflow_runs,
    # Convenience
    quick_issue,
)
```

## Intent Detection

```python
args = "$ARGUMENTS".strip().lower()

if any(w in args for w in ["repos", "repository", "lista repo"]):
    intent = "list_repos"
elif any(w in args for w in ["crea repo", "new repo", "nuovo repo"]):
    intent = "create_repo"
elif any(w in args for w in ["issue", "issues", "bug", "ticket"]):
    intent = "issues"
elif any(w in args for w in ["pr", "pull request", "merge"]):
    intent = "prs"
elif any(w in args for w in ["gist", "snippet", "paste"]):
    intent = "gists"
elif any(w in args for w in ["page", "pages", "deploy"]):
    intent = "pages"
elif any(w in args for w in ["branch", "ramo"]):
    intent = "branches"
elif any(w in args for w in ["notification", "notifiche"]):
    intent = "notifications"
elif any(w in args for w in ["file", "leggi", "read", "contents"]):
    intent = "file_contents"
else:
    intent = "list_repos"  # default
```

## Commands

### Repos
- `/github repos` — list all repos
- `/github repo owner/name` — repo details (stars, forks, language, last push)
- `/github crea repo name [--private]` — create new repo
- `/github search query` — search repos

### Issues
- `/github issues owner/repo` — list open issues
- `/github crea issue owner/repo "title" [body]` — create issue
- `/github chiudi issue owner/repo #42` — close issue
- `/github commenta owner/repo #42 "text"` — add comment

### Pull Requests
- `/github pr owner/repo` — list open PRs
- `/github merge owner/repo #42` — merge PR
- `/github crea pr owner/repo title base:head` — create PR

### Gists
- `/github gist` — list gists
- `/github crea gist filename.py "content"` — create gist

### Pages
- `/github pages owner/repo` — get Pages status
- `/github pages enable owner/repo` — enable Pages
- `/github pages domain owner/repo example.com` — set custom domain

### Branches
- `/github branch owner/repo name` — create branch
- `/github branch info owner/repo main` — branch details

### Notifications
- `/github notifiche` — list unread notifications

## Expected Output

### `/github repos`
```
Repositories (23)

  brain              Python   last push: 2h ago       private
  claude-skills      -        last push: 1 day ago    public
  my-project         PHP      last push: 3 days ago   private
```

### `/github issues owner/repo`
```
Open issues — owner/repo (5)

#42  YAML parser bug              [bug]          opened 2d ago
#38  Feature: export CSV          [enhancement]  opened 5d ago
```

## Notes

- `GITHUB_TOKEN` needs `repo` scope for private repos
- For org operations use `list_repos(org='org-name')`
- The wrapper auto-reads `.env` from the brain root
- All functions accept `token_env` parameter for multi-account setups
