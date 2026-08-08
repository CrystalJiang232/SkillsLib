#!/usr/bin/env python3.11
"""Fetch unresolved GitHub PR review threads as JSON.

GitHub.com fork workflow only: `origin` is the private/source fork and the
single non-origin remote is the base repository that owns the pull request.
Code-tied review threads are fetched through the GraphQL API and keep
GitLab-like "unresolved" semantics via `isResolved`; non-code issue comments
are fetched separately but are not analyzed by default. Configuration
provides authentication and filtering only; the PR number is an invocation
parameter.
"""

import argparse
import json
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


Config = dict[str, Any]
RemoteInfo = tuple[str, str]

API_BASE = "https://api.github.com"
GRAPHQL_URL = "https://api.github.com/graphql"
API_VERSION = "2022-11-28"
PER_PAGE = 100


def fail(message: str, code: int) -> None:
    print(f"gitloong-github: {message}", file=sys.stderr)
    raise SystemExit(code)


def positive_pr_number(value: str) -> int:
    try:
        pr_number = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("PR number must be a positive integer") from exc
    if pr_number <= 0:
        raise argparse.ArgumentTypeError("PR number must be a positive integer")
    return pr_number


def run_git(args: list[str]) -> str:
    result = subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        fail("git command failed", 2)
    return result.stdout.strip()


def read_config(skill_dir: Path) -> Config:
    config_path = skill_dir / "config.json"
    if not config_path.exists():
        fail("missing config.json", 1)
    try:
        config = json.loads(config_path.read_text())
    except (OSError, json.JSONDecodeError):
        fail("invalid config.json", 1)
    allowed_keys = {"github_token", "drop_thread_contains_user"}
    extra_keys = set(config) - allowed_keys
    if extra_keys:
        fail("config.json must contain only github_token and drop_thread_contains_user", 1)
    if not str(config.get("github_token", "")).strip():
        fail("missing github_token in config.json", 1)
    return config


def parse_remote_url(remote_url: str) -> RemoteInfo:
    url = remote_url.removesuffix(".git")
    if url.startswith("https://") or url.startswith("http://"):
        parsed = urllib.parse.urlparse(url)
        if parsed.netloc.lower() != "github.com":
            fail("remote is not a github.com URL", 2)
        path = parsed.path.strip("/")
    elif url.startswith("git@"):
        host_part, sep, path_part = url.partition(":")
        if not sep:
            fail("unsupported SSH remote URL", 2)
        if host_part.replace("git@", "", 1).lower() != "github.com":
            fail("remote is not a github.com SSH URL", 2)
        path = path_part.strip("/")
    else:
        fail("unsupported remote URL", 2)
    segments = path.split("/")
    if len(segments) != 2:
        fail("remote path must be owner/repo", 2)
    return "https://github.com", f"{segments[0]}/{segments[1]}"


def get_remote_layout() -> tuple[RemoteInfo, RemoteInfo]:
    lines = run_git(["remote", "-v"]).splitlines()
    fetch_remotes: dict[str, str] = dict()
    for line in lines:
        parts = line.split()
        if len(parts) == 3 and parts[2] == "(fetch)":
            fetch_remotes[parts[0]] = parts[1]
    if "origin" not in fetch_remotes or len(fetch_remotes) != 2:
        fail("expected exactly two fetch remotes: origin plus target remote", 2)
    target_names = [name for name in fetch_remotes if name != "origin"]
    return parse_remote_url(fetch_remotes["origin"]), parse_remote_url(fetch_remotes[target_names[0]])


def rest_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": API_VERSION,
        "User-Agent": "gitloong",
    }


def rest_get(token: str, path: str) -> Any:
    request = urllib.request.Request(f"{API_BASE}/{path}", headers=rest_headers(token))
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        fail(f"api request failed: HTTP {exc.code}", 4)
    except Exception as exc:
        fail(f"api request failed: {exc}", 4)


def rest_list_all(token: str, path: str) -> list[Any]:
    items: list[Any] = []
    url = f"{API_BASE}/{path}?per_page={PER_PAGE}"
    while url:
        request = urllib.request.Request(url, headers=rest_headers(token))
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                payload = json.loads(response.read().decode("utf-8"))
                link = response.headers.get("Link", "")
        except urllib.error.HTTPError as exc:
            fail(f"api request failed: HTTP {exc.code}", 4)
        except Exception as exc:
            fail(f"api request failed: {exc}", 4)
        if not isinstance(payload, list):
            fail("unexpected list response", 4)
        items.extend(payload)
        next_url = None
        for part in link.split(","):
            match = re.match(r'<([^>]+)>;\s*rel="next"', part.strip())
            if match:
                next_url = match.group(1)
                break
        url = next_url
    return items


def fetch_pull_request(token: str, owner: str, repo: str, pr_number: int) -> dict[str, Any]:
    request = urllib.request.Request(
        f"{API_BASE}/repos/{owner}/{repo}/pulls/{pr_number}",
        headers=rest_headers(token),
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            pr = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            fail("pull request not found", 3)
        fail(f"api request failed: HTTP {exc.code}", 4)
    except Exception as exc:
        fail(f"api request failed: {exc}", 4)
    if not isinstance(pr, dict):
        fail("unexpected pull request response", 4)
    return pr


def validate_pr(pr: dict[str, Any], source_full_name: str, target_full_name: str) -> None:
    if pr.get("state") != "open":
        fail("pull request is not open", 3)
    if pr.get("merged") is True:
        fail("pull request is merged", 3)
    head_repo = pr.get("head", {}).get("repo")
    base_repo = pr.get("base", {}).get("repo")
    if not isinstance(head_repo, dict) or not isinstance(base_repo, dict):
        fail("pull request head/base repository missing", 3)
    if str(head_repo.get("full_name", "")).casefold() != source_full_name.casefold():
        fail("pull request source repository does not match origin remote", 3)
    if str(base_repo.get("full_name", "")).casefold() != target_full_name.casefold():
        fail("pull request target repository does not match target remote", 3)


GRAPHQL_QUERY = """
query PullRequestReviewThreads($owner: String!, $name: String!, $number: Int!, $cursor: String) {
  repository(owner: $owner, name: $name) {
    pullRequest(number: $number) {
      reviewThreads(first: 100, after: $cursor) {
        pageInfo {
          hasNextPage
          endCursor
        }
        nodes {
          id
          isResolved
          isCollapsed
          isOutdated
          path
          line
          startLine
          subjectType
          comments(first: 100) {
            nodes {
              id
              body
              createdAt
              updatedAt
              outdated
              path
              line
              replyTo {
                id
              }
              author {
                login
              }
            }
          }
        }
      }
    }
  }
}
"""


def graphql_query(token: str, query: str, variables: dict[str, Any]) -> dict[str, Any]:
    body = json.dumps({"query": query, "variables": variables}).encode("utf-8")
    headers = rest_headers(token)
    headers["Content-Type"] = "application/json"
    request = urllib.request.Request(GRAPHQL_URL, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        fail(f"graphql request failed: HTTP {exc.code}", 4)
    except Exception as exc:
        fail(f"graphql request failed: {exc}", 4)
    if not isinstance(payload, dict):
        fail("unexpected graphql response", 4)
    if payload.get("errors"):
        messages = "; ".join(
            str(error.get("message", error)) for error in payload["errors"]
        )
        fail(f"graphql error: {messages}", 4)
    return payload


def fetch_review_threads(
    token: str,
    owner: str,
    repo: str,
    pr_number: int,
) -> list[dict[str, Any]]:
    threads: list[dict[str, Any]] = []
    cursor: str | None = None
    while True:
        payload = graphql_query(
            token,
            GRAPHQL_QUERY,
            {"owner": owner, "name": repo, "number": pr_number, "cursor": cursor},
        )
        repository = payload.get("data", {}).get("repository")
        pull_request = (
            repository.get("pullRequest") if isinstance(repository, dict) else None
        )
        if not isinstance(pull_request, dict):
            fail("pull request not found", 3)
        threads_node = pull_request.get("reviewThreads", {})
        if not isinstance(threads_node, dict):
            fail("unexpected reviewThreads response", 4)
        page_info = threads_node.get("pageInfo", {})
        nodes = threads_node.get("nodes")
        if isinstance(nodes, list):
            threads.extend(node for node in nodes if isinstance(node, dict))
        if not page_info.get("hasNextPage"):
            break
        cursor = page_info.get("endCursor")
        if not cursor:
            break
    return threads


def comment_author(comment: dict[str, Any]) -> str:
    author = comment.get("author")
    if isinstance(author, dict):
        return str(author.get("login", "unknown")).strip()
    return "unknown"


def is_jenkins_comment(comment: dict[str, Any]) -> bool:
    author = comment.get("author")
    author_text = " ".join(
        str(author.get("login", "")) if isinstance(author, dict) else ""
    ).lower()
    body = str(comment.get("body", "")).lower()
    if "jenkins" in author_text:
        return True
    if "jenkins" not in body:
        return False
    return any(
        marker in body
        for marker in ("job/", "/job/", "build", "console", "pipeline", "started", "finished")
    )


def is_jenkins_thread(comments: list[dict[str, Any]]) -> bool:
    return bool(comments) and all(is_jenkins_comment(comment) for comment in comments)


def comment_common_fields(comment: dict[str, Any]) -> dict[str, Any]:
    reply_to = comment.get("replyTo")
    return {
        "note_id": comment.get("id"),
        "author": comment_author(comment),
        "body": comment.get("body", ""),
        "created_at": comment.get("createdAt"),
        "updated_at": comment.get("updatedAt"),
        "system": False,
        "resolvable": True,
        "resolved": False,
        "in_reply_to_id": reply_to.get("id") if isinstance(reply_to, dict) else None,
    }


def thread_position(thread: dict[str, Any]) -> dict[str, Any]:
    return {
        "path": thread.get("path"),
        "line": thread.get("line"),
        "start_line": thread.get("startLine"),
        "original_line": None,
        "position_type": thread.get("subjectType"),
        "outdated": thread.get("isOutdated", False),
    }


def filter_threads(
    threads: list[dict[str, Any]],
    drop_users: set[str],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    kept: list[dict[str, Any]] = []
    counts: dict[str, int] = {
        "resolved_threads_dropped": 0,
        "drop_user_threads_dropped": 0,
        "jenkins_threads_dropped": 0,
        "unresolved_code_threads": 0,
    }
    for thread in threads:
        if thread.get("isResolved") is True:
            counts["resolved_threads_dropped"] += 1
            continue
        comments_node = thread.get("comments")
        comments = comments_node.get("nodes", []) if isinstance(comments_node, dict) else []
        dict_comments = [comment for comment in comments if isinstance(comment, dict)]
        authors = {comment_author(comment) for comment in dict_comments}
        if authors & drop_users:
            counts["drop_user_threads_dropped"] += 1
            continue
        if is_jenkins_thread(dict_comments):
            counts["jenkins_threads_dropped"] += 1
            continue
        notes = [comment_common_fields(comment) for comment in dict_comments]
        if notes:
            counts["unresolved_code_threads"] += 1
            kept.append(
                {
                    "discussion_id": thread.get("id", "unknown"),
                    "thread_type": "code",
                    "resolved": False,
                    "is_outdated": thread.get("isOutdated", False),
                    "created_at": dict_comments[0].get("createdAt"),
                    "position": thread_position(thread),
                    "notes": notes,
                }
            )
    return kept, counts


def fetch_issue_comments(
    token: str,
    owner: str,
    repo: str,
    pr_number: int,
) -> list[dict[str, Any]]:
    raw = rest_list_all(token, f"repos/{owner}/{repo}/issues/{pr_number}/comments")
    comments: list[dict[str, Any]] = []
    for comment in raw:
        if not isinstance(comment, dict):
            continue
        user = comment.get("user")
        comments.append(
            {
                "comment_id": comment.get("id"),
                "author": str(user.get("login", "unknown")).strip()
                if isinstance(user, dict)
                else "unknown",
                "body": comment.get("body", ""),
                "created_at": comment.get("created_at"),
                "updated_at": comment.get("updated_at"),
                "html_url": comment.get("html_url"),
                "minimized": comment.get("minimized", False),
            }
        )
    return comments


def build_output(
    source_full_name: str,
    target_full_name: str,
    pr: dict[str, Any],
    threads_checked: int,
    threads: list[dict[str, Any]],
    non_code_comments: list[dict[str, Any]],
    counts: dict[str, int],
    drop_users: list[str],
) -> dict[str, Any]:
    head = pr.get("head", {})
    base = pr.get("base", {})
    head_repo = head.get("repo") if isinstance(head, dict) else {}
    base_repo = base.get("repo") if isinstance(base, dict) else {}
    head_repo = head_repo if isinstance(head_repo, dict) else {}
    base_repo = base_repo if isinstance(base_repo, dict) else {}
    return {
        "meta": {
            "provider": "github",
            "github_url": "https://github.com",
            "source_repository": source_full_name,
            "target_repository": target_full_name,
            "pr_number": pr.get("number"),
            "pr_title": pr.get("title", ""),
            "pr_web_url": pr.get("html_url", ""),
            "source_branch": head.get("ref", ""),
            "target_branch": base.get("ref", ""),
            "head_sha": head.get("sha", ""),
            "base_sha": base.get("sha", ""),
            "head_repo_id": head_repo.get("id"),
            "base_repo_id": base_repo.get("id"),
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "drop_thread_contains_user": drop_users,
            "total_review_threads_checked": threads_checked,
            "total_unresolved_code_threads": counts["unresolved_code_threads"],
            "total_resolved_threads_dropped": counts["resolved_threads_dropped"],
            "total_drop_user_threads_dropped": counts["drop_user_threads_dropped"],
            "total_jenkins_threads_dropped": counts["jenkins_threads_dropped"],
            "non_code_comments_fetched": len(non_code_comments),
            "non_code_analyzed": False,
        },
        "threads": threads,
        "non_code_comments": non_code_comments,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pr-number", required=True, type=positive_pr_number)
    parser.add_argument("--output", default=".agent/tmp/github_pr_comments.json")
    args = parser.parse_args()

    skill_dir = Path(__file__).resolve().parent.parent
    config = read_config(skill_dir)
    source_remote, target_remote = get_remote_layout()
    source_base, source_full_name = source_remote
    target_base, target_full_name = target_remote
    if source_base != target_base:
        fail("origin and target remotes use different hosts", 2)

    token = str(config["github_token"]).strip()
    pr_number = args.pr_number
    drop_users = [
        str(user).strip() for user in config.get("drop_thread_contains_user", [])
    ]

    owner, repo = target_full_name.split("/", 1)
    pr = fetch_pull_request(token, owner, repo, pr_number)
    validate_pr(pr, source_full_name, target_full_name)
    threads = fetch_review_threads(token, owner, repo, pr_number)
    kept_threads, counts = filter_threads(threads, set(drop_users))
    non_code_comments = fetch_issue_comments(token, owner, repo, pr_number)
    output = build_output(
        source_full_name,
        target_full_name,
        pr,
        len(threads),
        kept_threads,
        non_code_comments,
        counts,
        drop_users,
    )

    try:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2))
    except OSError as exc:
        fail(f"output write failed: {exc}", 5)
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
