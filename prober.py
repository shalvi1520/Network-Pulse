"""
prober.py - ICMP packet crafting + RTT & Jitter measurement

KEY CONCEPTS:
- RTT  (Round Trip Time)  = time for packet to go TO device and come BACK
- Jitter                  = variation in RTT over multiple pings
                          = std deviation of last N RTT samples
- We craft raw ICMP Echo Request packets using Scapy (not os.system ping)
"""

from scapy.all import IP, ICMP, sr1
import time
import statistics
from collections import deque

# How many past RTT samples to keep per device for jitter calculation
JITTER_WINDOW = 10

# Timeout in seconds waiting for ICMP reply
PROBE_TIMEOUT = 1.5


class DeviceStats:
    """Tracks RTT history and computes jitter for one IP."""

    def __init__(self, ip, mac="unknown"):
        self.ip = ip
        self.mac = mac
        self.rtt_history = deque(maxlen=JITTER_WINDOW)  # last 10 RTTs
        self.last_rtt = None       # most recent RTT in ms
        self.jitter = 0.0          # current jitter in ms
        self.status = "unknown"    # "online" / "timeout" / "unknown"
        self.packet_loss = 0       # count of timeouts
        self.total_probes = 0

    def record(self, rtt_ms):
        """Call this when we get a reply."""
        self.last_rtt = rtt_ms
        self.rtt_history.append(rtt_ms)
        self.status = "online"
        self.total_probes += 1

        # Jitter = std deviation of RTT samples (need at least 2)
        if len(self.rtt_history) >= 2:
            self.jitter = statistics.stdev(self.rtt_history)
        else:
            self.jitter = 0.0

    def record_timeout(self):
        """Call this when probe times out."""
        self.status = "timeout"
        self.packet_loss += 1
        self.total_probes += 1

    @property
    def loss_percent(self):
        if self.total_probes == 0:
            return 0
        return round((self.packet_loss / self.total_probes) * 100, 1)

    @property
    def avg_rtt(self):
        if not self.rtt_history:
            return None
        return round(statistics.mean(self.rtt_history), 2)


def probe_host(ip):
    """
    Craft and send one ICMP Echo Request to `ip`.
    Returns RTT in milliseconds, or None on timeout.

    This is the CORE of the project — we're manually building:
        IP Header → ICMP Header → (no payload needed)
    """
    # Build packet: IP layer / ICMP Echo Request
    packet = IP(dst=ip) / ICMP()

    # Record send time
    t_start = time.time()

    # sr1 = send 1 packet, receive 1 reply (or timeout)
    reply = sr1(packet, timeout=PROBE_TIMEOUT, verbose=0)

    t_end = time.time()

    if reply is None:
        return None  # Timeout — no reply received

    # Check it's actually an ICMP Echo Reply (type=0)
    if reply.haslayer(ICMP) and reply[ICMP].type == 0:
        rtt_ms = (t_end - t_start) * 1000  # convert to milliseconds
        return round(rtt_ms, 2)

    return None  # Got something but not a proper echo reply


def probe_all(device_stats_map):
    """
    Probe every device in the map once.
    Updates each DeviceStats object in-place.

    device_stats_map: dict of { ip_str: DeviceStats }
    """
    for ip, stats in device_stats_map.items():
        rtt = probe_host(ip)
        if rtt is not None:
            stats.record(rtt)
        else:
            stats.record_timeout()


if __name__ == "__main__":
    # Quick test: probe a single host
    test_ip = "8.8.8.8"
    print(f"Probing {test_ip}...")
    rtt = probe_host(test_ip)
    if rtt:
        print(f"RTT: {rtt} ms")
    else:
        print("No reply (timeout)")