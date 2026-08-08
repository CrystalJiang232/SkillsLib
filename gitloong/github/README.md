# GitLoong — GitHub Provider (github.com)

Use `scripts/fetch_pr_comments.py` from this directory. The script is
intentionally quiet: rely on exit codes and JSON output.

## Scope

- GitHub.com only (both remotes must be `github.com`; GitHub Enterprise is not
  supported).
- Fork workflow only: `origin` is the private/source fork, and the single
  non-origin remote is the base repository that owns the pull request.
- Code-tied review threads use GraphQL and keep GitLab-like "unresolved"
  semantics via `isResolved`.
- Non-code issue comments are fetched but are not analyzed by default; analyze
  them only when the user explicitly requests it.

## Error-Prone Policy

Strict workflow: if any precondition or validation step fails, halt and ask the
user to check or provide the missing information. Do not invent remotes, guess
PR numbers, switch repositories, change URLs, retry with alternate auth styles,
or apply spontaneous workarounds. Troubleshooting probes are allowed only after
the main command fails, and only to explain the failure.

## PR Number Gate

Before every invocation, ask the user for the target-repository PR number and
halt until the user explicitly provides it. Do not infer, retain, or reuse a PR
number from an earlier message, artifact, command history, or configuration
file. Pass only that explicit value through `--pr-number`.

## Required Config

Create `config.json` in this directory:

```json
{
    "github_token": "",
    "drop_thread_contains_user": []
}
```

- `github_token`: GitHub token with read access to the target repository.
  Use a fine-grained personal access token with **Pull requests: Read**
  repository permission (Metadata read is implied), or a classic token with
  the `repo` scope.
- `drop_thread_contains_user`: optional usernames (GitHub logins). Any thread
  containing a comment from one of these users is excluded.

No other keys are allowed.

## Invocation

```bash
python3.11 /path/to/gitloong/github/scripts/fetch_pr_comments.py --pr-number <user-provided-number> --output .agent/tmp/github_pr_comments.json
```

Use `python3.11` or another Python 3.10+ interpreter. Keep output under
`.agent/tmp/` unless the user explicitly asks for another path.

Exit codes:

| Code | Meaning |
| --- | --- |
| 0 | JSON written |
| 1 | missing or invalid config |
| 2 | invalid invocation or git remote layout is not `origin` plus one target remote |
| 3 | PR missing, not open, merged, or source/target repository mismatch |
| 4 | GitHub API, GraphQL, or network failure |
| 5 | output write failure |

## Workflow Contract

1. Obtain the explicit user-provided PR number and pass it through
   `--pr-number`.
2. Read `config.json` in this directory.
3. Inspect `git remote` only.
4. Require exactly two remotes, one named `origin` and one target remote, both
   on `github.com`.
5. Derive `owner/repo` from the remotes: `origin` is the source fork, the other
   remote is the target/base repository.
6. Fetch the target-repository pull request identified by `--pr-number`.
7. Continue only if the PR is open, not merged, its head repository matches the
   `origin` remote, and its base repository matches the target remote.
8. Fetch code-tied review threads via GraphQL, keep unresolved threads
   (`isResolved == false`), apply `drop_thread_contains_user`, drop Jenkins-only
   threads, and write JSON.
9. Fetch non-code issue comments into `non_code_comments`. Do not analyze them
   in the default pipeline; analyze only on explicit user request.

Failure handling:

- Missing `config.json` or token, or a missing/invalid `--pr-number`: stop and
  ask the user.
- Remote layout not exactly `origin` plus one target remote, or any remote off
  `github.com`: stop and ask the user to confirm the repository setup.
- PR missing, closed, merged, or source/target repository mismatch: stop and
  ask the user to recheck the supplied PR number, remotes, and ownership.
- API/GraphQL/network failure: stop. Do not silently switch protocols or auth
  methods; use the troubleshooting probes below only if needed.

## Troubleshooting Commands

Run these only after the main invocation fails. Redact tokens in all summaries.

Remote layout:

```bash
git remote -v
```

Repository and PR access with the primary token style:

```bash
curl -sS -X GET -H "Authorization: Bearer <redacted>" -H "X-GitHub-Api-Version: 2022-11-28" "https://api.github.com/repos/GROUP%2FPROJECT"
curl -sS -X GET -H "Authorization: Bearer <redacted>" -H "X-GitHub-Api-Version: 2022-11-28" "https://api.github.com/repos/GROUP%2FPROJECT/pulls/<PR_NUMBER>"
```

## Provider Differences (GitHub vs GitLab)

- PR numbers replace MR IIDs; PR `state` is `open`/`closed` and `merged` is a
  separate flag.
- Review threads and their resolved state exist only in GraphQL
  (`pullRequest.reviewThreads`, `isResolved`, `isOutdated`); the REST review
  comment list is flat with no thread or resolution metadata.
- GitHub has no system notes; comments may be minimized (`minimized`), which is
  reported on non-code comments.
- Non-code discussion is a flat issue-comment list, not threads.
