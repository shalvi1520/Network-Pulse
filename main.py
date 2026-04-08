"""
main.py - Network Pulse Entry Point

Terminal mode (default):
    sudo python3 main.py

Web UI mode:
    sudo python3 main.py --ui
    Then open http://localhost:5000 in your browser

Optional args:
    sudo python3 main.py --subnet 192.168.0.0/24
    sudo python3 main.py --subnet 192.168.0.0/24 --interval 3 --ui
"""

import argparse
import sys
import time
import webbrowser
import threading

from scanner import scan_network, get_local_subnet
from prober import DeviceStats, probe_all
from dashboard import run_dashboard
from rich.console import Console

console = Console()


def main():
    parser = argparse.ArgumentParser(description="Network Pulse — Real-Time Latency Heatmap")
    parser.add_argument("--subnet",   type=str,   default=None,  help="Target subnet, e.g. 192.168.1.0/24")
    parser.add_argument("--interval", type=float, default=2.0,   help="Seconds between probe cycles (default: 2)")
    parser.add_argument("--ui",       action="store_true",       help="Launch web UI instead of terminal dashboard")
    parser.add_argument("--port",     type=int,   default=8080,  help="Web UI port (default: 8080)")
    args = parser.parse_args()

    if args.subnet:
        subnet = args.subnet
        local_ip = "manual"
    else:
        subnet, local_ip = get_local_subnet()

    console.print(f"\n[bold cyan]NETWORK PULSE[/bold cyan] — Real-Time Latency Heatmap")
    console.print(f"[dim]Your IP: {local_ip}   Subnet: {subnet}[/dim]\n")

    console.print("[yellow]Scanning for devices...[/yellow]")
    devices = scan_network(subnet)

    if not devices:
        console.print("[red]No devices found. Are you on a network? Try running with sudo.[/red]")
        sys.exit(1)

    console.print(f"[green]Found {len(devices)} device(s).[/green]\n")
    for d in devices:
        console.print(f"  [cyan]{d['ip']:<18}[/cyan] {d['mac']}")

    device_stats_map = {}
    for d in devices:
        device_stats_map[d["ip"]] = DeviceStats(ip=d["ip"], mac=d["mac"])

    if args.ui:
        _launch_web_ui(device_stats_map, args.interval, args.port)
    else:
        console.print(f"\n[dim]Starting terminal dashboard (Ctrl+C to stop)...[/dim]\n")
        try:
            run_dashboard(
                device_stats_map=device_stats_map,
                probe_fn=probe_all,
                interval=args.interval
            )
        except KeyboardInterrupt:
            console.print("\n[yellow]Stopped by user. Goodbye![/yellow]")


def _launch_web_ui(device_stats_map, interval, port):
    try:
        from server import run_server, set_device_stats
    except ImportError:
        console.print("[red]Flask not found. Install it: pip install flask[/red]")
        sys.exit(1)

    meta = {"pulse_count": 0, "start_time": time.time()}
    set_device_stats(device_stats_map, meta)

    url = f"http://localhost:{port}"
    console.print(f"\n[bold green]Web UI starting at {url}[/bold green]")
    console.print("[dim]Press Ctrl+C to stop[/dim]\n")

    run_server(port=port)

    threading.Timer(1.2, lambda: webbrowser.open(url)).start()

    try:
        while True:
            probe_all(device_stats_map)
            meta["pulse_count"] += 1
            set_device_stats(device_stats_map, meta)
            time.sleep(interval)
    except KeyboardInterrupt:
        console.print("\n[yellow]Stopped by user. Goodbye![/yellow]")


if __name__ == "__main__":
    main()