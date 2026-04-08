"""
main.py - Network Pulse Entry Point

Run with:
    sudo python3 main.py

Optional args:
    sudo python3 main.py --subnet 192.168.0.0/24
    sudo python3 main.py --subnet 192.168.0.0/24 --interval 3
"""

import argparse
import sys
from scanner import scan_network, get_local_subnet
from prober import DeviceStats, probe_all
from dashboard import run_dashboard
from rich.console import Console

console = Console()


def main():
    parser = argparse.ArgumentParser(description="Network Pulse — Real-Time Latency Heatmap")
    parser.add_argument("--subnet",   type=str,   default=None, help="Target subnet, e.g. 192.168.1.0/24")
    parser.add_argument("--interval", type=float, default=2.0,  help="Seconds between probe cycles (default: 2)")
    args = parser.parse_args()

    # --- Step 1: Detect subnet ---
    if args.subnet:
        subnet = args.subnet
        local_ip = "manual"
    else:
        subnet, local_ip = get_local_subnet()

    console.print(f"\n[bold cyan]NETWORK PULSE[/bold cyan] — Real-Time Latency Heatmap")
    console.print(f"[dim]Your IP: {local_ip}   Subnet: {subnet}[/dim]\n")

    # --- Step 2: Discover devices via ARP ---
    console.print("[yellow]Scanning for devices...[/yellow]")
    devices = scan_network(subnet)

    if not devices:
        console.print("[red]No devices found. Are you on a network? Try running with sudo.[/red]")
        sys.exit(1)

    console.print(f"[green]Found {len(devices)} device(s).[/green]\n")
    for d in devices:
        console.print(f"  [cyan]{d['ip']:<18}[/cyan] {d['mac']}")

    # --- Step 3: Initialize stats objects ---
    device_stats_map = {}
    for d in devices:
        device_stats_map[d["ip"]] = DeviceStats(ip=d["ip"], mac=d["mac"])

    console.print(f"\n[dim]Starting live dashboard (Ctrl+C to stop)...[/dim]\n")

    # --- Step 4: Launch live dashboard ---
    try:
        run_dashboard(
            device_stats_map=device_stats_map,
            probe_fn=probe_all,
            interval=args.interval
        )
    except KeyboardInterrupt:
        console.print("\n[yellow]Stopped by user. Goodbye![/yellow]")


if __name__ == "__main__":
    main()