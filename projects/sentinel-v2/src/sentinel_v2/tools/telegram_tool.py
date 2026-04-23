"""
Telegram Tool — Send messages and handle updates via the Telegram Bot API.
Uses python-telegram-bot v20+ (async).

Approval flow:
1. Flow calls send_approval_poll() → message sent to Kike
2. Kike presses button → _on_callback() fires
3. _on_callback() writes to ApprovalState JSON file
4. Flow's check_approval() polls ApprovalState → proceeds when approved
"""
from __future__ import annotations

import os
import logging
from typing import Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
from telegram.constants import ParseMode

log = logging.getLogger("sentinel_v2.telegram")

# ── Bot setup ────────────────────────────────────────────────────────────────

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")


class TelegramTool:
    """
    Wrapper around python-telegram-bot.
    Sends messages and handles approval callbacks.
    """

    def __init__(self):
        self._token = BOT_TOKEN
        self._app: Optional[Application] = None
        self._approval_callback: Optional[callable] = None

    def set_approval_callback(self, fn: callable) -> None:
        """Register a callback for when Kike responds to an approval."""
        self._approval_callback = fn

    def _set_approval_callback(self, fn: callable) -> None:
        """Alias for set_approval_callback."""
        self.set_approval_callback(fn)

    # ── Outbound: send messages ─────────────────────────────────────────────

    def send_message(self, text: str, chat_id: Optional[str] = None) -> bool:
        """Send a text message. Works sync via asyncio.run."""
        if not self._token:
            log.warning("TELEGRAM_BOT_TOKEN not set — printing instead:\n%s", text)
            return False

        import asyncio

        async def _send():
            app = self._get_app()
            await app.initialize()
            target = chat_id or os.getenv("TELEGRAM_CHAT_ID", "")
            if not target:
                log.error("No TELEGRAM_CHAT_ID set")
                return
            await app.bot.send_message(
                chat_id=int(target),
                text=text,
                parse_mode=ParseMode.MARKDOWN_V2,
            )
            await app.shutdown()

        try:
            asyncio.run(_send())
            return True
        except Exception as e:
            log.error("Failed to send Telegram message: %s", e)
            return False

    def send_approval_poll(
        self,
        summary: str,
        cycle: int,
        chat_id: Optional[str] = None,
    ) -> str:
        """
        Send an approval message with inline buttons.
        Returns a tracking id.
        """
        if not self._token:
            log.info("APPROVAL POLL [cycle %d]:\n%s", cycle, summary)
            return f"cycle-{cycle}"

        keyboard = [
            [
                InlineKeyboardButton("✅ Approve", callback_data=f"approve:{cycle}"),
                InlineKeyboardButton("🔁 Revision", callback_data=f"revision:{cycle}"),
            ],
            [InlineKeyboardButton("⏸ Pause Sentinel", callback_data=f"stop:{cycle}")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        import asyncio

        async def _send():
            app = self._get_app()
            await app.initialize()
            target = chat_id or os.getenv("TELEGRAM_CHAT_ID", "")
            await app.bot.send_message(
                chat_id=int(target),
                text=summary,
                parse_mode=ParseMode.MARKDOWN_V2,
                reply_markup=reply_markup,
            )
            await app.shutdown()

        try:
            asyncio.run(_send())
            return f"cycle-{cycle}"
        except Exception as e:
            log.error("Failed to send approval poll: %s", e)
            return f"cycle-{cycle}"

    # ── Inbound: start polling (blocking) ─────────────────────────────────

    def start_listening(self) -> None:
        """Start the Telegram bot (blocking). Call this once at startup."""
        if not self._token:
            log.warning("Telegram bot token not set — not starting listener")
            return

        app = self._get_app()
        app.add_handlers(
            [
                CommandHandler("start", self._cmd_start),
                CommandHandler("status", self._cmd_status),
                CallbackQueryHandler(self._on_callback),
                MessageHandler(filters.TEXT & ~filters.COMMAND, self._on_message),
            ]
        )
        log.info("Telegram bot starting...")
        app.run_polling(drop_pending_updates=True)

    def _get_app(self) -> Application:
        if self._app is None:
            self._app = Application.builder().token(self._token).build()
        return self._app

    # ── Handlers ─────────────────────────────────────────────────────────────

    async def _cmd_start(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "🛡️ *Sentinel V2 is running*\\n\n"
            "Use /status to see current state\\n\\n"
            "I'll ping you when an opportunity needs your approval\\.",
            parse_mode=ParseMode.MARKDOWN_V2,
        )

    async def _cmd_status(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "✅ Sentinel V2 is running\\n\\n"
            "Awaiting opportunities…",
            parse_mode=ParseMode.MARKDOWN_V2,
        )

    async def _on_callback(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        """Handle inline button presses: approve / revision / stop."""
        from sentinel_v2.tools.approval_state import ApprovalState

        query = update.callback_query
        await query.answer()
        data = query.data or ""

        if ":" not in data:
            return

        action, cycle_str = data.split(":", 1)
        cycle = int(cycle_str)
        approval = ApprovalState()

        if action == "approve":
            await query.edit_message_text(
                text=f"✅ *Approved* — Cycle #{cycle}\\nDeploying…",
                parse_mode=ParseMode.MARKDOWN_V2,
            )
            approval.set_approved(cycle)
        elif action == "revision":
            await query.edit_message_text(
                text=f"🔁 *Revision requested* — Cycle #{cycle}\\nWill rebuild…",
                parse_mode=ParseMode.MARKDOWN_V2,
            )
            approval.set_revision(cycle)
        elif action == "stop":
            await query.edit_message_text(text="⏸ Sentinel paused by user")
            approval.set_stop()
            os.environ["SENTINEL_SHUTDOWN"] = "1"

        if self._approval_callback:
            try:
                self._approval_callback(action, cycle)
            except Exception as e:
                log.error("Approval callback error: %s", e)

    async def _on_message(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        from sentinel_v2.tools.approval_state import ApprovalState

        text = (update.message.text or "").strip().upper()
        approval = ApprovalState()

        if text in ("APPROVE", "APPROVED", "YES", "OK"):
            approval.set_approved(cycle=0)
            if self._approval_callback:
                self._approval_callback("approve", 0)
        elif text.startswith("REVISION") or text.startswith("REV"):
            notes = update.message.text or ""
            approval.set_revision(cycle=0, notes=notes)
            if self._approval_callback:
                self._approval_callback("revision", 0)
