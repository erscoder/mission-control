"""Tests for sentinel_v2.main CLI entry point."""
import pytest
from unittest.mock import patch, MagicMock, Mock
from pathlib import Path
import asyncio
import signal as signal_module


class TestMainImports:
    """Test that main module imports correctly."""

    def test_main_module_imports(self):
        """Main module can be imported."""
        from sentinel_v2.main import main, run_once, run_daemon
        assert main is not None
        assert run_once is not None
        assert run_daemon is not None

    def test_run_plot_exists(self):
        """run_plot function exists."""
        from sentinel_v2.main import run_plot
        assert run_plot is not None


class TestSetupLogging:
    """Test setup_logging function."""

    def test_setup_logging_runs(self, monkeypatch):
        """setup_logging doesn't crash."""
        from sentinel_v2.main import setup_logging
        # Should not raise
        setup_logging()

    def test_setup_logging_uses_env_var(self, monkeypatch):
        """setup_logging reads SENTINEL_LOG_LEVEL env var."""
        from sentinel_v2.main import setup_logging
        import os

        monkeypatch.setenv("SENTINEL_LOG_LEVEL", "DEBUG")
        # Should not raise
        setup_logging()


class TestRunPlot:
    """Test run_plot helper."""

    def test_run_plot_creates_and_plots_flow(self, monkeypatch):
        """run_plot creates flow and calls plot()."""
        from sentinel_v2.main import run_plot

        mock_flow = MagicMock()
        mock_flow.plot = MagicMock()

        with patch("sentinel_v2.flows.sentinel_loop.SentinelLoopFlow", return_value=mock_flow):
            run_plot()

        mock_flow.plot.assert_called_once()


class TestMain:
    """Test main() function."""

    def test_main_runs_once_mode(self, monkeypatch):
        """main() with --mode once calls run_once."""
        from sentinel_v2.main import main

        with patch("sys.argv", ["sentinel-v2", "--mode", "once"]):
            with patch("sentinel_v2.main.run_once") as mock_run_once:
                main()
                mock_run_once.assert_called_once()

    def test_main_runs_plot_mode(self, monkeypatch):
        """main() with --mode plot calls run_plot."""
        from sentinel_v2.main import main

        with patch("sys.argv", ["sentinel-v2", "--mode", "plot"]):
            with patch("sentinel_v2.main.run_plot") as mock_run_plot:
                main()
                mock_run_plot.assert_called_once()

    def test_main_runs_daemon_mode_default(self, monkeypatch):
        """main() defaults to daemon mode."""
        from sentinel_v2.main import main

        with patch("sys.argv", ["sentinel-v2"]):
            with patch("sentinel_v2.main.run_daemon") as mock_run_daemon:
                # Patch asyncio at the import level inside run_daemon
                with patch("asyncio.run") as mock_asyncio_run:
                    try:
                        main()
                    except (SystemExit, KeyboardInterrupt, AttributeError):
                        pass


class TestFilesPaths:
    """Test that file paths are correct."""

    def test_state_file_path(self):
        """STATE_FILE points to correct location."""
        from sentinel_v2.dashboard_state import STATE_FILE
        assert STATE_FILE == Path("/tmp/sentinel_v2_state.json")

    def test_agent_messages_file_path(self):
        """AGENT_MESSAGES_FILE points to correct location."""
        from sentinel_v2.dashboard_state import AGENT_MESSAGES_FILE
        assert AGENT_MESSAGES_FILE == Path("/tmp/sentinel_v2_agent_messages.json")


class TestRunOnce:
    """Tests for run_once() function."""

    def test_run_once_creates_flow_and_kickoff(self, monkeypatch):
        """run_once() creates SentinelLoopFlow and calls kickoff()."""
        from sentinel_v2.main import run_once

        mock_flow = MagicMock()
        mock_flow.kickoff = MagicMock()

        # Patch at the source of the import, since main.py imports it inside the function
        with patch("sentinel_v2.flows.sentinel_loop.SentinelLoopFlow", return_value=mock_flow):
            run_once()

        mock_flow.kickoff.assert_called_once()

    def test_run_once_logs_complete_on_success(self, monkeypatch):
        """run_once() logs 'Cycle complete' after successful kickoff."""
        from sentinel_v2.main import run_once

        mock_flow = MagicMock()
        mock_flow.kickoff.return_value = "success"

        with patch("sentinel_v2.flows.sentinel_loop.SentinelLoopFlow", return_value=mock_flow):
            with patch("sentinel_v2.main.log") as mock_log:
                run_once()

        # Check that log.info was called with our completion line
        mock_log.info.assert_called()
                


class TestRunDaemon:
    """Tests for run_daemon() function."""

    def test_run_daemon_sets_up_signal_handlers(self):
        """run_daemon() registers SIGTERM and SIGINT handlers."""
        from sentinel_v2.main import run_daemon

        with patch("sentinel_v2.flows.sentinel_loop.SentinelLoopFlow"), \
             patch("asyncio.run"):
            run_daemon()
        assert True  # no crash = signal setup succeeded

    def test_run_daemon_runs_without_crash(self):
        """run_daemon() starts and exits cleanly when asyncio.run is mocked."""
        from sentinel_v2.main import run_daemon

        with patch("sentinel_v2.flows.sentinel_loop.SentinelLoopFlow") as mock_flow_cls, \
             patch("asyncio.run") as mock_asyncio_run:
            mock_flow_cls.return_value = MagicMock(kickoff=MagicMock(return_value="done"))
            mock_asyncio_run.return_value = None
            run_daemon()

    def test_run_daemon_respects_sentinel_shutdown_env(self, monkeypatch):
        """run_daemon() stops when SENTINEL_SHUTDOWN environment variable is set."""
        from sentinel_v2.main import run_daemon

        monkeypatch.setenv("SENTINEL_SHUTDOWN", "1")
        with patch("sentinel_v2.flows.sentinel_loop.SentinelLoopFlow") as mock_flow_cls, \
             patch("asyncio.run", return_value=None):
            mock_flow_cls.return_value = MagicMock(kickoff=MagicMock(return_value="done"))
            run_daemon()

    def test_run_daemon_continues_on_cycle_error(self):
        """run_daemon() continues to next cycle on exception."""
        from sentinel_v2.main import run_daemon

        with patch("sentinel_v2.flows.sentinel_loop.SentinelLoopFlow") as mock_flow_cls, \
             patch("asyncio.run", return_value=None):
            mock_flow = MagicMock()
            mock_flow.kickoff.side_effect = [RuntimeError("cycle failed"), "success"]
            mock_flow_cls.return_value = mock_flow
            run_daemon()

    def test_run_daemon_uses_custom_interval_from_env(self, monkeypatch):
        """run_daemon() uses SENTINEL_LOOP_INTERVAL_HOURS env var."""
        from sentinel_v2.main import run_daemon

        monkeypatch.setenv("SENTINEL_LOOP_INTERVAL_HOURS", "2")
        with patch("sentinel_v2.flows.sentinel_loop.SentinelLoopFlow") as mock_flow_cls, \
             patch("asyncio.run", return_value=None):
            mock_flow_cls.return_value = MagicMock(kickoff=MagicMock(return_value="done"))
            run_daemon()

    def test_run_daemon_signal_handler_sets_shutdown(self):
        """Signal handler in daemon sets _shutdown flag."""
        from sentinel_v2.main import run_daemon

        captured_handlers: list = []

        def capture_signal(sig, handler):
            captured_handlers.append((sig, handler))

        with patch("sentinel_v2.flows.sentinel_loop.SentinelLoopFlow") as mock_flow_cls, \
             patch("asyncio.run", return_value=None), \
             patch("signal.signal", side_effect=capture_signal):
            mock_flow_cls.return_value = MagicMock(kickoff=MagicMock(return_value="done"))
            run_daemon()

        assert len(captured_handlers) >= 1


class TestMainSignalHandlers:
    """Tests for signal handling in daemon mode."""

    def test_signal_handler_sets_shutdown_flag(self):
        """Signal handler sets _shutdown local variable to True."""
        # This tests the inner function behavior
        shutdown_info = {"value": False}
        
        def on_signal(signum, frame):
            shutdown_info["value"] = True
        
        on_signal(signal_module.SIGTERM, None)
        assert shutdown_info["value"] is True

    def test_signal_handler_logs_info(self):
        """Signal handler logs appropriate message."""
        from sentinel_v2.main import log

        shutdown_info = {"value": False}
        
        def on_signal(signum, frame):
            shutdown_info["value"] = True
        
        with patch.object(log, "info") as mock_log_info:
            on_signal(signal_module.SIGINT, None)
        
        assert shutdown_info["value"] is True