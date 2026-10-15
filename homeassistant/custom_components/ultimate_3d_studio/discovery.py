"""Local Bambu printer discovery for Ultimate 3D Studio."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import ipaddress
import select
import socket
import time

SSDP_MULTICAST = ("239.255.255.250", 1900)
DISCOVERY_PORTS = (2021, 1900)


@dataclass(frozen=True, slots=True)
class DiscoveryCandidate:
    """One locally announced Bambu-compatible printer."""

    host: str
    serial: str = ""
    name: str = ""
    model: str = ""
    mqtt_reachable: bool = False

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def _clean_ipv4(value: str) -> str:
    value = str(value or "").strip()
    if not value:
        return ""
    try:
        return str(ipaddress.IPv4Address(value))
    except ipaddress.AddressValueError:
        return ""


def _headers(payload: bytes) -> dict[str, str]:
    text = payload.decode("utf-8", errors="replace")
    headers: dict[str, str] = {}
    for line in text.replace("\r\n", "\n").split("\n"):
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        headers[key.strip().lower()] = value.strip()
    return headers


def _parse_packet(payload: bytes, peer: tuple[str, int]) -> DiscoveryCandidate | None:
    text = payload.decode("utf-8", errors="replace").lower()
    if "bambulab" not in text and "urn:bambulab-com:device:3dprinter" not in text:
        return None

    headers = _headers(payload)
    raw_host = headers.get("devip.bambu.com") or headers.get("location") or peer[0]
    host = (
        str(raw_host)
        .replace("http://", "")
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
        mqtt_reachable=_tcp_open(host, 8883, 0.5),
    )


def _tcp_open(host: str, port: int, timeout: float) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def discover(timeout_seconds: float = 3.0) -> tuple[DiscoveryCandidate, ...]:
    """Probe and listen for local Bambu SSDP-like announcements."""
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
            pass

    deadline = time.monotonic() + max(0.5, min(10.0, timeout_seconds))
    try:
        while time.monotonic() < deadline:
            readable, _, _ = select.select(
                sockets,
                [],
                [],
                max(0.0, deadline - time.monotonic()),
            )
            if not readable:
                break
            for sock in readable:
                try:
                    payload, peer = sock.recvfrom(65535)
                except OSError:
                    continue
                candidate = _parse_packet(payload, peer)
                if candidate is not None:
                    found[candidate.host] = candidate
    finally:
        for sock in sockets:
            sock.close()

    return tuple(
        sorted(found.values(), key=lambda item: ipaddress.ip_address(item.host))
    )
