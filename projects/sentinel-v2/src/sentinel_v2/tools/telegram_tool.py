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
import time
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

# ── Rate Limiter (Token Bucket) ──────────────────────────────────────────────


class TokenBucketRateLimiter:
    """
    Token bucket rate limiter for Telegram messages.
    Limits to N messages per minute, configurable via TELEGRAM_RATE_LIMIT env var.
    """

    def __init__(self, max_messages: int | None = None, window_seconds: float = 60.0):
        # Default: 10 messages/min unless TELEGRAM_RATE_LIMIT is set
        if max_messages is None:
            env_limit = os.getenv("TELEGRAM_RATE_LIMIT")
            max_messages = int(env_limit) if env_limit else 10
        self._max_messages = max_messages
        self._window = window_seconds
        self._tokens: list[float] = []

    def acquire(self) -> bool:
        """
        Try to acquire a token.
        Returns True if allowed, False if rate limited.
        """
        now = time.monotonic()

        # Remove tokens that have expired (older than window)
        cutoff = now - self._window
        self._tokens = [t for t in self._tokens if t > cutoff]

        if len(self._tokens) >= self._max_messages:
            log.warning(
                "Telegram rate limit exceeded: %d messages in last %.0f seconds (max: %d)",
                len(self._tokens),
                self._window,
                self._max_messages,
            )
            return False

        self._tokens.append(now)
        return True

    @property
    def remaining(self) -> int:
        """Tokens remaining in current window."""
        now = time.monotonic()
        cutoff = now - self._window
        active = [t for t in self._tokens if t > cutoff]
        return max(0, self._max_messages - len(active))


# ── Bot setup ────────────────────────────────────────────────────────────────

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")


# ── Validate configuration ───────────────────────────────────────────────────

def _validate_config() -> bool:
    """Check BOT_TOKEN and TELEGRAM_CHAT_ID format. Log errors. Returns True if valid."""
    valid = True
    if not BOT_TOKEN or len(BOT_TOKEN) < 40:
        log.error(
            "TELEGRAM_BOT_TOKEN invalid format: expected >= 40 chars, got %d",
            len(BOT_TOKEN),
        )
        valid = False
    if TELEGRAM_CHAT_ID:
        try:
            int(TELEGRAM_CHAT_ID)
        except ValueError:
            log.error(
                "TELEGRAM_CHAT_ID invalid format: cannot convert '%s' to int",
                TELEGRAM_CHAT_ID,
            )
            valid = False
    return valid


_CONFIG_VALID = _validate_config()


class TelegramTool:
    """
    Wrapper around python-telegram-bot.
    Sends messages and handles approval callbacks.
    """


    def __init__(self):
        self._token = BOT_TOKEN if _CONFIG_VALID else ""
        self._chat_id = TELEGRAM_CHAT_ID if _CONFIG_VALID else ""
        self._app: Optional[Application] = None
        self._approval_callback: Optional[callable] = None
        self._rate_limiter = TokenBucketRateLimiter()

    def set_approval_callback(self, fn: callable) -> None:
        """Register a callback for when Kike responds to an approval."""
        self._approval_callback = fn

    def _set_approval_callback(self, fn: callable) -> None:
        """Alias for set_approval_callback."""
        self.set_approval_callback(fn)

    # ── Outbound: send messages ─────────────────────────────────────────────

    def _parse_chat_id(self, chat_id: str | None) -> int | None:
        """Parse and validate chat_id, returning int or None."""
        raw = chat_id or self._chat_id
        if not raw:
            log.error("No TELEGRAM_CHAT_ID set")
            return None
        try:
            return int(raw)
        except ValueError:
            log.error("TELEGRAM_CHAT_ID '%s' cannot be converted to int", raw)
            return None

    def send_message(self, text: str, chat_id: Optional[str] = None) -> bool:
        """Send a text message. Works sync via asyncio.run."""
        if not self._rate_limiter.acquire():
            return False

        if not self._token:
            log.warning("TELEGRAM_BOT_TOKEN not set — printing instead:\n%s", text)
            return False

        target = self._parse_chat_id(chat_id)
        if target is None:
            return False

        import asyncio

        async def _send():
            app = self._get_app()
            await app.initialize()
            await app.bot.send_message(
                chat_id=target,
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
        if not self._rate_limiter.acquire():
            return f"cycle-{cycle}"

        if not self._token:
            log.info("APPROVAL POLL [cycle %d]:\n%s", cycle, summary)
            return f"cycle-{cycle}"

        target = self._parse_chat_id(chat_id)
        if target is None:
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
            await app.bot.send_message(
                chat_id=target,
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
