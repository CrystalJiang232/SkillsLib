---
name: gitloong
description: >
  Fetch unresolved review discussions from GitLab merge requests (by MR IID)
  or GitHub pull requests (by PR number) in a fork workflow where origin is
  the private/source remote and one additional remote is the target
  repository. Before invoking or editing, read the provider contract in the
  matching directory (gitlab/README.md or github/README.md) and use that
  provider's script; never assume one provider's API behavior from the other.
---

# GitLoong

GitLoong fetches unresolved review discussions from either provider:

- **GitLab**: MR threads via `gitlab/scripts/fetch_comments.py --mr-iid`.
- **GitHub.com**: PR review threads via `github/scripts/fetch_pr_comments.py
  --pr-number`.

Both scripts are intentionally quiet: rely on exit codes and JSON output.
The default behavior after fetching is proposal and clarification, not
implementation.

## Required Reading Before Invocation or Edit

Read the provider contract completely before invoking its script or editing
anything under that provider directory:

| Provider | Contract to read | Script to use |
| --- | --- | --- |
| GitLab | `gitlab/README.md` | `gitlab/scripts/fetch_comments.py` (`--mr-iid`) |
| GitHub | `github/README.md` | `github/scripts/fetch_pr_comments.py` (`--pr-number`) |

The provider READMEs hold the authoritative API details, config schema,
troubleshooting probes, and provider-specific rules. Do not mix provider
conventions (auth headers, IDs, state values, output fields) between the two.

## Error-Prone Policy

Strict workflow for both providers. If any precondition or validation step
fails, halt and ask the user to check or provide the missing information. Do
not invent remotes, guess MR IDs or PR numbers, switch projects or
repositories, change URLs, retry with alternate auth styles, or apply
spontaneous workarounds. Troubleshooting probes are allowed only after the main
command fails, and only to explain the failure.

## ID Gate (MR IID / PR Number)

Before every invocation, ask the user for the target-project MR IID (GitLab) or
PR number (GitHub) and halt until the user explicitly provides it. Do not
infer, retain, or reuse an ID from an earlier message, artifact, command
history, or configuration file. Pass only that explicit value through
`--mr-iid` or `--pr-number`.

## Required Config

One config file per provider, stored in the provider directory. Create it from
the matching template before first use.

- `gitlab/config.json`: `gitlab_token`, `drop_thread_contains_user`.
- `github/config.json`: `github_token`, `drop_thread_contains_user`.

Tokens need API read access to the target repository:

- GitLab: token with API read access (`PRIVATE-TOKEN` header).
- GitHub: fine-grained personal access token with **Pull requests: Read**
  repository permission (Metadata read is implied), or a classic token with the
  `repo` scope (`Authorization: Bearer` header).

## Invocation

GitLab:

```bash
python3.11 /path/to/gitloong/gitlab/scripts/fetch_comments.py --mr-iid <user-provided-iid> --output .agent/tmp/gitloong_comments.json
```

GitHub:

```bash
python3.11 /path/to/gitloong/github/scripts/fetch_pr_comments.py --pr-number <user-provided-number> --output .agent/tmp/github_pr_comments.json
```

Use `python3.11` or another Python 3.10+ interpreter. Keep output under
`.agent/tmp/` unless the user explicitly asks for another path.

Exit codes (shared by both providers):

| Code | Meaning |
| --- | --- |
| 0 | JSON written |
| 1 | missing or invalid config |
| 2 | invalid invocation or git remote layout is not `origin` plus one target remote |
| 3 | MR/PR missing, not open, or source/target repository mismatch |
| 4 | provider API or network failure |
| 5 | output write failure |

## Workflow Contract

1. Obtain the explicit user-provided MR IID or PR number and pass it through
   the provider flag.
2. Read the provider `config.json`.
3. Inspect `git remote` only.
4. Require exactly two remotes, one named `origin` and one target remote
   (GitHub additionally requires both remotes on `github.com`).
5. Derive source and target repositories from the remotes; `origin` is the
   source fork, the other remote is the target.
6. Fetch the target-repository MR/PR identified by the user-provided ID.
7. Continue only if the MR/PR exists, is open, and its source repository
   matches `origin` (and, for GitHub, its base repository matches the target
   remote).
8. Fetch review discussions/threads, keep unresolved ones, apply
   `drop_thread_contains_user`, drop Jenkins-only discussions, and write JSON.
9. For GitHub only, fetch non-code issue comments into `non_code_comments`;
   do not analyze them in the default pipeline.

Failure handling:

- Missing or invalid config, or a missing/invalid ID: stop and ask the user.
- Remote layout not exactly `origin` plus one target remote: stop and ask the
  user to confirm the repository setup.
- MR/PR missing, closed, merged, or source repository mismatch: stop and ask
  the user to recheck the supplied ID, remotes, and repository ownership.
- Provider API/network failure: stop. Do not silently switch protocols or auth
  methods; use the provider README troubleshooting probes only if needed.

## Non-Code Discussion Rule

- **GitLab**: unresolved discussions are kept whether code-tied or not; both
  types are analyzed in the default pipeline (provider-native behavior).
- **GitHub**: code-tied threads are analyzed by default; non-code issue
  comments are fetched into `non_code_comments` but analyzed only when the
  user explicitly requests it.

## Default Pipeline (Comments)

For ordinary MR/PR comment workflows, use a persistent subagent pipeline by
default when subagents are available:

1. Fetch subagent: run only the strict fetch workflow above and write the JSON
   artifact under `.agent/tmp/`.
2. Proposal subagent: inspect the fetched comments against local code and
   produce modification proposals only. Do not edit code in this phase. Include
   options, trade-offs, default behavior, and clarification points awaiting
   human confirmation.
3. Cross-verification subagent: independently verify the proposal against local
   code, project patterns, and any relevant docs. Mark each proposal confirmed,
   qualified, or rejected before the parent agent reports or implements it.

The default behavior after fetching comments is proposal and clarification, not
implementation. Enter a decision phase with the user after proposals and
cross-verification are available; present trade-offs, default recommendations,
and any unresolved questions. Do not edit code, generated source, or project
configuration to address review comments unless the user explicitly grants
implementation permission for the specific follow-up.

If subagents are unavailable, decay to the same phases in-session and clearly
state that the pipeline was executed without separate agents. User instructions
can override the default pipeline, for example `fetch only`, `extra
cross-verification`, `skip proposals`, or `edit code after confirmation`.

Review comments skeptically for both providers: do not rush to accept or deny
them. Compare each comment against local code, behavior, project constraints,
and viable alternatives before recommending action.
Clarification artifacts should prefer this compact shape: location, code
segment, original review comment, agent analysis, options/trade-offs, default
behavior, and `[ ] Human review:` space.

## Foreign MR/PR Code Changes

The GitLab provider offers a foreign-MR code-changes subskill
(`gitlab/scripts/fetch_mr_changes.py`, `--mr-iid`) for inspecting diffs of a
target-project MR whose source project may differ from local `origin`. See
`gitlab/README.md` for its contract, config, and review-phase gates. GitHub has
no equivalent subskill yet.
