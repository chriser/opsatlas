"""A worktree gets its own writable runtime (AUDIT F15): live state is never linked, read-only assets are."""
import os
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/worktree_setup.py"


IDENTITY = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}


def git(*args, cwd):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, env={**os.environ, **IDENTITY})


def test_live_state_is_unlinked_and_read_only_assets_stay_shared(tmp_path):
    main = tmp_path / "main"
    (main / "scripts").mkdir(parents=True)
    (main / "scripts/worktree_setup.py").write_text(SCRIPT.read_text())
    git("init", "-q", cwd=main)
    git("add", ".", cwd=main)
    git("commit", "-q", "-m", "init", cwd=main)
    live_workspace = main / ".runtime/opsatlas-sales"
    live_workspace.mkdir(parents=True)
    (live_workspace / "iam.db").write_text("live")
    (main / ".runtime/opsatlas-sales-foundation").mkdir()
    tibi = main / "services/sme_interviewer/.runtime"
    (tibi / "models").mkdir(parents=True)
    (tibi / "interviews.sqlite").write_text("live")
    worktree = tmp_path / "wt"
    git("worktree", "add", "-q", str(worktree), cwd=main)
    (worktree / ".runtime").mkdir()
    (worktree / ".runtime/opsatlas-sales").symlink_to(live_workspace)  # the hazard the script removes
    (worktree / "services/sme_interviewer").mkdir(parents=True)
    (worktree / "services/sme_interviewer/.runtime").symlink_to(tibi)

    def run(*extra):
        return subprocess.run([sys.executable, str(worktree / "scripts/worktree_setup.py"), str(worktree), *extra],
                              capture_output=True, text=True)

    assert run("--check").returncode == 1  # reported, nothing changed yet
    assert (worktree / ".runtime/opsatlas-sales").is_symlink()
    done = run()
    assert done.returncode == 0, done.stdout + done.stderr
    assert not (worktree / ".runtime/opsatlas-sales").exists()
    assert (worktree / ".runtime/opsatlas-sales-foundation").is_symlink()
    own_tibi = worktree / "services/sme_interviewer/.runtime"
    assert own_tibi.is_dir() and not own_tibi.is_symlink()
    assert (own_tibi / "models").is_symlink() and not (own_tibi / "interviews.sqlite").exists()
    assert (live_workspace / "iam.db").read_text() == "live" and (tibi / "interviews.sqlite").read_text() == "live"
    assert subprocess.run([sys.executable, str(worktree / "scripts/worktree_setup.py"), str(main)], capture_output=True).returncode == 2
