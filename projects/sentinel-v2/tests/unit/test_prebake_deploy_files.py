"""Tests for `_prebake_deploy_files` strict template handling (F3.4).

The function must raise ``FileNotFoundError`` instead of silently skipping a
missing canonical template. Silent skip would let a refactor that moves
``data/deploy_templates/`` ship a half-baked workspace where the agent's bad
``package.json`` is never reverted.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from sentinel_v2.flows.sentinel_loop import _prebake_deploy_files


def test_prebake_raises_on_missing_template(tmp_path: Path) -> None:
    """Pointing at a stack dir that does not exist must raise FileNotFoundError.

    The error message must contain the missing path so operators can grep
    docker logs and find the broken template path immediately.
    """
    workspace = tmp_path / "draft_c1_app"
    workspace.mkdir()

    with pytest.raises(FileNotFoundError) as excinfo:
        _prebake_deploy_files(str(workspace), "myapp", stack="nonexistent_stack")

    assert "nonexistent_stack" in str(excinfo.value)
    assert "Missing canonical template" in str(excinfo.value)


def test_prebake_succeeds_on_valid_stack(tmp_path: Path) -> None:
    """Happy path: real ``node_nestjs`` stack writes infra files + protected sources."""
    workspace = tmp_path / "draft_c1_app"
    workspace.mkdir()

    written = _prebake_deploy_files(str(workspace), "myapp", stack="node_nestjs")

    backend = workspace / "backend"
    assert (backend / "fly.toml").exists()
    assert (backend / "Dockerfile").exists()
    assert (backend / "package.json").exists()
    # Walk-recursive prebake also writes any nested protected source files
    # (e.g. src/config/stripe.config.ts). The infra trio must always be present;
    # nested files are stack-dependent and listed by relative path in `written`.
    assert {"fly.toml", "Dockerfile", "package.json"}.issubset(set(written.keys()))


def test_prebake_writes_canonical_typescript_configs(tmp_path: Path) -> None:
    """tsconfig.json + tsconfig.build.json + nest-cli.json must be pre-baked.

    Without these the agent's `nest build` fails with "Could not find
    TypeScript configuration file 'tsconfig.json'" (observed live: backend
    agent imported PrismaService and Stripe modules but never wrote a
    tsconfig, post-build verification then rejected the draft on attempt 1).
    Pinning here so a future template refactor cannot quietly drop them.
    """
    workspace = tmp_path / "draft_c1_app"
    workspace.mkdir()

    written = _prebake_deploy_files(str(workspace), "myapp", stack="node_nestjs")

    backend = workspace / "backend"
    tsconfig = backend / "tsconfig.json"
    tsconfig_build = backend / "tsconfig.build.json"
    nest_cli = backend / "nest-cli.json"
    assert tsconfig.is_file()
    assert tsconfig_build.is_file()
    assert nest_cli.is_file()
    # Canonical NestJS keys the build pipeline depends on.
    cfg = json.loads(tsconfig.read_text())
    assert cfg["compilerOptions"]["emitDecoratorMetadata"] is True
    assert cfg["compilerOptions"]["experimentalDecorators"] is True
    assert "src/**/*" in cfg["include"]
    nest_cfg = json.loads(nest_cli.read_text())
    assert nest_cfg["sourceRoot"] == "src"
    expected_rels = {"tsconfig.json", "tsconfig.build.json", "nest-cli.json"}
    assert expected_rels.issubset(set(written.keys()))


def test_prebake_writes_canonical_prisma_module_and_service(tmp_path: Path) -> None:
    """PrismaModule + PrismaService must land at the canonical path.

    Build agents reference `import { PrismaService } from '../../prisma/prisma.service'`;
    if the file is not pre-baked the post-build verification gate fails with
    TS2307 (observed live: backend agent imported the path in every service +
    test but never wrote the file, npm run build failed in attempt 1, draft
    auto-rejected). Pinning here so a future template refactor cannot quietly
    drop the file.
    """
    workspace = tmp_path / "draft_c1_app"
    workspace.mkdir()

    written = _prebake_deploy_files(str(workspace), "myapp", stack="node_nestjs")

    backend = workspace / "backend"
    prisma_service = backend / "src" / "prisma" / "prisma.service.ts"
    prisma_module = backend / "src" / "prisma" / "prisma.module.ts"
    assert prisma_service.is_file()
    assert prisma_module.is_file()
    # Canonical export names the build agent imports must be present.
    assert "export class PrismaService" in prisma_service.read_text()
    assert "@Global()" in prisma_module.read_text()
    assert "export class PrismaModule" in prisma_module.read_text()
    # Returned dict uses the relative path as its key, matching how the flow
    # logs the bake summary.
    expected_rels = {"src/prisma/prisma.service.ts", "src/prisma/prisma.module.ts"}
    assert expected_rels.issubset(set(written.keys()))


def test_prebake_substitutes_slug_correctly(tmp_path: Path) -> None:
    """The ``{{SLUG}}`` token in package.json must be replaced with the slug."""
    workspace = tmp_path / "draft_c1_app"
    workspace.mkdir()

    _prebake_deploy_files(str(workspace), "myslug", stack="node_nestjs")

    pkg = json.loads((workspace / "backend" / "package.json").read_text())
    assert pkg["name"] == "myslug-backend"
    # Sanity: the unsubstituted token must not survive in any baked file (walk
    # the whole baked tree, including nested protected source files).
    for path in (workspace / "backend").rglob("*"):
        if path.is_file():
            assert "{{SLUG}}" not in path.read_text(), f"unsubstituted token in {path}"


def test_prebake_raises_when_workspace_missing(tmp_path: Path) -> None:
    """Workspace dir must exist; the function refuses to climb to /."""
    missing = tmp_path / "never_created"

    with pytest.raises(FileNotFoundError) as excinfo:
        _prebake_deploy_files(str(missing), "x")

    assert "workspace_dir" in str(excinfo.value)
