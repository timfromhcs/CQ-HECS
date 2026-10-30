"""
CQ-HECS Rich TUI dashboard — DEMO ONLY.

No value shown by this dashboard is a measurement. VRAM, bond dimension,
residual energy, throughput, attention weights and "jitter" are generated
from presets, sine functions and timer noise. GEMINI.md 3.6 forbids showing
such values as live telemetry, so the dashboard runs only with ``demo=True``
(``--demo`` on the command line) and labels every frame ``SIMULATED DATA``.
"""

from __future__ import annotations
import argparse
import sys
import time
import math
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from typing import Dict, List, Optional

from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.progress import ProgressBar
from rich.text import Text
from rich.live import Live

from python_bridge.cq_hecs import (
    VulkanComputeScheduler
)

try:
    from cqhecs import __version__ as _VERSION
except ImportError:  # pragma: no cover - python_bridge used without the package
    _VERSION = "unknown"

DEMO_BANNER = "SIMULATED DATA - NOT A MEASUREMENT"


class DemoModeRequired(RuntimeError):
    """Raised when the dashboard is started without explicitly asking for demo data."""


class TUIRuntimeState:
    """Synthetic demo values; none of them is read from a device or a run."""
    def __init__(self):
        self.active_vram_mb: float = 4.531
        self.vram_ceiling_mb: float = 120.0
        self.mps_bond_chi: int = 64
        self.num_qubits: int = 300
        self.lambda_res: float = 0.0042
        self.entropy_jitter_ns: float = 45.2
        self.nudge_active: bool = False
        self.nudge_val: int = 0
        self.attention_weights: Dict[str, float] = {
            "Alpha (ARX)": 0.22,
            "Beta (Phase)": 0.28,
            "Gamma (SAT)": 0.18,
            "Delta (SVD)": 0.14,
            "Epsilon (Shield)": 0.18
        }
        self.solved_states_per_sec: float = 14520.0
        self.rejected_branches_per_sec: float = 89450.0
        self.jitter_history: List[float] = [30.0 + 20.0 * math.sin(i * 0.3) for i in range(24)]
        self.qpc_drift_ppm: float = 0.0
        self.cycle_count: int = 0


class TUIRenderer:
    """Builds and renders the Rich TUI layout."""
    def __init__(self, console: Optional[Console] = None):
        self.console = console or Console()

    def build_layout(self) -> Layout:
        layout = Layout(name="root")
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="main_body", ratio=1),
            Layout(name="footer", size=3)
        )
        layout["main_body"].split_row(
            Layout(name="left_col", ratio=1),
            Layout(name="right_col", ratio=1)
        )
        layout["left_col"].split_column(
            Layout(name="vram_widget", ratio=1),
            Layout(name="mps_widget", ratio=1)
        )
        layout["right_col"].split_column(
            Layout(name="attention_widget", ratio=1),
            Layout(name="entropy_widget", ratio=1)
        )
        return layout

    def render_header(self, state: TUIRuntimeState) -> Panel:
        title = Text(f" CQ-HECS {_VERSION} :: DEMO DASHBOARD :: {DEMO_BANNER} ", style="bold white on red")
        sub = Text(
            f" [Demo frame #{state.cycle_count:06d}]  All values below are synthetic presets and "
            "sine/timer noise; no device or simulation is being observed. ",
            style="dim cyan",
        )
        grid = Table.grid(expand=True)
        grid.add_column(justify="center")
        grid.add_row(title)
        grid.add_row(sub)
        return Panel(grid, style="blue")

    def render_vram_widget(self, state: TUIRuntimeState) -> Panel:
        vram_ratio = min(max(state.active_vram_mb / state.vram_ceiling_mb, 0.0), 1.0)
        color = "green" if vram_ratio < 0.7 else ("yellow" if vram_ratio < 0.9 else "red")
        
        table = Table.grid(padding=(0, 1))
        table.add_column(style="bold white", width=18)
        table.add_column()
        
        table.add_row("VRAM (demo):", f"[{color}]{state.active_vram_mb:.3f} MB[/{color}]")
        table.add_row("Ceiling (demo):", f"{state.vram_ceiling_mb:.1f} MB")
        table.add_row("Margin (demo):", f"{(state.vram_ceiling_mb - state.active_vram_mb):.2f} MB")
        
        pbar = ProgressBar(total=state.vram_ceiling_mb, completed=state.active_vram_mb, width=32, style="blue", complete_style=color)
        
        content = Table.grid(padding=(1, 0))
        content.add_row(table)
        content.add_row(pbar)
        
        return Panel(content, title=f"[bold cyan]VRAM gauge — {DEMO_BANNER}[/bold cyan]", border_style=color)

    def render_mps_widget(self, state: TUIRuntimeState) -> Panel:
        table = Table(expand=True, box=None, padding=(0, 1))
        table.add_column("Metric", style="dim white")
        table.add_column("Value", style="bold yellow")

        table.add_row("MPS Qubit Count", f"{state.num_qubits} Qubits (1D Chain)")
        table.add_row("Bond Dimension (chi)", f"{state.mps_bond_chi} (Capacity: 64)")
        table.add_row("Residual Energy (Lambda_res)", f"{state.lambda_res:.6f}")
        table.add_row("Candidate Throughput", f"{state.solved_states_per_sec:,.0f} states/sec")
        table.add_row("Cuckoo Pruning Rate", f"{state.rejected_branches_per_sec:,.0f} rejected/sec")

        return Panel(table, title=f"[bold yellow]MPS metrics — {DEMO_BANNER}[/bold yellow]", border_style="yellow")

    def render_attention_widget(self, state: TUIRuntimeState) -> Panel:
        table = Table(expand=True, box=None, padding=(0, 1))
        table.add_column("Sub-Space", style="bold white", width=18)
        table.add_column("Attention", width=10)
        table.add_column("Load Bar", width=16)

        for space, weight in state.attention_weights.items():
            pct = weight * 100.0
            bar_len = int(weight * 14)
            bar_str = "[" + "#" * bar_len + "-" * (14 - bar_len) + "]"
            table.add_row(space, f"{pct:5.1f}%", f"[magenta]{bar_str}[/magenta]")

        return Panel(table, title=f"[bold magenta]Workload weights — {DEMO_BANNER}[/bold magenta]", border_style="magenta")

    def render_entropy_widget(self, state: TUIRuntimeState) -> Panel:
        # Mini oscilloscope for QPC hardware jitter (ASCII-safe across all Windows terminals)
        min_v = min(state.jitter_history or [0.0])
        max_v = max(state.jitter_history or [1.0])
        span = max(max_v - min_v, 1e-6)
        
        wave_chars = [".", ":", "-", "=", "+", "*", "#", "%", "@"]
        wave_str = ""
        for val in state.jitter_history[-24:]:
            norm = (val - min_v) / span
            idx = int(norm * (len(wave_chars) - 1))
            idx = min(max(idx, 0), len(wave_chars) - 1)
            wave_str += wave_chars[idx]

        grid = Table.grid(padding=(0, 1))
        grid.add_column(style="bold white", width=18)
        grid.add_column()

        grid.add_row("Timer noise:", f"[green]{state.entropy_jitter_ns:.2f} (demo units)[/green]")
        grid.add_row("Drift (demo):", f"[yellow]{state.qpc_drift_ppm:+.2f}[/yellow]")
        grid.add_row("Nudge (demo):", "[bold green]YES[/bold green]" if state.nudge_active else "[dim]no[/dim]")
        grid.add_row("Trace:", f"[cyan]{wave_str}[/cyan]")

        return Panel(grid, title=f"[bold green]Timer-noise trace — {DEMO_BANNER}[/bold green]", border_style="green")

    def render_footer(self) -> Panel:
        text = Text(f"  Ctrl+C exits  |  {DEMO_BANNER}  |  for real runs use `cq-hecs` (Python package CLI)", style="dim white on grey23")
        return Panel(text, style="grey23")

    def update_layout(self, layout: Layout, state: TUIRuntimeState) -> None:
        layout["header"].update(self.render_header(state))
        layout["vram_widget"].update(self.render_vram_widget(state))
        layout["mps_widget"].update(self.render_mps_widget(state))
        layout["attention_widget"].update(self.render_attention_widget(state))
        layout["entropy_widget"].update(self.render_entropy_widget(state))
        layout["footer"].update(self.render_footer())


def run_dashboard_loop(max_cycles: Optional[int] = None, refresh_rate: float = 0.1, demo: bool = False):
    """Run the demo dashboard. Refuses unless ``demo`` is True (GEMINI.md 3.6)."""
    if not demo:
        raise DemoModeRequired(
            "the dashboard shows synthetic values only; start it with --demo to "
            "acknowledge that nothing it displays is a measurement"
        )
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            _ = None

    console = Console(safe_box=True, highlight=False)
    renderer = TUIRenderer(console)
    layout = renderer.build_layout()
    state = TUIRuntimeState()
    scheduler = VulkanComputeScheduler()

    cycle = 0
    with Live(layout, console=console, refresh_per_second=10, screen=False):
        try:
            while True:
                cycle += 1
                state.cycle_count = cycle

                # Synthetic demo values (timer noise and sine waves), not telemetry.
                ent = scheduler.harvest_timing_jitter()
                jitter = (ent % 100) * 0.8 + 15.0
                state.entropy_jitter_ns = jitter
                state.jitter_history.append(jitter)
                if len(state.jitter_history) > 32:
                    state.jitter_history.pop(0)

                # Nudge trigger on random entropy spikes
                state.nudge_active = (ent % 17 == 0)
                state.nudge_val = 1 if (ent & 1) else 7

                # Workload metric aggregation dynamic variation
                attn = scheduler.aggregate_workload_metrics(
                    carry_pressure=0.5 + 0.3 * math.sin(cycle * 0.2),
                    phase_cancellation=0.6 + 0.2 * math.cos(cycle * 0.15),
                    sat_violation_ratio=0.3,
                    residual_frobenius_energy=0.01,
                    lyapunov_lambda=0.8
                )
                state.attention_weights = {
                    "Alpha (ARX)": attn["alpha_weight"],
                    "Beta (Phase)": attn["beta_weight"],
                    "Gamma (SAT)": attn["gamma_weight"],
                    "Delta (SVD)": attn["delta_weight"],
                    "Epsilon (Shield)": attn["epsilon_weight"]
                }

                # Synthetic VRAM curve for the demo; no device is queried.
                state.active_vram_mb = 4.531 + 0.6 * math.sin(cycle * 0.1)

                renderer.update_layout(layout, state)
                time.sleep(refresh_rate)

                if max_cycles is not None and cycle >= max_cycles:
                    break
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CQ-HECS demo dashboard (synthetic data only)")
    parser.add_argument("--demo", action="store_true", help="Required: acknowledge that all values are synthetic")
    parser.add_argument("--cycles", type=int, default=None, help="Number of cycles to run (default: infinite)")
    parser.add_argument("--rate", type=float, default=0.1, help="Refresh delay in seconds (default: 0.1)")
    args = parser.parse_args()

    try:
        run_dashboard_loop(max_cycles=args.cycles, refresh_rate=args.rate, demo=args.demo)
    except DemoModeRequired as exc:
        parser.error(str(exc))
