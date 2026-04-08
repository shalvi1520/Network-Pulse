"""
dashboard.py - Live color-coded terminal heatmap using Rich library

Color logic (RTT-based):
  GREEN   < 20ms   → Excellent
  YELLOW  20–80ms  → Good
  ORANGE  80–150ms → Fair
  RED     > 150ms  → Poor
  GRAY             → Timeout / No reply
"""

from rich.console import Console
from rich.table import Table
from rich.live import Live
from rich.text import Text
from rich.panel import Panel
from rich.columns import Columns
from rich import box
import time

console = Console()


def rtt_color(rtt):
    """Return a Rich color string based on RTT value."""
    if rtt is None:
        return "dim white"
    if rtt < 20:
        return "bright_green"
    if rtt < 80:
        return "yellow"
    if rtt < 150:
        return "dark_orange"
    return "bright_red"


def rtt_label(rtt):
    """Human-readable quality label."""
    if rtt is None:
        return "TIMEOUT"
    if rtt < 20:
        return "EXCELLENT"
    if rtt < 80:
        return "GOOD"
    if rtt < 150:
        return "FAIR"
    return "POOR"


def jitter_color(jitter):
    """Color for jitter value."""
    if jitter < 5:
        return "bright_green"
    if jitter < 20:
        return "yellow"
    return "bright_red"


def make_mini_graph(history, width=10):
    """
    Draw a tiny ASCII sparkline from RTT history.
    e.g.  ▁▂▃▄▅▆▇█
    """
    bars = " ▁▂▃▄▅▆▇█"
    if not history:
        return "─" * width

    vals = list(history)[-width:]
    max_v = max(vals) if max(vals) > 0 else 1
    graph = ""
    for v in vals:
        idx = int((v / max_v) * (len(bars) - 1))
        graph += bars[idx]

    # Pad left if fewer than width samples
    graph = graph.rjust(width, "─")
    return graph


def build_table(device_stats_map, pulse_count, elapsed):
    """Build the Rich table from current device stats."""

    table = Table(
        title=None,
        box=box.SIMPLE_HEAVY,
        header_style="bold cyan",
        show_lines=True,
        expand=True,
    )

    table.add_column("IP Address",      style="bold white",   min_width=16)
    table.add_column("MAC Address",     style="dim white",    min_width=18)
    table.add_column("Last RTT (ms)",   justify="right",      min_width=12)
    table.add_column("Avg RTT (ms)",    justify="right",      min_width=12)
    table.add_column("Jitter (ms)",     justify="right",      min_width=12)
    table.add_column("Loss %",          justify="right",      min_width=8)
    table.add_column("Quality",         justify="center",     min_width=10)
    table.add_column("Trend",           justify="left",       min_width=12)

    for ip, stats in sorted(device_stats_map.items()):
        rtt = stats.last_rtt
        avg = stats.avg_rtt
        jitter = stats.jitter
        loss = stats.loss_percent
        color = rtt_color(rtt)

        # RTT cell
        rtt_text = Text(f"{rtt:.1f}" if rtt else "—", style=color)

        # Avg RTT
        avg_text = Text(f"{avg:.1f}" if avg else "—", style=rtt_color(avg))

        # Jitter
        jitter_text = Text(f"{jitter:.1f}", style=jitter_color(jitter))

        # Loss
        loss_style = "bright_red" if loss > 10 else ("yellow" if loss > 0 else "dim green")
        loss_text = Text(f"{loss}%", style=loss_style)

        # Quality badge
        quality_text = Text(rtt_label(rtt), style=color)

        # Sparkline trend
        trend = make_mini_graph(stats.rtt_history)
        trend_text = Text(trend, style=color)

        table.add_row(
            ip,
            stats.mac,
            rtt_text,
            avg_text,
            jitter_text,
            loss_text,
            quality_text,
            trend_text,
        )

    return table


def build_legend():
    """Small color legend panel."""
    t = Text()
    t.append("● EXCELLENT ", style="bright_green bold")
    t.append("<20ms   ", style="dim")
    t.append("● GOOD ", style="yellow bold")
    t.append("20–80ms   ", style="dim")
    t.append("● FAIR ", style="dark_orange bold")
    t.append("80–150ms   ", style="dim")
    t.append("● POOR ", style="bright_red bold")
    t.append(">150ms", style="dim")
    return Panel(t, title="[bold]RTT Legend[/bold]", border_style="dim cyan", padding=(0, 1))


def build_header(pulse_count, device_count, elapsed):
    t = Text()
    t.append("NETWORK PULSE", style="bold cyan")
    t.append(f"   |   Devices: {device_count}", style="white")
    t.append(f"   |   Pulses: {pulse_count}", style="white")
    t.append(f"   |   Uptime: {int(elapsed)}s", style="dim white")
    t.append("   |   Press Ctrl+C to stop", style="dim")
    return Panel(t, border_style="cyan", padding=(0, 1))


def run_dashboard(device_stats_map, probe_fn, interval=2.0):
    """
    Main loop: probe all devices every `interval` seconds,
    redraw the table live.

    probe_fn: callable(device_stats_map) — updates stats in-place
    """
    pulse_count = 0
    start_time = time.time()

    with Live(console=console, refresh_per_second=2, screen=False) as live:
        while True:
            # Run one probe cycle
            probe_fn(device_stats_map)
            pulse_count += 1
            elapsed = time.time() - start_time

            # Build display
            header = build_header(pulse_count, len(device_stats_map), elapsed)
            table = build_table(device_stats_map, pulse_count, elapsed)
            legend = build_legend()

            live.update(Columns([header], expand=True))  # quick flash
            live.update(
                Panel(
                    table,
                    title=f"[bold cyan]Live Heatmap — Pulse #{pulse_count}[/bold cyan]",
                    border_style="cyan",
                    subtitle=f"[dim]Refreshes every {interval}s[/dim]",
                    padding=(0, 1),
                )
            )

            time.sleep(interval)