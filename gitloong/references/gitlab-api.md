# GitLab API Reference — Merge Request Discussions

## Table of Contents
- [Authentication](#authentication)
- [Find Open MR by Branch](#find-open-mr-by-branch)
- [List MR Discussions](#list-mr-discussions)
- [Discussion Object Structure](#discussion-object-structure)
- [Position Object (Code-Tied)](#position-object-code-tied)

---

## Authentication

All requests require a **Personal Access Token** via header:

```
PRIVATE-TOKEN: <token>
```

Token scope: `read_api` (minimum)

## Find Open MR by Branch

```
GET /api/v4/projects/:id/merge_requests?source_branch=:branch&state=opened
```

Parameters:
| Param | Description |
|-------|-------------|
| `:id` | URL-encoded project path (`group%2Fproject`) or numeric project ID |
| `source_branch` | Exact branch name |
| `state` | `opened` |

Returns array of MR objects. Expect 1 match for auto-detect.

Response fields used:
- `iid` — MR number (use this for subsequent calls)
- `title`, `web_url`, `source_branch`, `target_branch`

## List MR Discussions

```
GET /api/v4/projects/:id/merge_requests/:merge_request_iid/discussions
```

Returns array of discussion objects.

**Key behavior**: No server-side filter for unresolved. Fetch all, then filter client-side by `resolved == false`.

Pagination: Use `per_page=100` (max). For >100 discussions, implement cursor pagination via `X-Next-Page` headers. (Rare for typical MRs.)

## Discussion Object Structure

```json
{
  "id": "abc123...",
  "individual_note": false,
  "notes": [
    {
      "id": 100,
      "body": "Rename this variable to something clearer",
      "author": { "username": "reviewer" },
      "created_at": "2026-06-01T12:00:00.000Z",
      "updated_at": "2026-06-01T12:00:00.000Z",
      "resolved": false,
      "position": {
        "base_sha": "abc...",
        "head_sha": "def...",
        "start_sha": "abc...",
        "old_path": "src/main.py",
        "new_path": "src/main.py",
        "position_type": "text",
        "new_line": 42,
        "old_line": null,
        "line_range": null
      }
    }
  ],
  "resolved": false
}
```

Filtering rules:
- **Unresolved**: `discussion.resolved == false`
- **Code-tied**: at least one note has a non-null `position` field
- Threads without `position` are general MR discussion, not line-level review

## Position Object (Code-Tied)

Only present for diff-level (inline) comments.

| Field | Meaning |
|-------|---------|
| `old_path` | File path in base branch |
| `new_path` | File path in head branch |
| `new_line` | Line number in the new file (head) |
| `old_line` | Line number in the old file (base) |
| `position_type` | `"text"` for text diffs |
| `base_sha` | Base commit SHA |
| `head_sha` | Head commit SHA |
| `start_sha` | Start SHA for multi-line comments |
| `line_range` | Range info for multi-line comments (may be null) |
