#!/usr/bin/env python
"""Assert that deps.yml and its no-op twin remain exact complements.

Why this exists
---------------
`licences` and `vulnerabilities` are required status checks, but `deps.yml` is
path-filtered: it only runs when the dependency graph moved. GitHub does not
resolve a required check that never reports. It sits at "Expected — Waiting for
status", and the pull request can never merge.

`deps-noop.yml` fires on the exact complement of those paths and reports
instantly-passing jobs under the same names, so the contexts always resolve.

That only works while three things stay true:

1. The two `paths:` / `paths-ignore:` lists are identical.
2. The workflow `name:` matches.
3. The job ids and their display names match.

Break any of them and either the real checks run twice (harmless) or every pull
request blocks forever (not harmless). Neither shows up until a pull request is
already open, and the second one looks like a GitHub outage rather than a
mistake in a file nobody edited.

There is no way for CI to test itself here. This is the test.

Usage: python scripts/check_workflow_invariants.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

WORKFLOWS = Path(".github/workflows")
REAL = WORKFLOWS / "deps.yml"
NOOP = WORKFLOWS / "deps-noop.yml"

# PyYAML resolves the bare key `on` to the boolean True, per the YAML 1.1 spec.
ON = True


def _check_names(real: dict, noop: dict) -> list[str]:
    """The workflow name and every job's id and display name must match."""
    problems: list[str] = []

    if real["name"] != noop["name"]:
        problems.append(f"workflow name differs: {real['name']!r} vs {noop['name']!r}")

    if sorted(real["jobs"]) != sorted(noop["jobs"]):
        problems.append(f"job ids differ: {sorted(real['jobs'])} vs {sorted(noop['jobs'])}")
        return problems

    for job in real["jobs"]:
        if real["jobs"][job].get("name") != noop["jobs"][job].get("name"):
            problems.append(f"job {job!r}: display name differs")
    return problems


def _check_paths(real: dict, noop: dict) -> list[str]:
    """`paths` in the real workflow must equal `paths-ignore` in the twin."""
    problems: list[str] = []
    for trigger in ("push", "pull_request"):
        paths = real[ON][trigger].get("paths")
        ignore = noop[ON][trigger].get("paths-ignore")
        if paths != ignore:
            problems.append(
                f"{trigger}: paths and paths-ignore are not complements\n"
                f"      deps.yml      {paths}\n"
                f"      deps-noop.yml {ignore}"
            )
    return problems


def main() -> int:
    """Compare the two workflows and report every divergence."""
    for path in (REAL, NOOP):
        if not path.is_file():
            print(f"missing workflow: {path}")
            return 2

    real = yaml.safe_load(REAL.read_text(encoding="utf-8"))
    noop = yaml.safe_load(NOOP.read_text(encoding="utf-8"))

    problems = _check_names(real, noop) + _check_paths(real, noop)

    if problems:
        print("deps.yml and deps-noop.yml have drifted:\n")
        for problem in problems:
            print(f"  {problem}")
        print(
            "\nA required check that never reports blocks every pull request."
            "\nChange both files in the same commit, or delete the pair."
        )
        return 1

    print("OK: deps.yml and deps-noop.yml are exact complements")
    return 0


if __name__ == "__main__":
    sys.exit(main())
