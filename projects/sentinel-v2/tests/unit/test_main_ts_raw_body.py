"""Tests for ``_ensure_main_ts_raw_body``.

Closes KG MED-3 sibling of MED-2: the build agent must bootstrap NestJS
with ``NestFactory.create(AppModule, { rawBody: true })`` so the webhook
controller can read ``req.rawBody`` for Stripe-Signature verification. If
the agent forgets, signature verification fails for every Stripe webhook.

Defensive helper: never raises, never fails the build, returns
``{patched: bool, reason: str}``.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from sentinel_v2.flows.sentinel_loop import _ensure_main_ts_raw_body


def _workspace_with_main(tmp_path: Path, main_text: str | None) -> Path:
    workspace = tmp_path / "draft_x"
    backend_src = workspace / "backend" / "src"
    backend_src.mkdir(parents=True)
    if main_text is not None:
        (backend_src / "main.ts").write_text(main_text)
    return workspace


class TestEnsureMainTsRawBody:
    def test_no_op_when_already_set(self, tmp_path: Path):
        text = (
            "import { NestFactory } from '@nestjs/core';\n"
            "import { AppModule } from './app.module';\n"
            "\n"
            "async function bootstrap() {\n"
            "  const app = await NestFactory.create(AppModule, { rawBody: true });\n"
            "  await app.listen(3000);\n"
            "}\n"
            "bootstrap();\n"
        )
        workspace = _workspace_with_main(tmp_path, text)

        result = _ensure_main_ts_raw_body(str(workspace))

        assert result == {"patched": False, "reason": "already_set"}
        assert (workspace / "backend" / "src" / "main.ts").read_text() == text

    def test_patches_single_arg_form(self, tmp_path: Path):
        """NestFactory.create(AppModule) → adds full options object."""
        text = (
            "import { NestFactory } from '@nestjs/core';\n"
            "import { AppModule } from './app.module';\n"
            "\n"
            "async function bootstrap() {\n"
            "  const app = await NestFactory.create(AppModule);\n"
            "  await app.listen(3000);\n"
            "}\n"
            "bootstrap();\n"
        )
        workspace = _workspace_with_main(tmp_path, text)

        result = _ensure_main_ts_raw_body(str(workspace))

        assert result["patched"] is True
        on_disk = (workspace / "backend" / "src" / "main.ts").read_text()
        assert "NestFactory.create(AppModule, { rawBody: true })" in on_disk

    def test_patches_empty_options(self, tmp_path: Path):
        """NestFactory.create(AppModule, {}) → inserts rawBody key."""
        text = (
            "const app = await NestFactory.create(AppModule, {});\n"
        )
        workspace = _workspace_with_main(tmp_path, text)

        result = _ensure_main_ts_raw_body(str(workspace))

        assert result["patched"] is True
        on_disk = (workspace / "backend" / "src" / "main.ts").read_text()
        assert "rawBody: true" in on_disk

    def test_patches_existing_options(self, tmp_path: Path):
        """NestFactory.create(AppModule, { logger: ... }) → appends rawBody."""
        text = (
            "const app = await NestFactory.create(AppModule, { logger: ['error'] });\n"
        )
        workspace = _workspace_with_main(tmp_path, text)

        result = _ensure_main_ts_raw_body(str(workspace))

        assert result["patched"] is True
        on_disk = (workspace / "backend" / "src" / "main.ts").read_text()
        assert "rawBody: true" in on_disk
        assert "logger: ['error']" in on_disk  # original option preserved

    def test_returns_false_when_main_ts_missing(self, tmp_path: Path):
        workspace = _workspace_with_main(tmp_path, None)

        result = _ensure_main_ts_raw_body(str(workspace))

        assert result == {"patched": False, "reason": "main_ts_missing"}

    def test_returns_false_when_no_nestfactory_call(self, tmp_path: Path):
        """Unparseable shape: no NestFactory.create at all."""
        text = (
            "import { Application } from 'express';\n"
            "const app: Application = express();\n"
            "app.listen(3000);\n"
        )
        workspace = _workspace_with_main(tmp_path, text)

        result = _ensure_main_ts_raw_body(str(workspace))

        assert result == {"patched": False, "reason": "no_nestfactory_call"}
        # File untouched.
        assert (workspace / "backend" / "src" / "main.ts").read_text() == text

    def test_idempotent_on_repeat_call(self, tmp_path: Path):
        """Patch twice in a row: second call is a no-op."""
        text = "const app = await NestFactory.create(AppModule);\n"
        workspace = _workspace_with_main(tmp_path, text)

        first = _ensure_main_ts_raw_body(str(workspace))
        second = _ensure_main_ts_raw_body(str(workspace))

        assert first["patched"] is True
        assert second == {"patched": False, "reason": "already_set"}

    def test_patches_generic_typed_bootstrap(self, tmp_path: Path):
        """`NestFactory.create<NestFastifyApplication>(AppModule)` form."""
        text = (
            "import { NestFastifyApplication } from '@nestjs/platform-fastify';\n"
            "const app = await NestFactory.create<NestFastifyApplication>(AppModule);\n"
        )
        workspace = _workspace_with_main(tmp_path, text)

        result = _ensure_main_ts_raw_body(str(workspace))

        assert result["patched"] is True
        on_disk = (workspace / "backend" / "src" / "main.ts").read_text()
        assert "rawBody: true" in on_disk
        # Generic preserved.
        assert "<NestFastifyApplication>" in on_disk

    def test_no_op_on_generic_already_set(self, tmp_path: Path):
        """Generic form with rawBody already present: no-op."""
        text = (
            "const app = await NestFactory.create<NestExpressApplication>(\n"
            "  AppModule,\n"
            "  { rawBody: true },\n"
            ");\n"
        )
        workspace = _workspace_with_main(tmp_path, text)

        result = _ensure_main_ts_raw_body(str(workspace))

        assert result == {"patched": False, "reason": "already_set"}
