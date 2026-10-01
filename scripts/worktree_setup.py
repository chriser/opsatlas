#!/usr/bin/env python3
"""Give a git worktree its own writable runtime, so work there cannot write into live state (AUDIT F15).

A live restart loads the main folder, so changes are developed in a worktree. Worktrees used to link their whole
.runtime into the main folder's: the live Sales workspace, Tibi's databases and logs. A replay or a script left on its
default path then wrote to live data. After this script:

- `.runtime/` is the worktree's own folder. Only the DT603 paper extract (`opsatlas-sales-foundation`), which tests
  and seeding read, links to the main folder. The live Sales workspace is never linked: a worktree creates its own
  workspace when it needs one.
- `services/sme_interviewer/.runtime/` is the worktree's own folder. Tibi's model weights, recogniser and voice assets
  link read-only to the main folder's; its databases, logs, caches and evaluation outputs start empty here.
- `.venv`, `services/sme_interviewer/.venv` and `frontend/node_modules` link to the main folder's, shared. Never run
  `pip install` or `npm install` in a worktree: it would change the live environment. Create the worktree's own
  environment first if packages must change.

    python scripts/worktree_setup.py ../ai-knowledge-analytics-assistant-<name>
    python scripts/worktree_setup.py ../ai-knowledge-analytics-assistant-<name> --check   # report only
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

MAIN = Path(__file__).resolve().parents[1]
# Tibi's runtime: what is only read (weights, recogniser, voices, interpreters, provisioning records) stays shared.
# recognition-check holds the compiled recogniser the voice service runs (sales_preview.py links it).
TIBI_SHARED = ("models", "hf", "experience", "experience-env", "uv-cache", "conversation-recognizer", "recognition-check",
               "provision-manifest.json", "conversation-runtime.json")
REPO_SHARED = ("opsatlas-sales-foundation",)
ENV_LINKS = (".venv", "services/sme_interviewer/.venv", "frontend/node_modules")


def main_checkout() -> Path:
    """The main folder: the first entry of `git worktree list`."""
    out = subprocess.run(["git", "-C", str(MAIN), "worktree", "list", "--porcelain"], capture_output=True, text=True, check=True)
    return Path(out.stdout.splitlines()[0].split(" ", 1)[1]).resolve()


def live_links(worktree: Path, main: Path) -> list[str]:
    """Links in the worktree's runtime that point into the main folder's writable state."""
    found = []
    for folder in (worktree / ".runtime", worktree / "services/sme_interviewer/.runtime"):
        if folder.is_symlink():
            found.append(f"{folder.relative_to(worktree)} -> {os.readlink(folder)} (the whole folder)")
            continue
        if not folder.is_dir():
            continue
        allowed = REPO_SHARED if folder.name == ".runtime" and folder.parent == worktree else TIBI_SHARED
        for entry in folder.iterdir():
            if entry.is_symlink() and entry.name not in allowed and str(Path(os.readlink(entry)).resolve()).startswith(str(main)):
                found.append(f"{entry.relative_to(worktree)} -> {os.readlink(entry)}")
    return found


def link(target: Path, source: Path) -> None:
    if target.is_symlink() or target.exists():
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    target.symlink_to(source, target_is_directory=source.is_dir())


def own_folder(path: Path) -> None:
    """Make `path` a real folder; if it is a link, remove only the link, never what it points to."""
    if path.is_symlink():
        path.unlink()
    path.mkdir(parents=True, exist_ok=True)


def setup(worktree: Path, main: Path) -> list[str]:
    done = []
    runtime = worktree / ".runtime"
    own_folder(runtime)
    for entry in list(runtime.iterdir()):
        if entry.is_symlink() and entry.name not in REPO_SHARED:
            entry.unlink()
            done.append(f"unlinked .runtime/{entry.name} (live state)")
    for name in REPO_SHARED:
        if (main / ".runtime" / name).exists():
            link(runtime / name, main / ".runtime" / name)
    tibi = worktree / "services/sme_interviewer/.runtime"
    if tibi.is_symlink():
        done.append("services/sme_interviewer/.runtime became the worktree's own folder")
    own_folder(tibi)
    for entry in list(tibi.iterdir()):
        if entry.is_symlink() and entry.name not in TIBI_SHARED:
            entry.unlink()
            done.append(f"unlinked services/sme_interviewer/.runtime/{entry.name} (live state)")
    for name in TIBI_SHARED:
        if (main / "services/sme_interviewer/.runtime" / name).exists():
            link(tibi / name, main / "services/sme_interviewer/.runtime" / name)
    for rel in ENV_LINKS:
        if (main / rel).exists():
            link(worktree / rel, main / rel)
    return done


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("worktree", type=Path)
    parser.add_argument("--check", action="store_true", help="report links into live state; change nothing")
    args = parser.parse_args()
    worktree, main_folder = args.worktree.resolve(), main_checkout()
    if worktree == main_folder:
        print("This is the main folder, which runs OpsAtlas: nothing to do.", file=sys.stderr)
        return 2
    if not (worktree / ".git").exists():
        print(f"{worktree} is not a git worktree.", file=sys.stderr)
        return 2
    if not args.check:
        for line in setup(worktree, main_folder):
            print(line)
    found = live_links(worktree, main_folder)
    for line in found:
        print("live link:", line)
    print("no links into live state" if not found else f"{len(found)} link(s) into live state")
    return 1 if found else 0


if __name__ == "__main__":
    raise SystemExit(main())
