"""
scanner.py - ARP-based host discovery
Uses Scapy to broadcast ARP requests and collect responses.
This tells us WHO is on the network (IP + MAC address).
"""

from scapy.all import ARP, Ether, srp
import socket


def get_local_subnet():
    """Auto-detect your machine's subnet (e.g. 192.168.1.0/24)"""
    hostname = socket.gethostname()
    local_ip = socket.gethostbyname(hostname)
    # Build a /24 subnet from local IP
    parts = local_ip.split(".")
    subnet = f"{parts[0]}.{parts[1]}.{parts[2]}.0/24"
    return subnet, local_ip


def scan_network(subnet=None):
    """
    Send ARP broadcast to entire subnet.
    Returns list of dicts: [{"ip": ..., "mac": ...}, ...]
    """
    if subnet is None:
        subnet, _ = get_local_subnet()

    print(f"[*] Scanning subnet: {subnet}")

    # Craft ARP request wrapped in Ethernet broadcast frame
    arp_request = ARP(pdst=subnet)
    broadcast = Ether(dst="ff:ff:ff:ff:ff:ff")
    packet = broadcast / arp_request

    # Send and receive — timeout=2s, verbose=0 means silent
    answered, _ = srp(packet, timeout=2, verbose=0)

    devices = []
    for sent, received in answered:
        devices.append({
            "ip": received.psrc,
            "mac": received.hwsrc
        })

    return devices


if __name__ == "__main__":
    devices = scan_network()
    print(f"\nFound {len(devices)} device(s):\n")
    for d in devices:
        print(f"  IP: {d['ip']:<18}  MAC: {d['mac']}")