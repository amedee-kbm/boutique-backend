#!/usr/bin/env python
"""Fail when a Celery task is declared without an explicit ``name=``.

Why this exists
---------------
A bare ``@shared_task`` registers under a name Celery derives from the module
path — ``apps.users.tasks.send_password_reset_email``. That name is a *string*,
and it is written into two places you do not control:

1. Messages already sitting in the broker, which name the task they want run.
2. ``django_celery_beat`` ``PeriodicTask`` rows, which reference tasks by name.

So the moment anyone moves or renames the module, the registered name changes
silently. In-flight messages address a task that no longer exists, and beat
rows point at nothing. Nothing raises at import time. The failure surfaces in
production, after a deploy, as tasks that simply never run.

Pinning ``name=`` decouples the registered name from the file's location. When
you move a task, keep its name verbatim — the name is the contract.

This is a static check: it parses, it never imports. That matters, because
importing Django tasks requires a settings module and a database.

Usage: python scripts/check_task_names.py [source_root]
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

# Decorators that register a Celery task. Matched on the trailing attribute, so
# `@shared_task`, `@celery.shared_task`, `@app.task` and `@current_app.task`
# all land here.
TASK_DECORATORS = frozenset({"shared_task", "task", "periodic_task"})

SKIP_DIRS = frozenset({"migrations", "tests", "__pycache__", ".venv"})


def _decorator_name(node: ast.expr) -> str | None:
    """Return the trailing identifier of a decorator expression, if any.

    ``@shared_task`` -> "shared_task"; ``@app.task(bind=True)`` -> "task".
    """
    if isinstance(node, ast.Call):
        node = node.func
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Name):
        return node.id
    return None


def _has_explicit_name(node: ast.expr) -> bool:
    """True when the decorator is called with a ``name=`` keyword argument."""
    if not isinstance(node, ast.Call):
        # A bare `@shared_task` cannot carry a name.
        return False
    return any(kw.arg == "name" for kw in node.keywords)


def _suggested_name(path: Path, root: Path, func: str) -> str:
    """Build the name Celery would derive today, so moving the task is a no-op."""
    dotted = path.relative_to(root).with_suffix("").as_posix().replace("/", ".")
    return f"{dotted}.{func}"


def check_file(path: Path, root: Path) -> list[str]:
    """Return one message per unnamed task found in ``path``."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    problems: list[str] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        for decorator in node.decorator_list:
            if _decorator_name(decorator) not in TASK_DECORATORS:
                continue
            if _has_explicit_name(decorator):
                continue
            suggestion = _suggested_name(path, root, node.name)
            problems.append(
                f"  {path}:{node.lineno}  {node.name}() has no explicit name=\n"
                f"      fix: @shared_task(name={suggestion!r}, ...)"
            )
    return problems


def iter_sources(root: Path) -> list[Path]:
    """Every .py file under ``root``, minus generated and test directories."""
    return sorted(p for p in root.rglob("*.py") if not SKIP_DIRS.intersection(p.parts))


def main() -> int:
    """Scan the source root and report every unnamed Celery task."""
    root = Path(sys.argv[1] if len(sys.argv) > 1 else "src")
    if not root.is_dir():
        print(f"source root {root!r} does not exist")
        return 2

    problems = [msg for path in iter_sources(root) for msg in check_file(path, root)]

    if problems:
        print("Celery tasks must declare an explicit name=:\n")
        print("\n".join(problems))
        print(
            "\nA task's registered name is derived from its module path unless you pin it."
            "\nMoving the module then silently orphans queued messages and beat rows."
            "\nWhen moving an existing task, keep its current name verbatim."
        )
        return 1

    print("OK: every Celery task declares an explicit name=")
    return 0


if __name__ == "__main__":
    sys.exit(main())
