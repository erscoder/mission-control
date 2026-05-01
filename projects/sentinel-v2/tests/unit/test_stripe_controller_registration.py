"""Tests for ``_ensure_stripe_controller_registered``.

Closes the prompt-only enforcement gap on the build agent: AppModule must
import and register ``StripeWebhookController`` or the per-app webhook
returns 404 silently while Stripe retries indefinitely. This helper
auto-patches the AppModule when the controller is missing.

The helper is defensive: it never raises and never fails the build.
On unparseable AppModule shape it logs a WARNING and returns
``registered=False`` so the deploy QA verifier surfaces the resulting 404
to the operator.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from sentinel_v2.flows.sentinel_loop import _ensure_stripe_controller_registered


def _make_workspace(tmp_path: Path, app_module_text: str | None) -> Path:
    workspace = tmp_path / "draft_x"
    backend_src = workspace / "backend" / "src"
    backend_src.mkdir(parents=True)
    if app_module_text is not None:
        (backend_src / "app.module.ts").write_text(app_module_text)
    return workspace


class TestEnsureStripeControllerRegistered:
    def test_no_op_when_already_registered(self, tmp_path: Path):
        text = (
            "import { Module } from '@nestjs/common';\n"
            "import { StripeWebhookController } from "
            "'./modules/stripe/stripe.controller';\n"
            "import { OtherController } from './other.controller';\n"
            "\n"
            "@Module({\n"
            "  controllers: [OtherController, StripeWebhookController],\n"
            "  providers: [],\n"
            "})\n"
            "export class AppModule {}\n"
        )
        workspace = _make_workspace(tmp_path, text)

        result = _ensure_stripe_controller_registered(str(workspace))

        assert result == {
            "registered": True,
            "patched": False,
            "reason": "already_registered",
        }
        on_disk = (workspace / "backend" / "src" / "app.module.ts").read_text()
        assert on_disk == text  # untouched

    def test_patches_when_import_and_entry_missing(self, tmp_path: Path):
        text = (
            "import { Module } from '@nestjs/common';\n"
            "import { OtherController } from './other.controller';\n"
            "\n"
            "@Module({\n"
            "  controllers: [OtherController],\n"
            "  providers: [],\n"
            "})\n"
            "export class AppModule {}\n"
        )
        workspace = _make_workspace(tmp_path, text)

        result = _ensure_stripe_controller_registered(str(workspace))

        assert result["registered"] is True
        assert result["patched"] is True
        on_disk = (workspace / "backend" / "src" / "app.module.ts").read_text()
        assert (
            "import { StripeWebhookController } from "
            "'./modules/stripe/stripe.controller';" in on_disk
        )
        assert "StripeWebhookController" in on_disk
        assert "OtherController, StripeWebhookController" in on_disk

    def test_patches_when_only_controllers_entry_missing(self, tmp_path: Path):
        """Import already present but agent forgot to add to controllers list."""
        text = (
            "import { Module } from '@nestjs/common';\n"
            "import { StripeWebhookController } from "
            "'./modules/stripe/stripe.controller';\n"
            "import { OtherController } from './other.controller';\n"
            "\n"
            "@Module({\n"
            "  controllers: [OtherController],\n"
            "  providers: [],\n"
            "})\n"
            "export class AppModule {}\n"
        )
        workspace = _make_workspace(tmp_path, text)

        result = _ensure_stripe_controller_registered(str(workspace))

        assert result["registered"] is True
        assert result["patched"] is True
        on_disk = (workspace / "backend" / "src" / "app.module.ts").read_text()
        # Import not duplicated: appears exactly twice (import statement + array entry).
        assert on_disk.count("StripeWebhookController") == 2
        assert "OtherController, StripeWebhookController" in on_disk

    def test_patches_empty_controllers_array(self, tmp_path: Path):
        text = (
            "import { Module } from '@nestjs/common';\n"
            "\n"
            "@Module({\n"
            "  controllers: [],\n"
            "  providers: [],\n"
            "})\n"
            "export class AppModule {}\n"
        )
        workspace = _make_workspace(tmp_path, text)

        result = _ensure_stripe_controller_registered(str(workspace))

        assert result["registered"] is True
        assert result["patched"] is True
        on_disk = (workspace / "backend" / "src" / "app.module.ts").read_text()
        assert "controllers: [StripeWebhookController]" in on_disk

    def test_handles_trailing_comma_in_controllers(self, tmp_path: Path):
        text = (
            "import { Module } from '@nestjs/common';\n"
            "import { OtherController } from './other.controller';\n"
            "\n"
            "@Module({\n"
            "  controllers: [\n"
            "    OtherController,\n"
            "  ],\n"
            "  providers: [],\n"
            "})\n"
            "export class AppModule {}\n"
        )
        workspace = _make_workspace(tmp_path, text)

        result = _ensure_stripe_controller_registered(str(workspace))

        assert result["registered"] is True
        assert result["patched"] is True
        on_disk = (workspace / "backend" / "src" / "app.module.ts").read_text()
        # Trailing-comma form preserved; new entry inserted.
        assert "OtherController" in on_disk
        assert "StripeWebhookController" in on_disk

    def test_returns_false_when_app_module_missing(self, tmp_path: Path):
        workspace = _make_workspace(tmp_path, None)  # no app.module.ts

        result = _ensure_stripe_controller_registered(str(workspace))

        assert result == {
            "registered": False,
            "patched": False,
            "reason": "app_module_missing",
        }

    def test_returns_false_when_no_controllers_array(self, tmp_path: Path):
        """Unparseable shape: no controllers: [...] array at all.

        The agent produced something we cannot safely auto-patch. Log a WARNING
        and let the deploy phase surface the failure.
        """
        text = (
            "import { Module } from '@nestjs/common';\n"
            "\n"
            "@Module({\n"
            "  imports: [SomeOtherModule],\n"
            "  providers: [],\n"
            "})\n"
            "export class AppModule {}\n"
        )
        workspace = _make_workspace(tmp_path, text)

        result = _ensure_stripe_controller_registered(str(workspace))

        assert result == {
            "registered": False,
            "patched": False,
            "reason": "no_controllers_array",
        }
        # File untouched on this failure mode.
        on_disk = (workspace / "backend" / "src" / "app.module.ts").read_text()
        assert on_disk == text
