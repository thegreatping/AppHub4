#!/usr/bin/env python
"""AppHub 4.0 isolated-work helper (multi-dev safe).

Creates or reuses a per-developer git worktree + feature branch so several
developers can work on different AppHub modules at the same time without
colliding in one shared working tree. Auto-detects the developer from
`git config user.email`.

Usage:
    py _apphub_worktree.py <module> [dev]

    module : short module name, e.g. new-hire, scorecard, pdm, peak-academy
    dev    : optional override; otherwise detected from git user.email
"""
import os
import re
import subprocess
import sys

# git user.email -> short dev tag
DEV_BY_EMAIL = {
    "cpell@peakmade.com": "craig",
    "rmahaffey@peakmade.com": "ryan",
    "rmadhu@peakmade.com": "rohit",
    "agraham@peakmade.com": "austin",
    "eyourse@peakmade.com": "elliott",
}

# Distinct dev-server port per dev so multiple worktrees don't fight over 5001.
PORT_BY_DEV = {"craig": 5001, "ryan": 5002, "rohit": 5003, "austin": 5004, "elliott": 5005}


def git(*args, capture=True):
    r = subprocess.run(["git", *args], capture_output=capture, text=True)
    if capture and r.returncode != 0 and r.stderr:
        sys.stderr.write(r.stderr)
    return r


def main():
    if len(sys.argv) < 2:
        print("Usage: py _apphub_worktree.py <module> [dev]")
        sys.exit(1)

    module = re.sub(r"[^a-z0-9-]", "-", sys.argv[1].lower()).strip("-")
    dev = sys.argv[2].lower() if len(sys.argv) > 2 else None

    if not dev:
        email = git("config", "user.email").stdout.strip().lower()
        dev = DEV_BY_EMAIL.get(email)
        if not dev:
            print(f"Unknown git user.email {email!r}.")
            print(f"  Pass your name: py _apphub_worktree.py {module} <craig|ryan|rohit|austin|elliott>")
            sys.exit(1)

    branch = f"feat/{module}-{dev}"
    repo_root = git("rev-parse", "--show-toplevel").stdout.strip()
    worktree = os.path.join(os.path.dirname(repo_root), f"APPHUB_4__{dev}-{module}")

    git("fetch", "origin", capture=False)

    if worktree in git("worktree", "list").stdout:
        print(f"Reusing existing worktree: {worktree}")
    else:
        branch_exists = git("rev-parse", "--verify", f"refs/heads/{branch}").returncode == 0
        if branch_exists:
            r = git("worktree", "add", worktree, branch, capture=False)
        else:
            r = git("worktree", "add", worktree, "-b", branch, "origin/main", capture=False)
        if r.returncode != 0:
            print("Failed to create worktree (see git error above).")
            sys.exit(1)

    port = PORT_BY_DEV.get(dev, 5001)
    print()
    print("=== AppHub isolated worktree ready ===")
    print(f"  dev     : {dev}")
    print(f"  module  : {module}")
    print(f"  branch  : {branch}")
    print(f"  folder  : {worktree}")
    print(f"  devport : {port}")
    print()
    print("Open that folder and edit only your module's files.")
    print("Stage explicitly (git add <files>), `git pull --rebase origin main` before push,")
    print("bump config.py APP_VERSION last. Merging to main (= deploy) is an explicit step.")


if __name__ == "__main__":
    main()
