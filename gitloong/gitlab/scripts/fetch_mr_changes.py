#!/usr/bin/env python3.11
"""Fetch target-project MR code changes as JSON.

This script is for explicitly requested foreign MR inspection. It derives the
GitLab host and target project only from the current repository's non-origin
remote, then fetches the invocation-selected MR's latest code changes from
that target project.
"""

import argparse
import json
import subprocess
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


Config = dict[str, Any]
RemoteInfo = tuple[str, str]


def fail(message: str, code: int) -> None:
    print(f"gitloong-mr-changes: {message}", file=sys.stderr)
    raise SystemExit(code)


def positive_mr_iid(value: str) -> int:
    try:
        mr_iid = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("MR IID must be a positive integer") from exc
    if mr_iid <= 0:
        raise argparse.ArgumentTypeError("MR IID must be a positive integer")
    return mr_iid


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
    config_path = skill_dir / "foreign_mr_config.json"
    if not config_path.exists():
        fail("missing foreign_mr_config.json", 1)
    try:
        config = json.loads(config_path.read_text())
    except (OSError, json.JSONDecodeError):
        fail("invalid foreign_mr_config.json", 1)
    allowed_keys = {"gitlab_token"}
    extra_keys = set(config) - allowed_keys
    if extra_keys:
        fail("foreign_mr_config.json must contain only gitlab_token", 1)
    if not str(config.get("gitlab_token", "")).strip():
        fail("missing gitlab_token in foreign_mr_config.json", 1)
    return config


def parse_remote_url(remote_url: str) -> RemoteInfo:
    url = remote_url.removesuffix(".git")
    if url.startswith("https://") or url.startswith("http://"):
        parsed = urllib.parse.urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}", parsed.path.lstrip("/")
    if url.startswith("git@"):
        host_part, sep, path_part = url.partition(":")
        if not sep:
            fail("unsupported SSH remote URL", 2)
        host = host_part.replace("git@", "", 1)
        scheme = "http" if host == "192.168.12.159" else "https"
        return f"{scheme}://{host}", path_part
    fail("unsupported remote URL", 2)


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


def api_json(gitlab_base: str, token: str, path: str) -> Any:
    url = f"{gitlab_base}/api/v4/{path}"
    request = urllib.request.Request(url, headers={"PRIVATE-TOKEN": token})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        fail(f"api request failed: {exc}", 4)


def fetch_mr_changes(
    gitlab_base: str,
    token: str,
    target_project_path: str,
    mr_iid: int,
) -> dict[str, Any]:
    encoded_path = urllib.parse.quote(target_project_path, safe="")
    changes = api_json(
        gitlab_base,
        token,
        f"projects/{encoded_path}/merge_requests/{mr_iid}/changes",
    )
    if not isinstance(changes, dict):
        fail("unexpected MR changes response", 4)
    return changes


def validate_mr_changes(changes: dict[str, Any], target_branch: str | None) -> None:
    state = changes.get("state")
    if state != "opened":
        fail("MR is not open", 3)
    if target_branch and changes.get("target_branch") != target_branch:
        fail(f"MR target branch is not {target_branch}", 3)


def build_output(
    source_project_path: str,
    target_project_path: str,
    gitlab_base: str,
    changes: dict[str, Any],
    required_target_branch: str | None,
) -> dict[str, Any]:
    files: list[dict[str, Any]] = []
    raw_changes = changes.get("changes", [])
    if not isinstance(raw_changes, list):
        fail("unexpected changes list in MR response", 4)
    for change in raw_changes:
        if not isinstance(change, dict):
            continue
        files.append(
            {
                "old_path": change.get("old_path"),
                "new_path": change.get("new_path"),
                "new_file": change.get("new_file"),
                "renamed_file": change.get("renamed_file"),
                "deleted_file": change.get("deleted_file"),
                "generated_file": change.get("generated_file"),
                "a_mode": change.get("a_mode"),
                "b_mode": change.get("b_mode"),
                "diff": change.get("diff", ""),
            }
        )
    return {
        "meta": {
            "mode": "foreign_mr_code_changes",
            "gitlab_url": gitlab_base,
            "origin_project_path": source_project_path,
            "target_project_path": target_project_path,
            "mr_iid": changes.get("iid"),
            "mr_id": changes.get("id"),
            "mr_title": changes.get("title", ""),
            "mr_web_url": changes.get("web_url", ""),
            "state": changes.get("state"),
            "source_branch": changes.get("source_branch", ""),
            "target_branch": changes.get("target_branch", ""),
            "required_target_branch": required_target_branch,
            "source_project_id": changes.get("source_project_id"),
            "target_project_id": changes.get("target_project_id"),
            "diff_refs": changes.get("diff_refs"),
            "changes_count": len(files),
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "source_project_match_not_required": True,
        },
        "files": files,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mr-iid", required=True, type=positive_mr_iid)
    parser.add_argument("--output", default=".agent/tmp/gitloong_mr_changes.json")
    parser.add_argument(
        "--target-branch",
        default="main",
        help="Required MR target branch. Use an empty value to skip this check.",
    )
    args = parser.parse_args()

    skill_dir = Path(__file__).resolve().parent.parent
    config = read_config(skill_dir)
    source_remote, target_remote = get_remote_layout()
    source_base, source_project_path = source_remote
    target_base, target_project_path = target_remote
    if source_base != target_base:
        fail("origin and target remotes use different GitLab hosts", 2)

    token = str(config["gitlab_token"]).strip()
    mr_iid = args.mr_iid
    target_branch = args.target_branch or None
    changes = fetch_mr_changes(target_base, token, target_project_path, mr_iid)
    validate_mr_changes(changes, target_branch)
    output = build_output(
        source_project_path,
        target_project_path,
        target_base,
        changes,
        target_branch,
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
