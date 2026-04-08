"""
scanner.py - ARP-based host discovery
Uses Scapy to broadcast ARP requests and collect responses.
This tells us WHO is on the network (IP + MAC address).
"""

from scapy.all import ARP, Ether, srp
import socket
import subprocess
import re


def get_local_subnet():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
    except Exception:
        try:
            output = subprocess.check_output(["ifconfig"], text=True)
            matches = re.findall(r"inet (\d+\.\d+\.\d+\.\d+)", output)
            local_ip = next((ip for ip in matches if not ip.startswith("127.")), None)
            if not local_ip:
                raise RuntimeError("Could not determine local IP")
        except Exception as e:
            raise RuntimeError(f"Failed to detect local IP: {e}")

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

    arp_request = ARP(pdst=subnet)
    broadcast = Ether(dst="ff:ff:ff:ff:ff:ff")
    packet = broadcast / arp_request

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