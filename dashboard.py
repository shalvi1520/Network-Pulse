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
    if jitter < 5:
        return "bright_green"
    if jitter < 20:
        return "yellow"
    return "bright_red"


def make_mini_graph(history, width=10):
    bars = " ▁▂▃▄▅▆▇█"
    if not history:
        return "─" * width

    vals = list(history)[-width:]
    max_v = max(vals) if max(vals) > 0 else 1
    graph = ""
    for v in vals:
        idx = int((v / max_v) * (len(bars) - 1))
        graph += bars[idx]

    graph = graph.rjust(width, "─")
    return graph


def build_table(device_stats_map, pulse_count, elapsed):

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

        rtt_text = Text(f"{rtt:.1f}" if rtt else "—", style=color)

        avg_text = Text(f"{avg:.1f}" if avg else "—", style=rtt_color(avg))

        jitter_text = Text(f"{jitter:.1f}", style=jitter_color(jitter))

        loss_style = "bright_red" if loss > 10 else ("yellow" if loss > 0 else "dim green")
        loss_text = Text(f"{loss}%", style=loss_style)

        quality_text = Text(rtt_label(rtt), style=color)

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
    pulse_count = 0
    start_time = time.time()

    with Live(console=console, refresh_per_second=2, screen=False) as live:
        while True:
            probe_fn(device_stats_map)
            pulse_count += 1
            elapsed = time.time() - start_time

            header = build_header(pulse_count, len(device_stats_map), elapsed)
            table = build_table(device_stats_map, pulse_count, elapsed)
            legend = build_legend()

            live.update(Columns([header], expand=True))  
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