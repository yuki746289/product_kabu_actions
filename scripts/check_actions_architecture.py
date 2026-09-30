# Created: 2026-09-30T19:35:00+09:00
"""Fail fast when the product_kabu Actions execution architecture is violated.

Canonical architecture:
- GitHub Actions runs in public yuki746289/product_kabu_actions.
- Private yuki746289/product_kabu is checked out only as runtime core.
- The private core must not contain .github/workflows/*.yml or *.yaml.
- docs/ACTIONS_MIGRATION.md must exist and contain the canonical rules.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

EXPECTED_ACTIONS_REPO = "yuki746289/product_kabu_actions"
REQUIRED_RULE_SNIPPETS = (
    "`product_kabu` では GitHub Actions を実行しない。",
    "`product_kabu_actions` の public runner で実行する。",
    "`product_kabu` 側に `.github/workflows/*.yml` を再追加しない。",
)


def _git(core: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(core), *args],
        text=True,
        encoding="utf-8",
    ).strip()


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--core-dir", type=Path, default=Path("core"))
    p.add_argument("--expected-core-sha", default="")
    p.add_argument("--expected-actions-repo", default=EXPECTED_ACTIONS_REPO)
    return p.parse_args()


def main() -> int:
    a = parse_args()
    core = a.core_dir.resolve()
    errors: list[str] = []

    actual_actions_repo = os.environ.get("GITHUB_REPOSITORY", "")
    if actual_actions_repo and actual_actions_repo != a.expected_actions_repo:
        errors.append(
            f"Actions repository mismatch: {actual_actions_repo} != {a.expected_actions_repo}"
        )

    if not core.is_dir():
        errors.append(f"Private core checkout missing: {core}")
        actual_sha = ""
    else:
        try:
            actual_sha = _git(core, "rev-parse", "HEAD")
        except Exception as exc:  # noqa: BLE001
            actual_sha = ""
            errors.append(f"Cannot resolve private core SHA: {exc}")

    if a.expected_core_sha and actual_sha and actual_sha != a.expected_core_sha:
        errors.append(
            f"Private core SHA mismatch: {actual_sha} != {a.expected_core_sha}"
        )

    migration = core / "docs" / "ACTIONS_MIGRATION.md"
    if not migration.is_file():
        errors.append(f"Canonical Actions rule missing: {migration}")
    else:
        rule_text = migration.read_text(encoding="utf-8")
        for snippet in REQUIRED_RULE_SNIPPETS:
            if snippet not in rule_text:
                errors.append(f"Canonical Actions rule snippet missing: {snippet}")

    workflow_dir = core / ".github" / "workflows"
    private_workflows: list[Path] = []
    if workflow_dir.is_dir():
        private_workflows.extend(sorted(workflow_dir.glob("*.yml")))
        private_workflows.extend(sorted(workflow_dir.glob("*.yaml")))
    if private_workflows:
        errors.append(
            "Private core contains forbidden GitHub Actions workflows: "
            + ", ".join(str(p.relative_to(core)) for p in private_workflows)
        )

    print("Actions runner repository :", actual_actions_repo or "(local)")
    print("Expected runner repository:", a.expected_actions_repo)
    print("Private core directory     :", core)
    print("Private core SHA           :", actual_sha or "(unresolved)")
    print("Expected core SHA          :", a.expected_core_sha or "(not specified)")
    print("Migration rule             :", "PASS" if migration.is_file() else "FAIL")
    print("Private workflow count     :", len(private_workflows))

    if errors:
        for err in errors:
            print(f"::error::{err}")
        print("Actions architecture gate  : FAIL")
        return 1

    print("Actions architecture gate  : PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
