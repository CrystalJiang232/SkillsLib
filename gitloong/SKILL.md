---
name: gitloong
description: >
  Fetch unresolved GitLab merge request discussions from a self-managed
  GitLab fork workflow. Use when a repo has origin as the private/source remote
  and one additional remote as the upstream/target project, and the agent needs
  structured unresolved MR review comments for follow-up processing.
---

# GitLoong

Use `scripts/fetch_comments.py` from the target git repository. The script is
intentionally quiet: rely on exit codes and JSON output.

## Error-Prone Policy

This workflow is strict. If any precondition or validation step fails, halt and
ask the user to check or provide the missing information. Do not invent remotes,
guess MR IDs, switch projects, change URLs, retry with alternate auth styles, or
apply spontaneous workarounds. Troubleshooting probes are allowed only after the
main command fails, and only to explain the failure.

## MR IID Gate

Before every invocation of either script, ask the user for the target-project
MR IID and halt until the user explicitly provides it. Do not infer, retain, or
reuse an IID from an earlier message, artifact, command history, or
configuration file. Pass only that explicit value through `--mr-iid`.

## Required Config

Create `config.json` beside this `SKILL.md`:

```json
{
    "gitlab_token": "",
    "drop_thread_contains_user": [
        "xiaozhou"
    ]
}
```

- `gitlab_token`: GitLab token with API read access.
- `drop_thread_contains_user`: optional usernames. Any thread containing a note
  from one of these users is excluded.

## Invocation

```bash
python3.11 /path/to/gitloong/scripts/fetch_comments.py --mr-iid <user-provided-iid> --output .agent/tmp/gitloong_comments.json
```

Use `python3.11` or another Python 3.10+ interpreter. Keep output under
`.agent/tmp/` unless the user explicitly asks for another path.

Exit codes:

| Code | Meaning |
| --- | --- |
| 0 | JSON written |
| 1 | missing or invalid config |
| 2 | invalid invocation or git remote layout is not `origin` plus one target remote |
| 3 | MR missing, not open, or source/target project mismatch |
| 4 | GitLab API or network failure |
| 5 | output write failure |

## Workflow Contract

1. Obtain the explicit user-provided MR IID and pass it through `--mr-iid`.
2. Read `config.json`.
3. Inspect `git remote` only.
4. Require exactly two remotes, one named `origin` and one target remote.
5. Derive source project from `origin`; derive target project and GitLab base URL
   from the other remote.
6. Fetch the target-project MR identified by `--mr-iid`.
7. Continue only if the MR exists, is open, and its `source_project_id` matches
   the source project.
8. Fetch MR discussions, keep unresolved threads whether code-tied or not,
   apply `drop_thread_contains_user`, drop Jenkins-only discussions, and write
   JSON.

Failure handling:

- Missing `config.json` or token, or a missing/invalid `--mr-iid`: stop and ask
  the user.
- Remote layout not exactly `origin` plus one target remote: stop and ask the
  user to confirm the repository setup.
- MR missing, closed, merged, or source project mismatch: stop and ask the user
  to recheck the supplied MR IID, remotes, and branch/project ownership.
- GitLab/API/network failure: stop. Do not silently switch protocols or auth
  methods; use the troubleshooting commands below only if needed.

## Troubleshooting Commands

Run these only after the main invocation fails. Redact tokens in all summaries.

Remote layout:

```bash
git remote -v
```

Check HTTP/HTTPS service behavior:

```bash
curl -I --connect-timeout 8 http://GITLAB_HOST
curl -I --connect-timeout 8 https://GITLAB_HOST
```

Project access with the primary token style:

```bash
curl -sS -X GET -H "PRIVATE-TOKEN: <redacted>" "http://GITLAB_HOST/api/v4/projects/GROUP%2FPROJECT"
```

MR lookup under the target project:

```bash
curl -sS -X GET -H "PRIVATE-TOKEN: <redacted>" "http://GITLAB_HOST/api/v4/projects/TARGET_GROUP%2FTARGET_PROJECT/merge_requests/<MR_IID>"
```

Cross-project MR discovery, for diagnosis only:

```bash
curl -sS -X GET -H "PRIVATE-TOKEN: <redacted>" "http://GITLAB_HOST/api/v4/merge_requests?source_branch=BRANCH&state=opened&source_project_id=SOURCE_ID&target_project_id=TARGET_ID&per_page=20"
```

## Default Non-Foreign MR Comment Pipeline

For ordinary MR comment workflows, use a persistent subagent pipeline by default
when subagents are available:

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

Review GitLab comments skeptically: do not rush to accept or deny them. Compare
each comment against local code, behavior, project constraints, and viable
alternatives before recommending action.
Clarification artifacts should prefer this compact shape: location, code
segment, original review comment, agent analysis, options/trade-offs, default
behavior, and `[ ] Human review:` space.

## Subskill: Foreign MR Code Changes

Use this subskill only when the user explicitly asks to inspect code changes
from a specific target-project MR whose source project may differ from local
`origin`.

This subskill fetches MR code diffs for later agent review. It does not fetch or
interpret review comments. The parent GitLoong comment workflow remains strict
and unchanged.

### Required Config

Create `foreign_mr_config.json` beside this `SKILL.md`:

```json
{
    "gitlab_token": ""
}
```

- `gitlab_token`: GitLab token with API read access.
- No other keys are allowed in this config. In particular, a legacy persisted
  MR IID is rejected.

### Invocation

```bash
python3.11 /path/to/gitloong/scripts/fetch_mr_changes.py --mr-iid <user-provided-iid> --output .agent/tmp/gitloong_mr_changes.json
```

By default the subskill requires the MR target branch to be `main` and fetches
the latest MR code changes as reported by GitLab. To inspect a user-approved MR
whose target branch is not `main`, pass `--target-branch ""` or the explicitly
requested branch name.

### Workflow Contract

1. Obtain the explicit user-provided MR IID and pass it through `--mr-iid`.
2. Read `foreign_mr_config.json`.
3. Inspect `git remote` only.
4. Require exactly two remotes, one named `origin` and one target remote.
5. Derive the GitLab base URL and target project path from the non-origin
   remote. Do not guess or override the target project URL.
6. Fetch the target-project MR identified by `--mr-iid`.
7. Continue only if the MR exists, is open, and matches the required target
   branch when one is configured.
8. Do not require the MR source project to match local `origin`.
9. Write JSON containing MR metadata, diff refs, changed file metadata, and raw
   per-file diff text.

Failure handling:

- Missing `foreign_mr_config.json` or token, or a missing/invalid `--mr-iid`:
  stop and ask the user.
- Config keys other than `gitlab_token`: stop and ask the user.
- Remote layout not exactly `origin` plus one target remote: stop and ask the
  user to confirm the repository setup.
- MR missing, closed, merged, or target branch mismatch: stop and ask the user
  to recheck the supplied MR IID, remotes, and target branch intent.
- GitLab/API/network failure: stop. Do not silently switch protocols or auth
  methods; use troubleshooting probes only after failure and redact tokens.

### Review Phase

Before reviewing fetched code changes, check the current branch:

```bash
git branch --show-current
```

If the current branch is not `main`, terminate the subskill invocation and tell
the user to switch to `main` and sync with the target remote before trying
again. Do not inspect or review MR diffs from another branch.

When the branch gate passes, review the fetched diff JSON by spawning subagents.
The parent agent must orchestrate, assign focused file groups, collect findings,
and synthesize the final review artifact. Code inspection for fetched MR diffs
should always be done by subagent spawning to prevent parent-context occupation.

Subagents may inspect the current local codebase for context because the branch
gate ensures the workspace is on `main`. They must not edit files for review
phase work.

Preferred review artifact shape:

```markdown
# Foreign MR Code-Change Review

## MR

- MR: <iid/title/url>
- Source branch: <source_branch>
- Target branch: <target_branch>
- Diff refs: <base/head/start sha>

## Findings

### <short finding title>

- Location: `<path>:<line>` or `<path>:<diff hunk header>` for quick lookup.
  Always include concrete local line numbers when available. If the finding is
  only present in the fetched diff and no stable local line exists, include the
  diff hunk header such as `@@ -10,6 +10,9 @@`.
- Code segment: `<brief changed code or hunk summary>`
- MR diff signal: `<what the fetched diff changed>`
- Agent analysis: `<why this may be risky or why it is acceptable>`
- Options/trade-offs: `<practical choices>`
- Default behavior: `<recommended default>`
- [ ] Human review:
```

Lead with concrete risks. If no issues are found, say so and mention residual
risk such as limited runtime coverage, API truncation, or untested paths.
