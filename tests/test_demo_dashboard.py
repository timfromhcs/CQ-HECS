"""The Python dashboard shows synthetic values only (GEMINI.md 3.6 / 3.8)."""

from __future__ import annotations

import importlib.util
import io
import unittest

HAVE_RICH = importlib.util.find_spec("rich") is not None


@unittest.skipUnless(HAVE_RICH, "rich is an optional dependency of the demo dashboard")
class DemoDashboardTests(unittest.TestCase):
    def test_refuses_without_explicit_demo(self):
        from python_bridge.tui_dashboard import DemoModeRequired, run_dashboard_loop

        with self.assertRaises(DemoModeRequired):
            run_dashboard_loop(max_cycles=1, refresh_rate=0.0)

    def test_every_panel_is_labelled_and_versioned(self):
        from rich.console import Console

        from cqhecs import __version__
        from python_bridge.tui_dashboard import DEMO_BANNER, TUIRenderer, TUIRuntimeState

        buffer = io.StringIO()
        console = Console(file=buffer, width=200, record=True)
        renderer = TUIRenderer(console)
        layout = renderer.build_layout()
        renderer.update_layout(layout, TUIRuntimeState())
        console.print(layout)
        text = console.export_text()
        self.assertIn(f"CQ-HECS {__version__}", text)
        self.assertGreaterEqual(text.count(DEMO_BANNER), 5)
        for forbidden in ("2.4.0", "ACTIVE (100% Deterministic)", "Hard Contract", "[V] Force Vulkan"):
            self.assertNotIn(forbidden, text)


if __name__ == "__main__":
    unittest.main()
