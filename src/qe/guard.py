"""Read-only protection for the starter repository (the Application Under Test).

Used as a Claude Code PreToolUse hook (scripts/guard_readonly.py). Given a tool call,
decide whether it would write inside a protected root.

- File tools (Edit/Write/MultiEdit/NotebookEdit): blocked if the target path resolves
  inside a protected root. Symlinks and ``..`` are resolved first.
- Bash: a conservative static check. It blocks write-type commands (rm, mv, sed -i,
  output redirection, mutating git subcommands, build tools...) that target a protected
  path, or that run with the working directory inside one. Read-only commands
  (cat, grep, git status/log/show/diff...) are allowed.

This is defence in depth, not a sandbox. An arbitrary program (e.g. ``python x.py``) can
still write files without that being visible in the command line. The deny rules in
.claude/settings.json and the CLAUDE.md policy are the other layers.

Stdlib only: the hook runs under the system interpreter with ``python3 -I``.
"""

from __future__ import annotations

import os
import shlex
from dataclasses import dataclass
from pathlib import Path

FILE_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}

# Commands that modify any path argument they are given.
WRITE_COMMANDS = {
    "rm", "rmdir", "mv", "touch", "mkdir", "chmod", "chown", "chgrp", "ln", "truncate",
    "dd", "tee", "patch", "unzip", "install", "shred", "unlink", "setfacl",
}
# Commands whose last positional argument is the destination.
COPY_COMMANDS = {"cp", "rsync", "scp"}
# Build/package tools that write into their working directory (target/, node_modules/.vite...).
BUILD_TOOLS = {"mvn", "mvnw", "./mvnw", "gradle", "./gradlew", "npm", "npx", "yarn", "pnpm", "vite", "make"}
# git subcommands that do not modify the work tree or refs.
READONLY_GIT = {
    "status", "log", "show", "diff", "rev-parse", "ls-files", "ls-tree", "ls-remote",
    "blame", "grep", "cat-file", "check-ignore", "describe", "shortlog", "reflog", "remote",
    "for-each-ref", "name-rev", "whatchanged", "count-objects", "fsck", "version", "help",
}
SEPARATORS = {";", "&&", "||", "|", "&", "|&", "(", ")"}
REDIRECTS = {">", ">>", ">|", "&>", "&>>"}


@dataclass(frozen=True)
class Decision:
    allowed: bool
    reason: str = ""


def default_protected_roots() -> list[Path]:
    """Roots from QE_PROTECTED_ROOTS (os.pathsep-separated), else ../git-demo next to this project."""
    env = os.environ.get("QE_PROTECTED_ROOTS")
    if env:
        return [Path(p) for p in env.split(os.pathsep) if p]
    project_root = Path(__file__).resolve().parents[2]
    return [project_root.parent / "git-demo"]


def _resolve(path: str, cwd: str) -> Path:
    expanded = os.path.expandvars(os.path.expanduser(path))
    return Path(os.path.realpath(os.path.join(cwd, expanded)))


def _inside(path: Path, roots: list[Path]) -> bool:
    for root in roots:
        real_root = Path(os.path.realpath(root))
        if path == real_root or real_root in path.parents:
            return True
    return False


def check_file_tool(tool_input: dict, cwd: str, roots: list[Path]) -> Decision:
    target = tool_input.get("file_path") or tool_input.get("notebook_path")
    if not target:
        return Decision(True)
    resolved = _resolve(target, cwd)
    if _inside(resolved, roots):
        return Decision(False, f"write to read-only starter repository blocked: {resolved}")
    return Decision(True)


def _segments(command: str) -> list[list[str]]:
    lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    segments: list[list[str]] = [[]]
    for token in lexer:
        if token in SEPARATORS:
            segments.append([])
        else:
            segments[-1].append(token)
    return [s for s in segments if s]


def _path_args(args: list[str]) -> list[str]:
    out = []
    for arg in args:
        if arg.startswith("-"):
            if "=" in arg:
                out.append(arg.split("=", 1)[1])
            continue
        out.append(arg)
    return out


def _git_decision(argv: list[str], cwd: str, roots: list[Path]) -> Decision:
    i, repo_dir = 1, cwd
    while i < len(argv) and argv[i].startswith("-"):
        if argv[i] == "-C" and i + 1 < len(argv):
            repo_dir = str(_resolve(argv[i + 1], cwd))
            i += 2
            continue
        if argv[i] in ("-c", "--git-dir", "--work-tree") and i + 1 < len(argv):
            if argv[i] in ("--git-dir", "--work-tree"):
                repo_dir = str(_resolve(argv[i + 1], cwd))
            i += 2
            continue
        i += 1
    sub = argv[i] if i < len(argv) else ""
    if not _inside(Path(os.path.realpath(repo_dir)), roots):
        return Decision(True)
    if sub in READONLY_GIT:
        rest = argv[i + 1:]
        if sub == "remote" and rest and rest[0] not in ("-v", "show", "get-url"):
            return Decision(False, f"git remote {rest[0]} modifies the starter repository")
        return Decision(True)
    if sub == "branch" and len(argv) == i + 1:
        return Decision(True)
    return Decision(False, f"git {sub or '(no subcommand)'} may modify the starter repository")


def check_bash(command: str, cwd: str, roots: list[Path]) -> Decision:
    try:
        segments = _segments(command)
    except ValueError as exc:  # unbalanced quotes etc.: refuse rather than guess
        return Decision(False, f"could not parse command safely: {exc}")

    for argv in segments:
        # Leading VAR=value assignments.
        while argv and "=" in argv[0] and not argv[0].startswith(("-", "/", ".")):
            argv = argv[1:]
        if not argv:
            continue
        # Output redirections anywhere in the segment.
        for idx, tok in enumerate(argv):
            if tok in REDIRECTS and idx + 1 < len(argv):
                target = _resolve(argv[idx + 1], cwd)
                if _inside(target, roots):
                    return Decision(False, f"redirect into read-only starter repository blocked: {target}")
        argv = [t for idx, t in enumerate(argv) if t not in REDIRECTS and (idx == 0 or argv[idx - 1] not in REDIRECTS)]
        if not argv:
            continue
        cmd = os.path.basename(argv[0]) if argv[0] not in BUILD_TOOLS else argv[0]
        if cmd in ("sudo", "env", "nice", "nohup", "time", "command") and len(argv) > 1:
            return check_bash(shlex.join(argv[1:]), cwd, roots)
        if cmd == "cd":
            cwd = str(_resolve(argv[1], cwd)) if len(argv) > 1 else os.path.expanduser("~")
            continue
        cwd_protected = _inside(Path(os.path.realpath(cwd)), roots)
        paths = [_resolve(p, cwd) for p in _path_args(argv[1:])]
        touches_protected = any(_inside(p, roots) for p in paths)

        if cmd == "git":
            decision = _git_decision(argv, cwd, roots)
            if not decision.allowed:
                return decision
            continue
        if cmd in WRITE_COMMANDS and (touches_protected or (cwd_protected and cmd != "tee")):
            return Decision(False, f"'{cmd}' on read-only starter repository blocked")
        if cmd == "tee" and touches_protected:
            return Decision(False, "'tee' into read-only starter repository blocked")
        in_place = any(a.startswith("-i") or a == "--in-place" for a in argv[1:])
        if cmd in ("sed", "perl") and in_place and (touches_protected or cwd_protected):
            return Decision(False, f"in-place '{cmd}' on read-only starter repository blocked")
        if cmd in COPY_COMMANDS:
            positional = _path_args(argv[1:])
            if positional and _inside(_resolve(positional[-1], cwd), roots):
                return Decision(False, f"'{cmd}' destination inside read-only starter repository blocked")
        if cmd == "tar" and (cwd_protected or touches_protected):
            mode = next((a for a in argv[1:] if not a.startswith("--")), "").lstrip("-")
            if "t" not in mode:  # only listing (-t) is read-only
                return Decision(False, "'tar' writing inside read-only starter repository blocked")
        if (argv[0] in BUILD_TOOLS or cmd in BUILD_TOOLS) and (cwd_protected or touches_protected):
            return Decision(False, f"build tool '{cmd}' would write inside read-only starter repository")
    return Decision(True)


def evaluate(payload: dict, roots: list[Path] | None = None) -> Decision:
    """Decide on a Claude Code PreToolUse payload: {tool_name, tool_input, cwd}."""
    roots = roots if roots is not None else default_protected_roots()
    tool = payload.get("tool_name", "")
    tool_input = payload.get("tool_input") or {}
    cwd = payload.get("cwd") or os.getcwd()
    if tool in FILE_TOOLS:
        return check_file_tool(tool_input, cwd, roots)
    if tool == "Bash":
        return check_bash(tool_input.get("command", ""), cwd, roots)
    return Decision(True)
