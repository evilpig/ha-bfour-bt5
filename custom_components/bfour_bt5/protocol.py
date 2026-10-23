"""Decode temperature notifications, never advertisements or configuration replies."""


def parse_temperatures(packet: bytes, probe_count: int) -> tuple[float | None, ...]:
    """Decode big-endian tenths of Celsius; FFFF means missing probe.

    This is the older BT5 layout. BF-30 compatibility must be checked against
    the physical display. Reject other message types rather than guessing.
    """
    if not 1 <= probe_count <= 6:
        raise ValueError("Probe count must be between 1 and 6")
    if len(packet) < 2 + 2 * probe_count or packet[:2] != b"\x55\x00":
        raise ValueError("Not a complete BT5 temperature notification")
    values = []
    for index in range(probe_count):
        offset = 2 + 2 * index
        raw = int.from_bytes(packet[offset:offset + 2], "big")
        if raw == 0xFFFF:
            values.append(None)
        elif raw <= 6000:
            values.append(raw / 10)
        else:
            raise ValueError("Temperature outside supported protocol range")
    return tuple(values)
