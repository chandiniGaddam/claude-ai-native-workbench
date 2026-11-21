"""One owning test per mutated course or learner.

Mutating tests register the record they change here. ``claim`` raises if a different test
already owns it, which turns accidental shared-state coupling into an immediate error.
"""

from __future__ import annotations

# record key -> owning test node id. Statically declared owners go here as tests are added.
OWNERS: dict[str, str] = {}


class OwnershipError(RuntimeError):
    pass


def claim(registry: dict[str, str], record: str, test_id: str) -> None:
    owner = registry.get(record)
    if owner is not None and owner != test_id:
        raise OwnershipError(f"{record} is already owned by {owner}; {test_id} may not mutate it")
    registry[record] = test_id


def release(registry: dict[str, str], record: str, test_id: str) -> None:
    if registry.get(record) == test_id:
        del registry[record]
