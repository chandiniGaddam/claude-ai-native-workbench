#!/usr/bin/env python3
"""Claude Code PreToolUse hook: block writes to the read-only starter repository.

Reads the hook payload (JSON) on stdin. Exits 2 with a reason on stderr to block the tool
call, or 0 to allow it. Logic lives in src/qe/guard.py (stdlib only).
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from qe.guard import evaluate


def main() -> int:
    # Claude Code treats any non-zero exit other than 2 as non-blocking, so every
    # failure path must return 2 (fail closed).
    try:
        payload = json.load(sys.stdin)
        decision = evaluate(payload)
    except Exception as exc:  # noqa: BLE001
        print(f"BLOCKED by guard_readonly: could not evaluate tool call ({exc!r})", file=sys.stderr)
        return 2
    if not decision.allowed:
        print(f"BLOCKED by guard_readonly: {decision.reason}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
