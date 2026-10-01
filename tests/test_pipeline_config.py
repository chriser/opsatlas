"""The build pipeline and the supply chain (ARCH F3): what the review of 27 September found is kept fixed."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_the_github_mirror_runs_only_after_a_successful_branch_build_under_the_full_branch_name():
    pipeline = (ROOT / "azure-pipelines.yml").read_text()
    mirror = pipeline[pipeline.index("Mirror to GitHub") - 900:pipeline.index("Mirror to GitHub") + 300]
    assert "condition: and(succeeded(), startsWith(variables['Build.SourceBranch'], 'refs/heads/'))" in mirror
    assert "Build.SourceBranchName" not in pipeline  # the last segment only: claude/x would arrive as x
    assert 'BRANCH="${BUILD_SOURCEBRANCH#refs/heads/}"' in mirror and 'HEAD:refs/heads/${BRANCH}' in mirror


def test_ci_installs_the_pinned_set_and_audits_it():
    pipeline = (ROOT / "azure-pipelines.yml").read_text()
    assert "pip install -r requirements.lock" in pipeline and "requirements-dev.txt" not in pipeline
    assert "pip-audit -r requirements.lock" in pipeline


def test_the_lock_pins_every_requirement_exactly():
    pins = {}
    for line in (ROOT / "requirements.lock").read_text().splitlines():
        if line and not line.startswith("#"):
            name, version = line.split("==")
            pins[re.sub(r"\[.*\]", "", name).lower().replace("_", "-")] = version
    wanted = [re.split(r"[><=\[]", line.strip())[0].lower() for f in ("requirements.txt", "requirements-dev.txt")
              for line in (ROOT / f).read_text().splitlines() if line.strip() and not line.startswith(("#", "-r"))]
    missing = [w for w in wanted if w not in pins]
    assert not missing, missing
    assert all(re.fullmatch(r"[\w.+!-]+", v) for v in pins.values())


def test_the_avatar_library_is_bundled_at_a_pinned_version_not_fetched_from_a_cdn():
    page = (ROOT / "frontend/src/AvatarLabPage.tsx").read_text()
    assert "esm.sh" not in page and 'import("@anam-ai/js-sdk")' in page
    package = (ROOT / "frontend/package.json").read_text()
    assert re.search(r'"@anam-ai/js-sdk": "\d+\.\d+\.\d+"', package)  # exact, no caret


def test_ci_runs_every_javascript_test_and_declares_what_the_code_imports():
    """AUDIT F6: one JavaScript test file never ran because CI named the files; the live code imported httpx and
    websockets without declaring them."""
    pipeline = (ROOT / "azure-pipelines.yml").read_text()
    assert "node --test tests/*.mjs" in pipeline
    declared = (ROOT / "requirements.txt").read_text()
    assert "httpx>=" in declared and "websockets>=" in declared


def test_every_branch_builds_on_the_python_that_runs_opsatlas():
    """AUDIT F8: CI ran only for main unless queued by hand, and on Python 3.11 while OpsAtlas runs on 3.12."""
    pipeline = (ROOT / "azure-pipelines.yml").read_text()
    assert "trigger:\n  branches:\n    include:\n      - '*'" in pipeline
    assert "versionSpec: '3.12'" in pipeline and "3.11" not in pipeline
