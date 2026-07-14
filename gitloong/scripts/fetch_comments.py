#!/usr/bin/env python3
"""
fetch_comments.py — Fetch unresolved, code-tied review comments from GitLab MR.

Usage:
    python3 fetch_comments.py [--output PATH] [--test-auth]

Options:
    --output PATH   Write JSON result to PATH (default: ./gitloong_comments.json)
    --test-auth     Only verify GitLab connectivity and token validity, then exit

Exit codes:
    0   Success
    1   Auth/config error (auth.json missing/invalid, token rejected)
    2   Git repo error (not a git repo, no remote)
    3   MR detection error (no open MR for current branch, ambiguous match)
    4   API/network error
    5   Output/write error
"""

import argparse
import json
import os
import subprocess
import sys
import urllib.parse
from pathlib import Path
from datetime import datetime, timezone


def error(msg: str, code: int = 1):
    print(f"[gitloong] {msg}", file=sys.stderr)
    sys.exit(code)


def info(msg: str):
    print(f"[gitloong] {msg}")


def run(cmd: list[str], check: bool = True, capture: bool = True) -> subprocess.CompletedProcess:
    """Run a shell command and return result."""
    return subprocess.run(
        cmd,
        capture_output=capture,
        text=True,
        check=check
    )


def get_skill_dir() -> Path:
    """Determine the skill directory path (where this script resides)."""
    return Path(__file__).resolve().parent.parent


def read_auth(skill_dir: Path) -> str:
    """
    Read gitlab_token from auth.json under skill directory.
    If missing or invalid, print instructions and exit.
    """
    auth_path = skill_dir / "auth.json"

    if not auth_path.exists():
        error(
            f"auth.json not found at {auth_path}\n\n"
            "To set up credentials, create auth.json in the skill directory:\n"
            "  {\n"
            "    \"gitlab_token\": \"glpat-xxxxxxxxxxxxxxxxxxxx\"\n"
            "  }\n\n"
            "Obtain a token from your GitLab instance:\n"
            "  User Settings → Access Tokens → Add new token\n"
            "Required scope: read_api\n\n"
            "Or provide credentials in-session when prompted.",
            code=1
        )

    try:
        data = json.loads(auth_path.read_text())
    except (json.JSONDecodeError, OSError) as e:
        error(
            f"auth.json exists but cannot be parsed: {e}\n\n"
            f"Please verify the file at {auth_path} contains valid JSON:\n"
            "  {\n"
            "    \"gitlab_token\": \"glpat-xxxxxxxxxxxxxxxxxxxx\"\n"
            "  }",
            code=1
        )

    token = data.get("gitlab_token", "").strip()
    if not token:
        error(
            "auth.json found but 'gitlab_token' is empty or missing.\n\n"
            "Please set a valid token:\n"
            "  {\"gitlab_token\": \"glpat-xxxxxxxxxxxxxxxxxxxx\"}",
            code=1
        )

    return token


def git_remote_info() -> tuple[str, str]:
    """
    Derive GitLab base URL and project path from git remote.
    Returns (gitlab_base_url, project_path).
    """
    # Check if we're in a git repo
    result = run(["git", "rev-parse", "--is-inside-work-tree"], check=False)
    if result.returncode != 0 or result.stdout.strip() != "true":
        error(
            "Not inside a git repository.\n"
            "Please run this command from within a git-tracked project.",
            code=2
        )

    result = run(["git", "remote", "get-url", "origin"], check=False)
    if result.returncode != 0:
        error(
            "Failed to get remote 'origin'.\n"
            "Ensure the repository has an 'origin' remote configured.",
            code=2
        )

    remote_url = result.stdout.strip()

    # Parse HTTPS: https://gitlab.example.com/group/project.git
    # Parse SSH:    git@gitlab.example.com:group/project.git
    if remote_url.startswith("https://"):
        # Remove .git suffix if present
        url = remote_url.removesuffix(".git")
        parsed = urllib.parse.urlparse(url)
        gitlab_base = f"{parsed.scheme}://{parsed.netloc}"
        project_path = parsed.path.lstrip("/")
    elif remote_url.startswith("git@"):
        # SSH format: git@host:path.git
        url = remote_url.removesuffix(".git")
        host_part, sep, path_part = url.partition(":")
        if not sep:
            error(
                f"Cannot parse SSH remote URL: {remote_url}\n"
                "Expected format: git@host:group/project.git",
                code=2
            )
        host = host_part.replace("git@", "", 1)
        gitlab_base = f"https://{host}"
        project_path = path_part
    else:
        error(
            f"Unsupported remote URL format: {remote_url}\n"
            "Expected: https://gitlab.example.com/group/project.git\n"
            "     or:  git@gitlab.example.com:group/project.git",
            code=2
        )

    return gitlab_base, project_path


def git_current_branch() -> str:
    """Get the current git branch name."""
    result = run(["git", "branch", "--show-current"])
    branch = result.stdout.strip()
    if not branch:
        error("Cannot determine current git branch (detached HEAD?).", code=2)
    return branch


def curl_json(url: str, token: str, method: str = "GET", data: dict | None = None) -> dict | list:
    """
    Make an authenticated request to GitLab API using curl.
    Returns parsed JSON response.
    """
    headers = [
        "-H", f"PRIVATE-TOKEN: {token}",
        "-H", "Content-Type: application/json"
    ]

    cmd = ["curl", "-s", "-w", "\\n%{http_code}", "--fail-with-body", "-L"]
    cmd += headers

    if method == "POST" and data:
        cmd += ["-X", "POST", "-d", json.dumps(data)]
    elif method != "GET":
        cmd += ["-X", method]

    cmd += [url]

    result = run(cmd, check=False)

    if result.returncode != 0:
        body = result.stdout.strip()
        err_body = result.stderr.strip()
        # Extract status code if present
        if body:
            lines = body.splitlines()
            try:
                status = int(lines[-1])
            except ValueError:
                status = 0
            if 400 <= status < 600:
                error(f"GitLab API HTTP {status}: {url}\n{body}", code=4)
        error(f"curl failed for {url}\n{err_body or body}", code=4)

    # Parse status code from last line
    lines = result.stdout.strip().splitlines()
    if not lines:
        error(f"Empty response from {url}", code=4)

    try:
        status = int(lines[-1])
    except ValueError:
        # No status code appended - maybe older curl, try parse as JSON directly
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError:
            error(f"Cannot parse response from {url}\n{result.stdout[:500]}", code=4)

    body = "\n".join(lines[:-1])

    if status == 401:
        error(
            "GitLab API returned 401 Unauthorized.\n\n"
            "Your token may be invalid, expired, or lacks read_api scope.\n"
            "Please verify your auth.json token and try again.",
            code=1
        )
    if status == 403:
        error(
            "GitLab API returned 403 Forbidden.\n\n"
            "The token does not have permission to access this project/MR.\n"
            "Check token scope (requires read_api) and project membership.",
            code=1
        )
    if status == 404:
        error(
            f"GitLab API returned 404 Not Found:\n  {url}\n\n"
            "The project or MR may not exist, or the token cannot access it.",
            code=4
        )
    if status >= 400:
        error(f"GitLab API HTTP {status}: {url}\n{body[:1000]}", code=4)

    try:
        return json.loads(body) if body else {}
    except json.JSONDecodeError as e:
        error(f"Cannot parse JSON from {url}: {e}\n{body[:500]}", code=4)


def find_open_mr(gitlab_base: str, project_path: str, token: str, branch: str) -> dict:
    """
    Find an open merge request for the given source branch.
    Returns MR dict with at least: iid, title, source_branch, target_branch, web_url.
    Exits with clear message if 0 or >1 matches found.
    """
    encoded_path = urllib.parse.quote(project_path, safe="")
    url = (
        f"{gitlab_base}/api/v4/projects/{encoded_path}/merge_requests"
        f"?source_branch={urllib.parse.quote(branch)}"
        f"&state=opened"
        f"&per_page=5"
    )

    info(f"Searching open MR for branch: {branch}")
    result = curl_json(url, token)

    if not isinstance(result, list):
        error(f"Unexpected API response type: {type(result).__name__}", code=4)

    if len(result) == 0:
        error(
            f"No open merge request found for branch '{branch}'.\n\n"
            "Please ensure:\n"
            "  1. The branch has an associated MR on GitLab\n"
            "  2. The MR is in 'open' state (not merged or closed)\n\n"
            "To proceed with a specific MR, you can specify it manually.",
            code=3
        )

    if len(result) > 1:
        mr_list = "\n".join(
            f"    MR !{mr['iid']}: {mr.get('title', 'N/A')} -> {mr.get('target_branch', 'N/A')}"
            for mr in result[:10]
        )
        error(
            f"Found {len(result)} open MRs for branch '{branch}'.\n\n"
            f"{mr_list}\n\n"
            "Multiple MRs from the same branch is ambiguous.\n"
            "Please resolve this before proceeding.",
            code=3
        )

    mr = result[0]
    info(f"Found MR !{mr['iid']}: {mr.get('title', 'N/A')}")
    return mr


def fetch_discussions(gitlab_base: str, project_path: str, token: str, mr_iid: int) -> list[dict]:
    """Fetch all discussions for a given MR. Returns list of discussion objects."""
    encoded_path = urllib.parse.quote(project_path, safe="")
    url = f"{gitlab_base}/api/v4/projects/{encoded_path}/merge_requests/{mr_iid}/discussions?per_page=100"

    info(f"Fetching discussions for MR !{mr_iid}...")
    result = curl_json(url, token)

    if not isinstance(result, list):
        error(f"Unexpected discussions response type: {type(result).__name__}", code=4)

    info(f"Retrieved {len(result)} total discussion threads")
    return result


def filter_unresolved_code_threads(discussions: list[dict]) -> list[dict]:
    """
    Filter discussions to include only:
    - unresolved (resolved == false)
    - code-tied (has at least one note with a 'position' field)

    Returns structured list for JSON output.
    """
    filtered = []

    for disc in discussions:
        disc_id = disc.get("id", "unknown")
        resolved = disc.get("resolved", False)
        notes_raw = disc.get("notes", [])

        # Must be unresolved
        if resolved:
            continue

        # Must have at least one note with a position (code-tied)
        code_notes = []
        for note in notes_raw:
            position = note.get("position")
            if position:  # Code-tied comment
                code_notes.append({
                    "note_id": note.get("id"),
                    "author": note.get("author", {}).get("username", "unknown"),
                    "body": note.get("body", ""),
                    "created_at": note.get("created_at"),
                    "updated_at": note.get("updated_at"),
                    "position": {
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
                })

        if not code_notes:
            continue  # Skip non-code-tied threads

        # Build thread-level info from first note
        first_note = notes_raw[0] if notes_raw else {}

        filtered.append({
            "discussion_id": disc_id,
            "resolved": False,
            "created_at": first_note.get("created_at"),
            "notes": code_notes
        })

    return filtered


def test_auth(gitlab_base: str, token: str):
    """Test connectivity and token validity against GitLab API."""
    info("Testing GitLab connectivity...")
    url = f"{gitlab_base}/api/v4/user"
    user = curl_json(url, token)
    username = user.get("username", "unknown")
    name = user.get("name", "unknown")
    info(f"Auth OK: {name} (@{username})")
    info(f"GitLab: {gitlab_base}")
    sys.exit(0)


def main():
    parser = argparse.ArgumentParser(
        description="Fetch unresolved code review comments from GitLab MR"
    )
    parser.add_argument(
        "--output",
        default="gitloong_comments.json",
        help="Output JSON file path (default: gitloong_comments.json)"
    )
    parser.add_argument(
        "--test-auth",
        action="store_true",
        help="Verify GitLab connectivity and token, then exit"
    )
    args = parser.parse_args()

    # ── Step 1: Read credentials ──
    skill_dir = get_skill_dir()
    token = read_auth(skill_dir)

    # ── Step 2: Derive GitLab info from remote ──
    gitlab_base, project_path = git_remote_info()

    # If --test-auth, just verify connectivity
    if args.test_auth:
        test_auth(gitlab_base, token)

    # ── Step 3: Detect current branch and find MR ──
    branch = git_current_branch()
    mr = find_open_mr(gitlab_base, project_path, token, branch)
    mr_iid = mr["iid"]

    # ── Step 4: Fetch all discussions ──
    discussions = fetch_discussions(gitlab_base, project_path, token, mr_iid)

    # ── Step 5: Filter unresolved + code-tied ──
    threads = filter_unresolved_code_threads(discussions)
    info(f"Found {len(threads)} unresolved, code-tied discussion threads")

    # ── Step 6: Build output ──
    output = {
        "meta": {
            "project_path": project_path,
            "mr_iid": mr_iid,
            "mr_title": mr.get("title", ""),
            "mr_web_url": mr.get("web_url", ""),
            "source_branch": mr.get("source_branch", branch),
            "target_branch": mr.get("target_branch", ""),
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "gitlab_url": gitlab_base,
            "total_unresolved_code_threads": len(threads),
            "total_discussions_checked": len(discussions),
        },
        "threads": threads
    }

    # ── Step 7: Write output ──
    output_path = Path(args.output)
    try:
        output_path.write_text(json.dumps(output, indent=2, ensure_ascii=False))
        info(f"Wrote output to: {output_path.resolve()}")
    except OSError as e:
        error(f"Failed to write output file: {e}", code=5)

    # Summary
    if threads:
        info(f"---")
        info(f"Branch: {branch}")
        info(f"MR: !{mr_iid} ({mr.get('title', 'N/A')})")
        info(f"Unresolved code threads: {len(threads)}")
        for t in threads:
            note_count = len(t["notes"])
            first_file = t["notes"][0]["position"]["new_path"] if t["notes"] else "?"
            first_line = t["notes"][0]["position"]["new_line"] if t["notes"] else "?"
            info(f"  - {first_file}:{first_line} ({note_count} note(s))")
    else:
        info("No unresolved code review comments found.")


if __name__ == "__main__":
    main()
