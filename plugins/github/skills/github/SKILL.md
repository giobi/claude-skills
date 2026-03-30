---
name: github
description: "GitHub — repos, issues, PRs, gists via API"
user-invocable: true
argument-hint: "[repos | issues <repo> | pr <repo> | crea repo | crea issue | gist]"
requires:
  env:
    - GITHUB_TOKEN
  packages:
    - requests
    - python-dotenv
---

# /github — GitHub Manager

Gestisci repository, issue, PR e gist tramite GitHub API.

## Setup

```
GITHUB_TOKEN=ghp_xxxxxxxxxxxx  # Personal access token, scope: repo
```

## Wrapper

```python
import sys
sys.path.insert(0, '.claude/skills/github')
from github import (
    list_repos, get_repo, create_repo, delete_repo,
    get_file_contents,
    create_issue, list_issues, get_issue, update_issue, close_issue, add_comment,
    list_prs, get_pr, merge_pr, create_pr,
    create_gist, list_gists, get_gist, update_gist, delete_gist,
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
elif any(w in args for w in ["file", "leggi", "read", "contents"]):
    intent = "file_contents"
else:
    intent = "list_repos"  # default
```

## Comandi principali

### Repos
- `/github repos` — lista tutti i repos dell'account
- `/github repo owner/name` — dettaglio repo (star, fork, lingua, ultimo push)
- `/github crea repo nome [--private]` — crea nuovo repo

### Issues
- `/github issues owner/repo` — lista issue aperte
- `/github crea issue owner/repo "titolo" [body]` — crea issue
- `/github chiudi issue owner/repo #42` — chiudi issue
- `/github commenta owner/repo #42 "testo"` — aggiungi commento

### Pull Requests
- `/github pr owner/repo` — lista PR aperte
- `/github merge owner/repo #42` — mergia PR
- `/github crea pr owner/repo title base:head` — crea PR

### Gist
- `/github gist` — lista gist
- `/github crea gist filename.py "contenuto"` — crea gist pubblico/privato

## Output atteso

### `/github repos`
```
Repositories (23)

⭐ brain              Python   last push: 2 ore fa      private
   claude-skills     -        last push: 1 giorno fa    public
   rankpilot         PHP      last push: 3 giorni fa    private
```

### `/github issues owner/repo`
```
Issues aperte — owner/repo (5)

#42  Bug nel parser YAML         [bug]          opened 2gg fa
#38  Feature: export CSV         [enhancement]  opened 5gg fa
```

## Note

- `GITHUB_TOKEN` deve avere scope `repo` per repos privati
- Per org operations usa `list_repos(org='nome-org')`
- Il wrapper auto-legge `.env` dalla root del brain
