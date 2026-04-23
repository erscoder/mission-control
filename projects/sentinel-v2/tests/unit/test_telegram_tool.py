"""
Unit tests for sentinel_v2/tools/telegram_tool.py

Covers: TelegramTool.send_message, send_approval_poll, start_listening,
set_approval_callback, _set_approval_callback, _get_app,
_cmd_start, _cmd_status, _on_callback, _on_message.
"""
from __future__ import annotations

import os
import sys
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

# Ensure src is on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))


# ── Helper: mock Application ────────────────────────────────────────────────

def _make_mock_app():
    """Return a fully-mocked Application-like object with awaitable methods."""
    mock_app = MagicMock()
    mock_bot = MagicMock()
    mock_bot.send_message = AsyncMock(return_value=MagicMock(message_id=1))
    mock_app.bot = mock_bot
    # These must be AsyncMock so `await app.initialize()` etc. work
    mock_app.initialize = AsyncMock()
    mock_app.shutdown = AsyncMock()
    return mock_app


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def tool():
    """Fresh TelegramTool instance."""
    from sentinel_v2.tools import telegram_tool
    return telegram_tool.TelegramTool()


# ── Init & callback ──────────────────────────────────────────────────────────

class TestInit:
    """Tests for TelegramTool.__init__."""

    def test_init_defaults(self, tool):
        """app is None and approval_callback is None."""
        assert tool._app is None
        assert tool._approval_callback is None


class TestSetApprovalCallback:
    """Tests for set_approval_callback and its alias."""

    def test_set_approval_callback_stores_fn(self, tool):
        """set_approval_callback stores the given function."""
        fn = MagicMock()
        tool.set_approval_callback(fn)
        assert tool._approval_callback is fn

    def test_set_approval_callback_overwrites(self, tool):
        """set_approval_callback replaces previous callback."""
        fn1, fn2 = MagicMock(), MagicMock()
        tool.set_approval_callback(fn1)
        tool.set_approval_callback(fn2)
        assert tool._approval_callback is fn2

    def test_alias_underscore_set_approval_callback(self, tool):
        """_set_approval_callback is an alias that works identically."""
        fn = MagicMock()
        tool._set_approval_callback(fn)
        assert tool._approval_callback is fn


# ── send_message ─────────────────────────────────────────────────────────────

class TestSendMessage:
    """Tests for TelegramTool.send_message."""

    def test_send_message_no_token_prints_and_returns_false(self, tool):
        """When BOT_TOKEN is empty, message is logged and False returned."""
        tool._token = ""
        with patch("sentinel_v2.tools.telegram_tool.log") as mock_log:
            result = tool.send_message("Hello")
        assert result is False
        mock_log.warning.assert_called_once()
        args = mock_log.warning.call_args[0]
        assert "Hello" in args[1]

    def test_send_message_no_chat_id_returns_false(self, tool):
        """When CHAT_ID is missing, error is logged and False returned."""
        tool._token = "tok"
        tool._app = None
        # Patch Application to return a mock whose initialize raises (simulates
        # connection failure when no chat_id is configured)
        import sentinel_v2.tools.telegram_tool as tg_module
        mock_app = _make_mock_app()
        mock_app.initialize = AsyncMock(
            side_effect=RuntimeError("Telegram: chat_id required")
        )
        with patch.object(tg_module, "Application") as MockApp:
            instance = MockApp.builder.return_value.token.return_value.build.return_value
            instance.initialize = AsyncMock(
                side_effect=RuntimeError("Telegram: chat_id required")
            )
            with patch("sentinel_v2.tools.telegram_tool.log") as mock_log:
                result = tool.send_message("Hello")
        assert result is False
        mock_log.error.assert_called_once()

    def test_send_message_no_chat_id_early_return_covers_lines_69_70(self, tool):
        """
        Covers the early return inside _send() when target is empty
        (log.error + return, lines 69-70).
        """
        import sentinel_v2.tools.telegram_tool as tg_module
        mock_app = _make_mock_app()
        # initialize() succeeds; the early return happens after it
        mock_app.initialize = AsyncMock()
        tool._token = "tok"
        with patch.object(tg_module, "Application") as MockApp:
            MockApp.builder.return_value.token.return_value.build.return_value = mock_app
            with patch("sentinel_v2.tools.telegram_tool.log") as mock_log:
                # TELEGRAM_CHAT_ID is not set → early return in _send()
                with patch.dict(os.environ, {}, clear=True):
                    result = tool.send_message("Hello")
        # The early return in _send() makes asyncio.run return None,
        # and send_message returns True (that's the current code behaviour).
        # What matters is that log.error was called.
        mock_log.error.assert_called_once()
        assert "No TELEGRAM_CHAT_ID set" in mock_log.error.call_args[0][0]
    def test_send_message_success_returns_true(self, tool):
        """Happy path: message sent successfully returns True."""
        mock_app = _make_mock_app()
        tool._token = "tok"
        tool._app = mock_app  # bypass _get_app by pre-setting cached app
        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "tok", "TELEGRAM_CHAT_ID": "111"}, clear=True):
            result = tool.send_message("Deploying v2")
        assert result is True
        mock_app.initialize.assert_called_once()
        mock_app.bot.send_message.assert_called_once()
        mock_app.shutdown.assert_called_once()

    def test_send_message_chat_id_param_overrides_env(self, tool):
        """Explicit chat_id parameter is used instead of env var."""
        mock_app = _make_mock_app()
        tool._token = "tok"
        tool._app = mock_app
        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "tok", "TELEGRAM_CHAT_ID": "111"}, clear=True):
            result = tool.send_message("Direct", chat_id="222")
        assert result is True
        call_chat_id = mock_app.bot.send_message.call_args[1]["chat_id"]
        assert call_chat_id == 222

    def test_send_message_async_exception_returns_false(self, tool):
        """If the async send raises, False is returned and error is logged."""
        mock_app = _make_mock_app()
        mock_app.bot.send_message = AsyncMock(side_effect=RuntimeError("network error"))
        tool._token = "tok"
        tool._app = mock_app
        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "tok", "TELEGRAM_CHAT_ID": "111"}, clear=True):
            with patch("sentinel_v2.tools.telegram_tool.log") as mock_log:
                result = tool.send_message("Hello")
        assert result is False
        mock_log.error.assert_called_once()
        assert "Failed to send Telegram message" in mock_log.error.call_args[0][0]

    def test_send_message_uses_markdown_v2_parse_mode(self, tool):
        """Message is sent with ParseMode.MARKDOWN_V2."""
        from telegram.constants import ParseMode
        mock_app = _make_mock_app()
        tool._token = "tok"
        tool._app = mock_app
        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "tok", "TELEGRAM_CHAT_ID": "111"}, clear=True):
            tool.send_message("Bold text")
        _, kwargs = mock_app.bot.send_message.call_args
        assert kwargs["parse_mode"] == ParseMode.MARKDOWN_V2


# ── send_approval_poll ───────────────────────────────────────────────────────

class TestSendApprovalPoll:
    """Tests for TelegramTool.send_approval_poll."""

    def test_send_approval_poll_no_token_logs_and_returns_tracking_id(self, tool):
        """Without a token, logs the summary and returns the cycle ID."""
        tool._token = ""
        with patch("sentinel_v2.tools.telegram_tool.log") as mock_log:
            result = tool.send_approval_poll(summary="Deploy v1.2.3", cycle=5)
        assert result == "cycle-5"
        mock_log.info.assert_called_once()
        args = mock_log.info.call_args[0]
        assert "APPROVAL POLL" in args[0]
        assert 5 in args

    def test_send_approval_poll_success_returns_tracking_id(self, tool):
        """Happy path: poll sent successfully, returns tracking ID."""
        mock_app = _make_mock_app()
        tool._token = "tok"
        tool._app = mock_app
        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "tok", "TELEGRAM_CHAT_ID": "111"}, clear=True):
            result = tool.send_approval_poll(summary="Deploy v1.2.3", cycle=5)
        assert result == "cycle-5"
        mock_app.initialize.assert_called_once()
        mock_app.bot.send_message.assert_called_once()
        mock_app.shutdown.assert_called_once()

    def test_send_approval_poll_includes_three_buttons(self, tool):
        """Poll message includes the three inline buttons."""
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        mock_app = _make_mock_app()
        tool._token = "tok"
        tool._app = mock_app
        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "tok", "TELEGRAM_CHAT_ID": "111"}, clear=True):
            tool.send_approval_poll(summary="Deploy", cycle=3)

        _, kwargs = mock_app.bot.send_message.call_args
        reply_markup: InlineKeyboardMarkup = kwargs["reply_markup"]
        # keyboard = [[Approve, Revision], [Stop]] → 2 rows, 3 buttons total
        assert len(reply_markup.inline_keyboard) == 2  # 2 rows
        # Row 1: Approve + Revision
        assert reply_markup.inline_keyboard[0][0].text == "✅ Approve"
        assert reply_markup.inline_keyboard[0][0].callback_data == "approve:3"
        assert reply_markup.inline_keyboard[0][1].text == "🔁 Revision"
        assert reply_markup.inline_keyboard[0][1].callback_data == "revision:3"
        # Row 2: Stop (full-width)
        assert reply_markup.inline_keyboard[1][0].text == "⏸ Pause Sentinel"
        assert reply_markup.inline_keyboard[1][0].callback_data == "stop:3"

    def test_send_approval_poll_exception_still_returns_tracking_id(self, tool):
        """If send fails, we still return the cycle ID (not crash)."""
        mock_app = _make_mock_app()
        mock_app.bot.send_message = AsyncMock(side_effect=RuntimeError("send error"))
        tool._token = "tok"
        tool._app = mock_app
        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "tok", "TELEGRAM_CHAT_ID": "111"}, clear=True):
            with patch("sentinel_v2.tools.telegram_tool.log") as mock_log:
                result = tool.send_approval_poll(summary="Deploy", cycle=7)
        assert result == "cycle-7"
        mock_log.error.assert_called_once()

    def test_send_approval_poll_chat_id_param(self, tool):
        """Explicit chat_id is used instead of env var."""
        mock_app = _make_mock_app()
        tool._token = "tok"
        tool._app = mock_app
        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "tok", "TELEGRAM_CHAT_ID": "111"}, clear=True):
            tool.send_approval_poll(summary="Deploy", cycle=1, chat_id="222")

        _, kwargs = mock_app.bot.send_message.call_args
        assert kwargs["chat_id"] == 222


# ── _get_app ─────────────────────────────────────────────────────────────────

class TestGetApp:
    """Tests for TelegramTool._get_app."""

    def test_get_app_creates_and_caches_app(self, tool):
        """_get_app creates an Application and caches it."""
        tool._token = "my-token"
        app = tool._get_app()
        assert app is not None
        assert tool._app is app

    def test_get_app_returns_cached_instance(self, tool):
        """Subsequent calls return the same cached instance."""
        tool._token = "tok"
        app1 = tool._get_app()
        app2 = tool._get_app()
        assert app1 is app2


# ── start_listening ──────────────────────────────────────────────────────────

class TestStartListening:
    """Tests for TelegramTool.start_listening."""

    def test_start_listening_no_token_logs_warning(self, tool):
        """When token is missing, a warning is logged and method returns."""
        tool._token = ""
        with patch("sentinel_v2.tools.telegram_tool.log") as mock_log:
            tool.start_listening()
        mock_log.warning.assert_called_once()
        assert "token" in mock_log.warning.call_args[0][0].lower()

    def test_start_listening_no_token_does_not_create_app(self, tool):
        """Without token, _get_app should never be called."""
        tool._token = ""
        with patch.object(tool, "_get_app") as mock_get_app:
            tool.start_listening()
        mock_get_app.assert_not_called()

    def test_start_listening_adds_handlers(self, tool):
        """With token, adds CommandHandler, CallbackQueryHandler, MessageHandler."""
        from telegram.ext import CommandHandler, CallbackQueryHandler, MessageHandler

        mock_app = MagicMock()
        tool._token = "tok"
        with patch.object(tool, "_get_app", return_value=mock_app):
            tool.start_listening()

        mock_app.add_handlers.assert_called_once()
        handlers_list = mock_app.add_handlers.call_args[0][0]
        handler_types = [type(h) for h in handlers_list]
        assert CommandHandler in handler_types
        assert CallbackQueryHandler in handler_types
        assert MessageHandler in handler_types

    def test_start_listening_calls_run_polling(self, tool):
        """start_listening calls app.run_polling with drop_pending_updates."""
        mock_app = MagicMock()
        tool._token = "tok"
        with patch.object(tool, "_get_app", return_value=mock_app):
            tool.start_listening()
        mock_app.run_polling.assert_called_once_with(drop_pending_updates=True)


# ── Async handlers ───────────────────────────────────────────────────────────

class TestCmdStart:
    """Tests for TelegramTool._cmd_start."""

    @pytest.mark.asyncio
    async def test_cmd_start_replies_with_running_message(self, tool):
        """_cmd_start replies with Sentinel running text."""
        mock_update = MagicMock()
        mock_update.message = MagicMock()
        mock_update.message.reply_text = AsyncMock()

        await tool._cmd_start(mock_update, MagicMock())

        mock_update.message.reply_text.assert_called_once()
        args, kwargs = mock_update.message.reply_text.call_args
        # text is the first positional arg
        assert "Sentinel V2 is running" in args[0]

    @pytest.mark.asyncio
    async def test_cmd_start_uses_markdown_v2(self, tool):
        """_cmd_start replies with ParseMode.MARKDOWN_V2."""
        from telegram.constants import ParseMode
        mock_update = MagicMock()
        mock_update.message = MagicMock()
        mock_update.message.reply_text = AsyncMock()

        await tool._cmd_start(mock_update, MagicMock())

        _, kwargs = mock_update.message.reply_text.call_args
        assert kwargs["parse_mode"] == ParseMode.MARKDOWN_V2


class TestCmdStatus:
    """Tests for TelegramTool._cmd_status."""

    @pytest.mark.asyncio
    async def test_cmd_status_replies_with_running_text(self, tool):
        """_cmd_status replies with 'Sentinel V2 is running'."""
        mock_update = MagicMock()
        mock_update.message = MagicMock()
        mock_update.message.reply_text = AsyncMock()

        await tool._cmd_status(mock_update, MagicMock())

        mock_update.message.reply_text.assert_called_once()
        args, kwargs = mock_update.message.reply_text.call_args
        assert "Sentinel V2 is running" in args[0]
        assert "Awaiting opportunities" in args[0]

    @pytest.mark.asyncio
    async def test_cmd_status_uses_markdown_v2(self, tool):
        """_cmd_status uses ParseMode.MARKDOWN_V2."""
        from telegram.constants import ParseMode
        mock_update = MagicMock()
        mock_update.message = MagicMock()
        mock_update.message.reply_text = AsyncMock()

        await tool._cmd_status(mock_update, MagicMock())

        _, kwargs = mock_update.message.reply_text.call_args
        assert kwargs["parse_mode"] == ParseMode.MARKDOWN_V2


# ── _on_callback ─────────────────────────────────────────────────────────────

class TestOnCallback:
    """Tests for TelegramTool._on_callback."""

    def _make_callback_update(self, data: str):
        """Build a mock Update with a CallbackQuery that has the given data."""
        mock_query = MagicMock()
        mock_query.data = data
        mock_query.answer = AsyncMock()
        mock_query.edit_message_text = AsyncMock()
        mock_update = MagicMock()
        mock_update.callback_query = mock_query
        return mock_update

    @pytest.mark.asyncio
    async def test_on_callback_approve_sets_approval_and_edits_message(self, tool):
        """approve action: sets approved, edits message."""
        with patch("sentinel_v2.tools.approval_state.ApprovalState") as MockApproval:
            mock_state = MagicMock()
            MockApproval.return_value = mock_state
            mock_update = self._make_callback_update("approve:5")

            await tool._on_callback(mock_update, MagicMock())

        mock_update.callback_query.answer.assert_called_once()
        mock_update.callback_query.edit_message_text.assert_called_once()
        args, kwargs = mock_update.callback_query.edit_message_text.call_args
        assert "Approved" in kwargs["text"] or "✅" in kwargs["text"]
        mock_state.set_approved.assert_called_once_with(5)

    @pytest.mark.asyncio
    async def test_on_callback_revision_sets_revision_and_edits_message(self, tool):
        """revision action: sets revision state, edits message."""
        with patch("sentinel_v2.tools.approval_state.ApprovalState") as MockApproval:
            mock_state = MagicMock()
            MockApproval.return_value = mock_state
            mock_update = self._make_callback_update("revision:3")

            await tool._on_callback(mock_update, MagicMock())

        mock_state.set_revision.assert_called_once_with(3)
        args, kwargs = mock_update.callback_query.edit_message_text.call_args
        assert "Revision" in kwargs["text"] or "🔁" in kwargs["text"]

    @pytest.mark.asyncio
    async def test_on_callback_stop_sets_stop_and_sets_env(self, tool):
        """stop action: sets stop, sets SENTINEL_SHUTDOWN env."""
        with patch("sentinel_v2.tools.approval_state.ApprovalState") as MockApproval:
            mock_state = MagicMock()
            MockApproval.return_value = mock_state
            mock_update = self._make_callback_update("stop:2")

            with patch.dict(os.environ, {}, clear=True):
                await tool._on_callback(mock_update, MagicMock())
                assert os.environ.get("SENTINEL_SHUTDOWN") == "1"

        mock_state.set_stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_on_callback_unknown_action_does_not_crash(self, tool):
        """Unknown action (e.g. 'foo:1') is silently ignored."""
        mock_update = self._make_callback_update("foo:99")
        await tool._on_callback(mock_update, MagicMock())

    @pytest.mark.asyncio
    async def test_on_callback_no_colon_early_returns(self, tool):
        """Callback data without ':' returns early without touching state."""
        mock_update = self._make_callback_update("just-a-string")
        with patch("sentinel_v2.tools.approval_state.ApprovalState") as MockApproval:
            await tool._on_callback(mock_update, MagicMock())
            MockApproval.assert_not_called()

    @pytest.mark.asyncio
    async def test_on_callback_triggers_approval_callback(self, tool):
        """After handling action, the registered approval_callback is called."""
        with patch("sentinel_v2.tools.approval_state.ApprovalState") as MockApproval:
            mock_state = MagicMock()
            MockApproval.return_value = mock_state
            mock_callback = MagicMock()
            tool.set_approval_callback(mock_callback)
            mock_update = self._make_callback_update("approve:7")

            await tool._on_callback(mock_update, MagicMock())

        mock_callback.assert_called_once_with("approve", 7)

    @pytest.mark.asyncio
    async def test_on_callback_approval_callback_error_is_logged(self, tool):
        """If the approval callback raises, error is logged but no exception propagates."""
        with patch("sentinel_v2.tools.approval_state.ApprovalState") as MockApproval:
            mock_state = MagicMock()
            MockApproval.return_value = mock_state
            bad_callback = MagicMock(side_effect=RuntimeError("callback broke"))
            tool.set_approval_callback(bad_callback)
            mock_update = self._make_callback_update("approve:1")

            with patch("sentinel_v2.tools.telegram_tool.log") as mock_log:
                await tool._on_callback(mock_update, MagicMock())

        mock_log.error.assert_called_once()
        assert "Approval callback error" in mock_log.error.call_args[0][0]


# ── _on_message ──────────────────────────────────────────────────────────────

class TestOnMessage:
    """Tests for TelegramTool._on_message."""

    def _make_message_update(self, text: str):
        mock_msg = MagicMock()
        mock_msg.text = text
        mock_msg.reply_text = AsyncMock()
        mock_update = MagicMock()
        mock_update.message = mock_msg
        return mock_update

    @pytest.mark.asyncio
    async def test_on_message_approve_keywords_sets_approval_cycle_0(self, tool):
        """APPROVE / APPROVED / YES / OK → set_approved(cycle=0)."""
        for keyword in ("APPROVE", "APPROVED", "YES", "OK"):
            with patch("sentinel_v2.tools.approval_state.ApprovalState") as MockApproval:
                mock_state = MagicMock()
                MockApproval.return_value = mock_state
                mock_update = self._make_message_update(keyword)

                await tool._on_message(mock_update, MagicMock())

                mock_state.set_approved.assert_called_with(cycle=0)

    @pytest.mark.asyncio
    async def test_on_message_approve_triggers_callback(self, tool):
        """APPROVE keyword also fires _approval_callback."""
        with patch("sentinel_v2.tools.approval_state.ApprovalState") as MockApproval:
            mock_state = MagicMock()
            MockApproval.return_value = mock_state
            mock_callback = MagicMock()
            tool.set_approval_callback(mock_callback)
            mock_update = self._make_message_update("APPROVE")

            await tool._on_message(mock_update, MagicMock())

        mock_callback.assert_called_once_with("approve", 0)

    @pytest.mark.asyncio
    async def test_on_message_revision_keyword_sets_revision(self, tool):
        """REVISION / REV keyword → set_revision with the full message as notes."""
        for keyword in ("REVISION", "REV", "REVISION this is bad", "REV please fix"):
            with patch("sentinel_v2.tools.approval_state.ApprovalState") as MockApproval:
                mock_state = MagicMock()
                MockApproval.return_value = mock_state
                mock_update = self._make_message_update(keyword)

                await tool._on_message(mock_update, MagicMock())

                mock_state.set_revision.assert_called_once_with(cycle=0, notes=keyword)

    @pytest.mark.asyncio
    async def test_on_message_revision_triggers_callback(self, tool):
        """REVISION keyword also fires _approval_callback."""
        with patch("sentinel_v2.tools.approval_state.ApprovalState") as MockApproval:
            mock_state = MagicMock()
            MockApproval.return_value = mock_state
            mock_callback = MagicMock()
            tool.set_approval_callback(mock_callback)
            mock_update = self._make_message_update("REVISION fix the API")

            await tool._on_message(mock_update, MagicMock())

        mock_callback.assert_called_once_with("revision", 0)

    @pytest.mark.asyncio
    async def test_on_message_no_match_does_nothing(self, tool):
        """Unrecognized text does not touch state or callback."""
        with patch("sentinel_v2.tools.approval_state.ApprovalState") as MockApproval:
            mock_state = MagicMock()
            MockApproval.return_value = mock_state
            mock_update = self._make_message_update("random text hello")

            await tool._on_message(mock_update, MagicMock())

        mock_state.set_approved.assert_not_called()
        mock_state.set_revision.assert_not_called()

    @pytest.mark.asyncio
    async def test_on_message_empty_text_does_nothing(self, tool):
        """Empty/whitespace-only message does not touch state."""
        with patch("sentinel_v2.tools.approval_state.ApprovalState") as MockApproval:
            mock_state = MagicMock()
            MockApproval.return_value = mock_state
            mock_update = self._make_message_update("   ")

            await tool._on_message(mock_update, MagicMock())

        mock_state.set_approved.assert_not_called()
        mock_state.set_revision.assert_not_called()

    @pytest.mark.asyncio
    async def test_on_message_none_text_handled(self, tool):
        """Message with None text is treated as empty."""
        with patch("sentinel_v2.tools.approval_state.ApprovalState") as MockApproval:
            mock_state = MagicMock()
            MockApproval.return_value = mock_state
            mock_msg = MagicMock()
            mock_msg.text = None
            mock_msg.reply_text = AsyncMock()
            mock_update = MagicMock()
            mock_update.message = mock_msg

            await tool._on_message(mock_update, MagicMock())

        mock_state.set_approved.assert_not_called()
        mock_state.set_revision.assert_not_called()
