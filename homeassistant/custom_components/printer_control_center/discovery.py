"""Advanced route-aware endpoint discovery for Bambu-compatible printers."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import ipaddress
import logging
from pathlib import Path
import select
import socket
import struct
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Iterable

_LOGGER = logging.getLogger(__name__)

SSDP_MULTICAST = ("239.255.255.250", 1900)
DISCOVERY_PORTS = (2021, 1900)
DEFAULT_PORTS = (8883, 990, 6000, 322, 21, 22)
MAX_ALLOWED_HOSTS = 8192
TRUSTED_SELECTION_SOURCES = frozenset(
    {"configured-endpoint", "explicit-endpoint", "local-discovery"}
)


@dataclass
class DiscoveryCandidate:
    host: str
    serial: str = ""
    name: str = ""
    model: str = ""
    sources: set[str] = field(default_factory=set)
    open_ports: set[int] = field(default_factory=set)

    @property
    def mqtt_port_open(self) -> bool:
        return 8883 in self.open_ports

    @property
    def selection_trusted(self) -> bool:
        return bool(self.sources.intersection(TRUSTED_SELECTION_SOURCES))

    @property
    def mqtt_ready(self) -> bool:
        """Return whether this endpoint is safe for Bambu MQTT selection."""
        return self.mqtt_port_open and self.selection_trusted

    @property
    def label(self) -> str:
        parts = [self.name or self.model or "Bambu-compatible endpoint", self.host]
        if self.serial:
            parts.append(self.serial)
        if self.open_ports:
            parts.append("Ports " + ",".join(str(port) for port in sorted(self.open_ports)))
        if self.sources:
            parts.append("Sources " + ",".join(sorted(self.sources)))
        return " · ".join(parts)

    def merge(self, other: "DiscoveryCandidate") -> None:
        if not self.serial and other.serial:
            self.serial = other.serial
        if not self.name and other.name:
            self.name = other.name
        if not self.model and other.model:
            self.model = other.model
        self.sources.update(other.sources)
        self.open_ports.update(other.open_ports)


@dataclass
class ScanReport:
    started_at: str
    finished_at: str
    profile: str
    scanned_hosts: int
    candidates: list[DiscoveryCandidate]
    selected_host: str = ""
    selected_source: str = ""
    error: str = ""

    @property
    def summary(self) -> str:
        if self.error:
            return f"error: {self.error}"
        selected = self.selected_host or "none"
        return (
            f"{len(self.candidates)} candidate(s), {self.scanned_hosts} host(s), "
            f"selected={selected}, profile={self.profile}"
        )


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _clean_ipv4(value: str) -> str:
    value = str(value or "").strip()
    if not value:
        return ""
    try:
        return str(ipaddress.IPv4Address(value))
    except ipaddress.AddressValueError:
        return ""


def parse_csv_hosts(raw: str) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for token in str(raw or "").replace(";", ",").replace("\n", ",").split(","):
        host = _clean_ipv4(token)
        if host and host not in seen:
            result.append(host)
            seen.add(host)
    return result


def parse_ports(raw: str, profile: str) -> list[int]:
    presets = {
        "quick": [8883],
        "balanced": [8883, 990, 6000, 322],
        "deep": list(DEFAULT_PORTS),
    }
    result = list(presets.get(profile, presets["balanced"]))
    for token in str(raw or "").replace(";", ",").replace(" ", ",").split(","):
        token = token.strip()
        if not token:
            continue
        try:
            port = int(token)
        except ValueError as exc:
            raise ValueError(f"Invalid TCP port: {token}") from exc
        if not 1 <= port <= 65535:
            raise ValueError(f"Invalid TCP port: {token}")
        if port not in result:
            result.append(port)
    return sorted(result)


def parse_networks(raw: str) -> list[ipaddress.IPv4Network]:
    networks: list[ipaddress.IPv4Network] = []
    for token in str(raw or "").replace(";", ",").replace("\n", ",").split(","):
        token = token.strip()
        if not token:
            continue
        network = ipaddress.ip_network(token, strict=False)
        if not isinstance(network, ipaddress.IPv4Network):
            raise ValueError(f"IPv6 is not supported for endpoint scan: {token}")
        networks.append(network)
    return networks


def _host_in_networks(host: str, networks: Iterable[ipaddress.IPv4Network]) -> bool:
    """Return whether an IPv4 host belongs to an explicit/directly routed network."""
    try:
        address = ipaddress.IPv4Address(host)
    except ipaddress.AddressValueError:
        return False
    return any(address in network for network in networks)


def _headers(payload: bytes) -> dict[str, str]:
    text = payload.decode("utf-8", errors="replace")
    result: dict[str, str] = {}
    for line in text.replace("\r\n", "\n").split("\n"):
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        result[key.strip().lower()] = value.strip()
    return result


def _parse_discovery_packet(payload: bytes, peer: tuple[str, int]) -> DiscoveryCandidate | None:
    headers = _headers(payload)
    haystack = payload.decode("utf-8", errors="replace").lower()
    if "bambulab" not in haystack and "urn:bambulab-com:device:3dprinter" not in haystack:
        return None

    raw_host = headers.get("location") or headers.get("devip.bambu.com") or peer[0]
    host = (
        raw_host.replace("http://", "")
        .replace("https://", "")
        .split("/", 1)[0]
        .split(":", 1)[0]
    )
    host = _clean_ipv4(host)
    if not host:
        return None

    serial = headers.get("usn", "")
    if "::" in serial:
        serial = serial.split("::", 1)[0]
    if serial.lower().startswith("uuid:"):
        serial = serial[5:]

    return DiscoveryCandidate(
        host=host,
        serial=serial,
        name=headers.get("devname.bambu.com", ""),
        model=headers.get("devmodel.bambu.com", ""),
        sources={"local-discovery"},
    )


def discover_broadcast(serial: str = "", timeout_seconds: float = 2.5) -> list[DiscoveryCandidate]:
    """Listen locally for Bambu SSDP-like announcements and probe multicast."""
    sockets: list[socket.socket] = []
    found: dict[str, DiscoveryCandidate] = {}

    for port in DISCOVERY_PORTS:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("", port))
        except OSError:
            sock.bind(("", 0))
        sock.setblocking(False)
        sockets.append(sock)

    probe = (
        "M-SEARCH * HTTP/1.1\r\n"
        "HOST: 239.255.255.250:1900\r\n"
        'MAN: "ssdp:discover"\r\n'
        "MX: 1\r\n"
        "ST: urn:bambulab-com:device:3dprinter:1\r\n"
        "\r\n"
    ).encode("ascii")

    for sock in sockets:
        try:
            sock.sendto(probe, SSDP_MULTICAST)
        except OSError:
            _LOGGER.debug("Unable to send multicast discovery probe", exc_info=True)

    deadline = time.monotonic() + timeout_seconds
    try:
        while time.monotonic() < deadline:
            readable, _, _ = select.select(sockets, [], [], max(0.0, deadline - time.monotonic()))
            if not readable:
                break
            for sock in readable:
                try:
                    payload, peer = sock.recvfrom(65535)
                except OSError:
                    continue
                candidate = _parse_discovery_packet(payload, peer)
                if candidate is None:
                    continue
                if serial and candidate.serial and candidate.serial != serial:
                    continue
                found[candidate.host] = candidate
    finally:
        for sock in sockets:
            sock.close()

    return sorted(found.values(), key=lambda item: ipaddress.ip_address(item.host))


def arp_neighbors() -> list[str]:
    """Read IPv4 neighbors visible in the current network namespace."""
    result: list[str] = []
    path = Path("/proc/net/arp")
    if not path.is_file():
        return result

    for line in path.read_text(encoding="utf-8", errors="replace").splitlines()[1:]:
        parts = line.split()
        if not parts:
            continue
        host = _clean_ipv4(parts[0])
        if host:
            result.append(host)
    return sorted(set(result), key=ipaddress.ip_address)


def _decode_proc_ipv4(value: str) -> str:
    packed = struct.pack("<I", int(value, 16))
    return socket.inet_ntoa(packed)


def connected_tcp_endpoints() -> list[str]:
    """Read remote IPv4 endpoints from the current namespace TCP table."""
    result: set[str] = set()
    path = Path("/proc/net/tcp")
    if not path.is_file():
        return []

    for line in path.read_text(encoding="utf-8", errors="replace").splitlines()[1:]:
        parts = line.split()
        if len(parts) < 4:
            continue
        remote = parts[2]
        state = parts[3]
        if ":" not in remote or state == "0A":  # LISTEN
            continue
        host_hex, _port_hex = remote.split(":", 1)
        try:
            host = _decode_proc_ipv4(host_hex)
        except (ValueError, OSError):
            continue
        host = _clean_ipv4(host)
        if host and host != "0.0.0.0":
            result.add(host)

    return sorted(result, key=ipaddress.ip_address)


def routed_networks(max_prefix_hosts: int = 256) -> list[ipaddress.IPv4Network]:
    """Read small directly visible IPv4 route networks from /proc/net/route."""
    result: list[ipaddress.IPv4Network] = []
    path = Path("/proc/net/route")
    if not path.is_file():
        return result

    for line in path.read_text(encoding="utf-8", errors="replace").splitlines()[1:]:
        parts = line.split()
        if len(parts) < 8:
            continue
        destination_hex, mask_hex = parts[1], parts[7]
        try:
            destination = _decode_proc_ipv4(destination_hex)
            mask = _decode_proc_ipv4(mask_hex)
            network = ipaddress.IPv4Network((destination, mask), strict=False)
        except (ValueError, OSError, ipaddress.NetmaskValueError):
            continue

        if network.prefixlen == 0:
            continue
        if network.num_addresses > max_prefix_hosts:
            continue
        result.append(network)

    return sorted(set(result), key=lambda item: (int(item.network_address), item.prefixlen))


def _tcp_open(host: str, port: int, timeout_seconds: float) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout_seconds):
            return True
    except OSError:
        return False


def _probe_host(host: str, ports: Iterable[int], timeout_seconds: float) -> DiscoveryCandidate | None:
    open_ports: set[int] = set()
    for port in ports:
        if _tcp_open(host, port, timeout_seconds):
            open_ports.add(port)
    if not open_ports:
        return None
    return DiscoveryCandidate(host=host, sources={"tcp-probe"}, open_ports=open_ports)


def advanced_scan(
    *,
    serial: str = "",
    configured_host: str = "",
    explicit_hosts: str = "",
    subnet_cidrs: str = "",
    custom_ports: str = "",
    profile: str = "balanced",
    timeout_ms: int = 300,
    workers: int = 128,
    max_hosts: int = 2048,
    include_broadcast: bool = True,
    include_neighbors: bool = True,
    include_connections: bool = True,
    include_routes: bool = True,
) -> ScanReport:
    """Discover endpoints with seed, connection, neighbor, route and active scans."""
    started = _utc_now()
    timeout_seconds = max(0.05, min(5.0, int(timeout_ms) / 1000))
    worker_count = max(1, min(256, int(workers)))
    host_limit = max(1, min(MAX_ALLOWED_HOSTS, int(max_hosts)))
    ports = parse_ports(custom_ports, profile)

    merged: dict[str, DiscoveryCandidate] = {}
    probe_hosts: set[str] = set()

    def add(candidate: DiscoveryCandidate) -> None:
        existing = merged.get(candidate.host)
        if existing is None:
            merged[candidate.host] = candidate
        else:
            existing.merge(candidate)

    configured = _clean_ipv4(configured_host)
    if configured:
        probe_hosts.add(configured)
        add(DiscoveryCandidate(host=configured, sources={"configured-endpoint"}))

    for host in parse_csv_hosts(explicit_hosts):
        probe_hosts.add(host)
        add(DiscoveryCandidate(host=host, sources={"explicit-endpoint"}))

    if include_neighbors:
        for host in arp_neighbors():
            probe_hosts.add(host)
            add(DiscoveryCandidate(host=host, sources={"arp-neighbor"}))

    explicit_networks = parse_networks(subnet_cidrs)
    local_route_networks = routed_networks()
    connection_networks = [*explicit_networks, *local_route_networks]

    if include_connections:
        for host in connected_tcp_endpoints():
            if not _host_in_networks(host, connection_networks):
                continue
            probe_hosts.add(host)
            add(DiscoveryCandidate(host=host, sources={"connected-endpoint"}))

    networks = list(explicit_networks)
    if include_routes:
        networks.extend(local_route_networks)

    network_hosts: list[str] = []
    for network in networks:
        for host in network.hosts():
            network_hosts.append(str(host))

    for host in network_hosts:
        probe_hosts.add(host)

    if len(probe_hosts) > host_limit:
        raise ValueError(
            f"Advanced scan would inspect {len(probe_hosts)} hosts. "
            f"Configured limit is {host_limit}. Use smaller CIDRs or increase the limit."
        )

    if include_broadcast:
        for candidate in discover_broadcast(serial=serial):
            add(candidate)
            probe_hosts.add(candidate.host)

    with ThreadPoolExecutor(max_workers=min(worker_count, max(1, len(probe_hosts)))) as pool:
        futures = {
            pool.submit(_probe_host, host, ports, timeout_seconds): host
            for host in sorted(probe_hosts, key=ipaddress.ip_address)
        }
        for future in as_completed(futures):
            host = futures[future]
            try:
                candidate = future.result()
            except Exception:
                _LOGGER.debug("Probe failed for %s", host, exc_info=True)
                continue
            if candidate is not None:
                add(candidate)

    candidates = sorted(
        [candidate for candidate in merged.values() if candidate.open_ports],
        key=lambda item: (
            0 if item.mqtt_ready else 1,
            0 if "configured-endpoint" in item.sources else 1,
            int(ipaddress.ip_address(item.host)),
        ),
    )

    selected_host = ""
    selected_source = ""

    # Prefer a validated configured endpoint. This is particularly important
    # across site-to-site VPNs where broadcast discovery cannot cross routers.
    if configured:
        selected = next(
            (
                item for item in candidates
                if item.host == configured and item.mqtt_ready
            ),
            None,
        )
        if selected:
            selected_host = selected.host
            selected_source = "configured-endpoint"

    if not selected_host:
        exact = [
            item
            for item in candidates
            if item.serial and item.serial == serial and item.mqtt_ready
        ]
        if len(exact) == 1:
            selected_host = exact[0].host
            selected_source = "serial-match"

    if not selected_host:
        mqtt_ready = [item for item in candidates if item.mqtt_ready]
        if len(mqtt_ready) == 1:
            selected_host = mqtt_ready[0].host
            selected_source = "single-trusted-mqtt-endpoint"

    return ScanReport(
        started_at=started,
        finished_at=_utc_now(),
        profile=profile,
        scanned_hosts=len(probe_hosts),
        candidates=candidates,
        selected_host=selected_host,
        selected_source=selected_source,
    )