"""Read-only guard: it blocks writes into the protected starter repo and allows reads.

The tests build a temporary protected root, so they never touch the real repository.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from qe.config import PROJECT_ROOT
from qe.guard import default_protected_roots, evaluate

pytestmark = pytest.mark.unit

HOOK = PROJECT_ROOT / "scripts" / "guard_readonly.py"


@pytest.fixture
def layout(tmp_path):
    repo = tmp_path / "repo"
    work = tmp_path / "work"
    (repo / "backend").mkdir(parents=True)
    work.mkdir()
    return repo, work


def decide(tool, tool_input, cwd, repo):
    return evaluate({"tool_name": tool, "tool_input": tool_input, "cwd": str(cwd)}, roots=[repo])


# --- file tools -----------------------------------------------------------------------

def test_write_inside_protected_root_is_blocked(layout):
    repo, work = layout
    d = decide("Write", {"file_path": str(repo / "backend" / "pom.xml")}, work, repo)
    assert not d.allowed and "read-only" in d.reason


def test_relative_path_traversal_into_protected_root_is_blocked(layout):
    repo, work = layout
    assert not decide("Edit", {"file_path": "../repo/backend/App.java"}, work, repo).allowed


def test_symlink_pointing_into_protected_root_is_blocked(layout):
    repo, work = layout
    (work / "link").symlink_to(repo, target_is_directory=True)
    assert not decide("Write", {"file_path": str(work / "link" / "x.txt")}, work, repo).allowed


def test_notebook_edit_inside_protected_root_is_blocked(layout):
    repo, work = layout
    assert not decide("NotebookEdit", {"notebook_path": str(repo / "n.ipynb")}, work, repo).allowed


def test_write_inside_project_is_allowed(layout):
    repo, work = layout
    assert decide("Write", {"file_path": str(work / "tests" / "test_x.py")}, work, repo).allowed


def test_sibling_directory_sharing_name_prefix_is_not_protected(layout, tmp_path):
    repo, work = layout
    evil_twin = tmp_path / "repo-copy"
    evil_twin.mkdir()
    assert decide("Write", {"file_path": str(evil_twin / "f")}, work, repo).allowed


def test_non_writing_tools_are_allowed(layout):
    repo, work = layout
    assert decide("Read", {"file_path": str(repo / "backend" / "pom.xml")}, work, repo).allowed


# --- bash -----------------------------------------------------------------------------

BLOCKED_COMMANDS = [
    "rm -rf {R}/backend",
    "echo x > {R}/f.txt",
    "cat a >> {R}/f.txt",
    "echo x | tee {R}/f.txt",
    "sed -i s/a/b/ {R}/backend/pom.xml",
    "cp /tmp/a {R}/b",
    "mv {R}/backend /tmp/stolen",
    "FOO=1 touch {R}/x",
    "sudo rm {R}/x",
    "ls && rm {R}/x",
    "git -C {R} checkout -- .",
    "git -C {R} remote add evil https://example.invalid/x.git",
    "cd {R} && mvn package",
    "cd {R}/backend; npm install",
    "cd {R} && echo x > notes.txt",
    "tar -xzf /tmp/x.tgz -C {R}",
    'echo "unbalanced',
]

ALLOWED_COMMANDS = [
    "cat {R}/backend/pom.xml",
    "grep -rn Course {R}",
    "git -C {R} status --short",
    "git -C {R} log --oneline -5",
    "cd {R} && git diff",
    "cp {R}/backend/pom.xml {W}/pom-copy.xml",
    "tar -tzf {R}/x.tgz",
    "docker build {R}/backend",
    "echo hi > {W}/out.txt",
    "ls -la",
]


@pytest.mark.parametrize("template", BLOCKED_COMMANDS)
def test_bash_write_commands_on_protected_root_are_blocked(layout, template):
    repo, work = layout
    cmd = template.format(R=repo, W=work)
    assert not decide("Bash", {"command": cmd}, work, repo).allowed, cmd


@pytest.mark.parametrize("template", ALLOWED_COMMANDS)
def test_bash_read_only_commands_are_allowed(layout, template):
    repo, work = layout
    cmd = template.format(R=repo, W=work)
    d = decide("Bash", {"command": cmd}, work, repo)
    assert d.allowed, f"{cmd}: {d.reason}"


# --- hook entry point (subprocess, as Claude Code runs it) ----------------------------

def run_hook(payload, env_roots):
    env = {**os.environ, "QE_PROTECTED_ROOTS": str(env_roots)}
    return subprocess.run(
        [sys.executable, "-I", str(HOOK)],
        input=payload if isinstance(payload, str) else json.dumps(payload),
        capture_output=True, text=True, env=env, timeout=30, check=False,
    )


def test_hook_exits_2_with_reason_when_blocking(layout):
    repo, work = layout
    proc = run_hook({"tool_name": "Write", "tool_input": {"file_path": str(repo / "a")}, "cwd": str(work)}, repo)
    assert proc.returncode == 2
    assert "BLOCKED by guard_readonly" in proc.stderr


def test_hook_exits_0_when_allowed(layout):
    repo, work = layout
    proc = run_hook({"tool_name": "Write", "tool_input": {"file_path": str(work / "a")}, "cwd": str(work)}, repo)
    assert proc.returncode == 0, proc.stderr


def test_hook_fails_closed_on_invalid_payload(layout):
    repo, _ = layout
    assert run_hook("not json", repo).returncode == 2


def test_default_protected_root_is_the_real_starter_repo():
    roots = default_protected_roots() if "QE_PROTECTED_ROOTS" not in os.environ else None
    if roots is None:
        pytest.skip("QE_PROTECTED_ROOTS overrides the default in this environment")
    assert roots == [PROJECT_ROOT.parent / "git-demo"]
    assert Path(roots[0], "starter_code", "backend", "pom.xml").is_file()
