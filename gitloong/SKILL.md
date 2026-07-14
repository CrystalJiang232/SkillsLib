---
name: gitloong
description: >
  Fetch unresolved, code-tied merge request review comments from a self-managed
  GitLab instance (点墨成龙). Automates the full pipeline: detect open MR from
  current git branch, authenticate via token, retrieve discussion threads via
  GitLab API, filter to unresolved inline comments only, and write structured
  JSON for downstream agent consumption. Use when the task involves: (1) Pulling
  pending MR review comments from GitLab, (2) Preparing code review context for
  an agent to act upon, (3) Checking unresolved feedback on a merge request,
  (4) Any workflow where a coding agent needs to see what reviewers have
  requested before resolving comments. Triggers on git repositories with GitLab
  remotes and open merge requests.
---

# GitLoong (点墨成龙)

Fetch unresolved, code-tied review comments from a GitLab merge request and
write them as structured JSON for downstream agent processing.

## Workflow

1. Verify credentials (`auth.json` in skill directory)
2. Derive GitLab URL and project path from `git remote get-url origin`
3. Detect open MR from current branch
4. Fetch all discussion threads via GitLab API
5. Filter to unresolved, code-tied (position-linked) threads
6. Write JSON output file

## Prerequisites

- `git` repo with a GitLab `origin` remote (HTTPS or SSH)
- `curl` and `python3` available in environment
- GitLab Personal Access Token with `read_api` scope

## Credential Setup

Locate `auth.json` in this skill's directory (beside `SKILL.md`).

If absent or the token is invalid:

1. Copy `auth.json.template` to `auth.json`
2. Replace the placeholder with a real token:
   ```json
   {"gitlab_token": "glpat-xxxxxxxxxxxxxxxxxxxx"}
   ```
3. Obtain a token from: User Settings → Access Tokens → Add new token
   (scope: `read_api`)

If in-session credential entry is needed, write the file directly. Do not use
environment variables.

## Core Script

Run `scripts/fetch_comments.py` from within the target git repository:

```bash
cd /path/to/repo
python3 /path/to/GitLoong/scripts/fetch_comments.py [--output PATH]
```

Options:
| Flag | Default | Purpose |
|------|---------|---------|
| `--output` | `gitloong_comments.json` | Output JSON file path |
| `--test-auth` | — | Verify token and connectivity only, then exit |

Exit codes for programmatic handling:
| Code | Meaning |
|------|---------|
| 0 | Success (or `--test-auth` passed) |
| 1 | Auth/config error — check `auth.json` token |
| 2 | Git repo error — not in a repo or no origin remote |
| 3 | MR detection error — no open MR or ambiguous match |
| 4 | API/network error — check GitLab availability |
| 5 | Output/write error |

## What the Script Does

### 1. Read auth.json
Reads `gitlab_token` from `auth.json` in the skill directory. Halts with
instructions if missing, unreadable, or token is empty.

### 2. Parse Git Remote
Runs `git remote get-url origin` to extract:
- **GitLab base URL**: `https://gitlab.company.com`
- **Project path**: `group/project`

Supports HTTPS (`https://host/path`) and SSH (`git@host:path`) formats.

### 3. Detect Open MR
Uses current branch name (`git branch --show-current`) to query:
```
GET /api/v4/projects/:id/merge_requests?source_branch=...&state=opened
```

**If zero matches**: Halt. Prompt user to confirm the branch has an open MR.
**If more than one match**: Halt. Present the MR list and ask user to resolve
ambiguity.

### 4. Fetch Discussions
```
GET /api/v4/projects/:id/merge_requests/:iid/discussions
```
Retrieves all discussion threads (server does not filter by resolved status).

### 5. Filter: Unresolved + Code-Tied
Applies two filters client-side:

- **Unresolved**: `discussion.resolved == false`
- **Code-tied**: at least one note has a non-null `position` field
  (indicating an inline/diff-level comment, not general discussion)

Threads failing either filter are excluded.

### 6. Write JSON Output

Writes a single JSON file with this structure:

```json
{
  "meta": {
    "project_path": "group/project",
    "mr_iid": 5,
    "mr_title": "Add feature X",
    "mr_web_url": "https://gitlab.company.com/group/project/-/merge_requests/5",
    "source_branch": "feature-branch",
    "target_branch": "main",
    "fetched_at": "2026-06-08T12:00:00+00:00",
    "gitlab_url": "https://gitlab.company.com",
    "total_unresolved_code_threads": 2,
    "total_discussions_checked": 8
  },
  "threads": [
    {
      "discussion_id": "...",
      "resolved": false,
      "created_at": "2026-06-01T10:00:00.000Z",
      "notes": [
        {
          "note_id": 100,
          "author": "reviewer",
          "body": "Consider extracting this into a helper function",
          "created_at": "2026-06-01T10:00:00.000Z",
          "updated_at": "2026-06-01T10:00:00.000Z",
          "position": {
            "base_sha": "abc...",
            "head_sha": "def...",
            "start_sha": "abc...",
            "old_path": "src/module.py",
            "new_path": "src/module.py",
            "position_type": "text",
            "new_line": 42,
            "old_line": null,
            "line_range": null
          }
        }
      ]
    }
  ]
}
```

### 7. Console Summary
Prints a human-readable summary of unresolved threads, including file paths and
line numbers for quick scanning.

## Extending the Filter

The filtering logic lives in `filter_unresolved_code_threads()` within the
script. To add additional criteria (e.g., exclude comments from certain authors,
include resolved threads, add date filters), modify that function.

The `references/gitlab-api.md` file contains the full API response schema for
discussion and position objects to guide extensions.

## Manual Override (Future Extension)

If auto-detect fails or a specific MR is needed without switching branches, the
script can be extended to accept `--mr-iid` and `--branch` flags to bypass
detection. These flags are not currently implemented — the workflow expects the
agent to be on the correct branch.

## Resources

- **API reference**: See `references/gitlab-api.md` for endpoint details,
  response schemas, and filtering rules.
