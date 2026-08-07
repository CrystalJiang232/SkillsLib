#!/usr/bin/env python3.11
"""Fetch unresolved GitLab MR discussions as JSON.

The script assumes a fork workflow: `origin` is the private/source project and
the single non-origin remote is the upstream/target project that owns the MR.
Configuration provides authentication and filtering only; the MR IID is an
invocation parameter.
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
    print(f"gitloong: {message}", file=sys.stderr)
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
    config_path = skill_dir / "config.json"
    if not config_path.exists():
        fail("missing config.json", 1)
    try:
        config = json.loads(config_path.read_text())
    except (OSError, json.JSONDecodeError):
        fail("invalid config.json", 1)
    allowed_keys = {"gitlab_token", "drop_thread_contains_user"}
    extra_keys = set(config) - allowed_keys
    if extra_keys:
        fail("config.json must contain only gitlab_token and drop_thread_contains_user", 1)
    if not str(config.get("gitlab_token", "")).strip():
        fail("missing gitlab_token in config.json", 1)
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


def fetch_project(gitlab_base: str, token: str, project_path: str) -> dict[str, Any]:
    encoded_path = urllib.parse.quote(project_path, safe="")
    project = api_json(gitlab_base, token, f"projects/{encoded_path}")
    if not isinstance(project, dict):
        fail("unexpected project response", 4)
    return project


def fetch_mr(
    gitlab_base: str,
    token: str,
    target_project_path: str,
    mr_iid: int,
) -> dict[str, Any]:
    encoded_path = urllib.parse.quote(target_project_path, safe="")
    mr = api_json(gitlab_base, token, f"projects/{encoded_path}/merge_requests/{mr_iid}")
    if not isinstance(mr, dict):
        fail("unexpected MR response", 4)
    return mr


def validate_mr(mr: dict[str, Any], source_project: dict[str, Any]) -> None:
    if mr.get("state") != "opened":
        fail("MR is not open", 3)
    if mr.get("source_project_id") != source_project.get("id"):
        fail("MR source project does not match origin remote", 3)


def fetch_discussions(
    gitlab_base: str,
    token: str,
    target_project_path: str,
    mr_iid: int,
) -> list[dict[str, Any]]:
    encoded_path = urllib.parse.quote(target_project_path, safe="")
    discussions = api_json(
        gitlab_base,
        token,
        f"projects/{encoded_path}/merge_requests/{mr_iid}/discussions?per_page=100",
    )
    if not isinstance(discussions, list):
        fail("unexpected discussions response", 4)
    return discussions


def is_resolved_discussion(discussion: dict[str, Any]) -> bool:
    if discussion.get("resolved") is True:
        return True
    notes = discussion.get("notes", [])
    if not isinstance(notes, list):
        return False
    resolvable_notes = [
        note
        for note in notes
        if isinstance(note, dict) and note.get("resolvable") is True
    ]
    return bool(resolvable_notes) and all(
        note.get("resolved") is True for note in resolvable_notes
    )


def note_author(note: dict[str, Any]) -> str:
    return str(note.get("author", {}).get("username", "unknown")).strip()


def note_common_fields(note: dict[str, Any]) -> dict[str, Any]:
    return {
        "note_id": note.get("id"),
        "author": note_author(note),
        "body": note.get("body", ""),
        "created_at": note.get("created_at"),
        "updated_at": note.get("updated_at"),
        "system": note.get("system", False),
        "resolvable": note.get("resolvable", False),
        "resolved": note.get("resolved", False),
    }


def position_fields(position: dict[str, Any]) -> dict[str, Any]:
    return {
        "base_sha": position.get("base_sha"),
        "head_sha": position.get("head_sha"),
        "start_sha": position.get("start_sha"),
        "old_path": position.get("old_path"),
        "new_path": position.get("new_path"),
        "position_type": position.get("position_type"),
        "new_line": position.get("new_line"),
        "old_line": position.get("old_line"),
        "line_range": position.get("line_range"),
    }


def is_jenkins_note(note: dict[str, Any]) -> bool:
    author = note.get("author", {})
    author_text = " ".join(
        str(author.get(key, "")) for key in ("username", "name")
    ).lower()
    body = str(note.get("body", "")).lower()
    if "jenkins" in author_text:
        return True
    if "jenkins" not in body:
        return False
    return any(
        marker in body
        for marker in ("job/", "/job/", "build", "console", "pipeline", "started", "finished")
    )


def is_jenkins_discussion(notes: list[dict[str, Any]]) -> bool:
    return bool(notes) and all(is_jenkins_note(note) for note in notes)


def filter_threads(
    discussions: list[dict[str, Any]],
    drop_users: set[str],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    threads: list[dict[str, Any]] = []
    counts: dict[str, int] = {
        "resolved_discussions_dropped": 0,
        "drop_user_discussions_dropped": 0,
        "jenkins_discussions_dropped": 0,
        "unresolved_code_threads": 0,
        "unresolved_non_code_threads": 0,
    }
    for discussion in discussions:
        if is_resolved_discussion(discussion):
            counts["resolved_discussions_dropped"] += 1
            continue
        notes = discussion.get("notes", [])
        if not isinstance(notes, list):
            notes = []
        dict_notes = [note for note in notes if isinstance(note, dict)]
        authors = {
            note_author(note)
            for note in dict_notes
        }
        if authors & drop_users:
            counts["drop_user_discussions_dropped"] += 1
            continue
        if is_jenkins_discussion(dict_notes):
            counts["jenkins_discussions_dropped"] += 1
            continue
        thread_notes: list[dict[str, Any]] = []
        has_position = False
        for note in dict_notes:
            thread_note = note_common_fields(note)
            position = note.get("position")
            if isinstance(position, dict) and position:
                has_position = True
                thread_note["position"] = position_fields(position)
            thread_notes.append(thread_note)
        if thread_notes:
            thread_type = "code" if has_position else "non_code"
            counts[f"unresolved_{thread_type}_threads"] += 1
            first_note = dict_notes[0] if dict_notes else {}
            threads.append(
                {
                    "discussion_id": discussion.get("id", "unknown"),
                    "thread_type": thread_type,
                    "resolved": False,
                    "created_at": first_note.get("created_at"),
                    "notes": thread_notes,
                }
            )
    return threads, counts


def build_output(
    source_project_path: str,
    target_project_path: str,
    gitlab_base: str,
    mr: dict[str, Any],
    discussions: list[dict[str, Any]],
    threads: list[dict[str, Any]],
    counts: dict[str, int],
    drop_users: list[str],
) -> dict[str, Any]:
    return {
        "meta": {
            "gitlab_url": gitlab_base,
            "source_project_path": source_project_path,
            "target_project_path": target_project_path,
            "mr_iid": mr.get("iid"),
            "mr_id": mr.get("id"),
            "mr_title": mr.get("title", ""),
            "mr_web_url": mr.get("web_url", ""),
            "source_branch": mr.get("source_branch", ""),
            "target_branch": mr.get("target_branch", ""),
            "source_project_id": mr.get("source_project_id"),
            "target_project_id": mr.get("target_project_id"),
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "drop_thread_contains_user": drop_users,
            "total_discussions_checked": len(discussions),
            "total_unresolved_threads": len(threads),
            "total_unresolved_code_threads": counts["unresolved_code_threads"],
            "total_unresolved_non_code_threads": counts["unresolved_non_code_threads"],
            "total_resolved_discussions_dropped": counts["resolved_discussions_dropped"],
            "total_drop_user_discussions_dropped": counts["drop_user_discussions_dropped"],
            "total_jenkins_discussions_dropped": counts["jenkins_discussions_dropped"],
        },
        "threads": threads,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mr-iid", required=True, type=positive_mr_iid)
    parser.add_argument("--output", default="gitloong_comments.json")
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
    drop_users = [str(user).strip() for user in config.get("drop_thread_contains_user", [])]
    source_project = fetch_project(target_base, token, source_project_path)
    mr = fetch_mr(target_base, token, target_project_path, mr_iid)
    validate_mr(mr, source_project)
    discussions = fetch_discussions(target_base, token, target_project_path, mr_iid)
    threads, counts = filter_threads(discussions, set(drop_users))
    output = build_output(
        source_project_path,
        target_project_path,
        target_base,
        mr,
        discussions,
        threads,
        counts,
        drop_users,
    )

    try:
        Path(args.output).write_text(json.dumps(output, ensure_ascii=False, indent=2))
    except OSError as exc:
        fail(f"output write failed: {exc}", 5)
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
