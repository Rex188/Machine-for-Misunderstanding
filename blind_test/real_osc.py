"""
real_osc.py — Production Real UDP/OSC Transport Implementation
Project 2: A Machine for Misunderstanding (Blind Test Experiment)

Architecture:
- Implements RealOscTransport behind abstract OscTransport interface (acoustic_bridge.py).
- Sends exactly the frozen 8 canonical OSC channels defined in BLIND_TEST_PLAN.md:
    /param/timbre    -> timbre_v    [-3.0V, +5.0V]
    /param/frequency -> frequency_v [-2.0V, +2.0V]
    /param/amplitude -> amplitude_v [+2.0V, +10.0V]
    /param/envelope  -> envelope_v  [-4.0V, +4.0V]
    /param/mode      -> mode_v      [-4.0V, +4.0V]
    /param/chord     -> chord_v     [0.0V,  +6.0V]
    /param/type      -> type_v      [0.0V,  +2.0V]
    /param/noise     -> noise_v     [0.0V,  +10.0V]
- Target: 127.0.0.1:7001 (configurable via environment or constructor parameters).
- Zero external pip dependencies: standard library socket & struct encoding (OSC 1.0 format).
- Strict voltage pre-validation: rejects missing keys, non-numeric, NaN, Infinity,
  and out-of-range voltages before transmission.
- Robust network error handling: timeout, socket errors, and dispatch status reporting.
"""

from datetime import datetime
import math
import os
import socket
import struct
import time
from typing import Any, Dict, List, Optional, Tuple

from acoustic_bridge import OSC_CHANNELS, OscDispatchResult, OscTransport

DEFAULT_OSC_HOST = os.environ.get("OSC_HOST", "127.0.0.1")
DEFAULT_OSC_PORT = int(os.environ.get("OSC_PORT", "7001"))
DEFAULT_OSC_TIMEOUT = float(os.environ.get("OSC_TIMEOUT", "1.0"))

# Frozen voltage ranges derived from compute_voltages() in acoustic_bridge.py
VOLTAGE_RANGES: Dict[str, Tuple[float, float]] = {
    "timbre_v": (-3.0, 5.0),
    "frequency_v": (-2.0, 2.0),
    "amplitude_v": (2.0, 10.0),
    "envelope_v": (-4.0, 4.0),
    "mode_v": (-4.0, 4.0),
    "chord_v": (0.0, 6.0),
    "type_v": (0.0, 2.0),
    "noise_v": (0.0, 10.0),
}


def _pad_osc_string(s: str) -> bytes:
    """Pad null-terminated string to 4-byte boundary according to OSC 1.0 standard."""
    b = s.encode("utf-8") + b"\x00"
    remainder = len(b) % 4
    if remainder != 0:
        b += b"\x00" * (4 - remainder)
    return b


def encode_osc_message(address: str, *args: float) -> bytes:
    """
    Encode an OSC 1.0 message packet with float arguments.
    Format: [Address String, null-padded] [Type Tag String ",fff...", null-padded] [Big-endian 32-bit floats]
    """
    address_bytes = _pad_osc_string(address)
    tag_str = "," + "f" * len(args)
    tag_bytes = _pad_osc_string(tag_str)
    args_bytes = b"".join(struct.pack(">f", float(val)) for val in args)
    return address_bytes + tag_bytes + args_bytes


def validate_voltages(voltages: Dict[str, float], tolerance: float = 1e-3) -> None:
    """
    Validate that voltages dictionary contains all 8 canonical voltage keys,
    with finite numeric values strictly inside allowable hardware CV ranges.
    Raises ValueError on validation failure.
    """
    if not isinstance(voltages, dict):
        raise ValueError(f"Voltages must be a dictionary, got {type(voltages).__name__}")

    for addr, v_key in OSC_CHANNELS.items():
        if v_key not in voltages:
            raise ValueError(f"Missing required voltage key '{v_key}' for channel '{addr}'")

        val = voltages[v_key]
        if not isinstance(val, (int, float)):
            raise ValueError(f"Voltage '{v_key}' must be a number, got {type(val).__name__}")

        if math.isnan(val) or math.isinf(val):
            raise ValueError(f"Voltage '{v_key}' cannot be NaN or Infinite (got {val})")

        min_v, max_v = VOLTAGE_RANGES[v_key]
        if val < (min_v - tolerance) or val > (max_v + tolerance):
            raise ValueError(
                f"Voltage '{v_key}' out of range [{min_v}, {max_v}]: got {val}"
            )


class RealOscTransport(OscTransport):
    """
    Production Real UDP/OSC Transport sending datagrams to VCV Rack / cvOSCcv.
    """

    def __init__(
        self,
        host: str = DEFAULT_OSC_HOST,
        port: int = DEFAULT_OSC_PORT,
        timeout: float = DEFAULT_OSC_TIMEOUT,
    ):
        self.host = host
        self.port = port
        self.timeout = timeout

    def send_voltages(self, voltages: Dict[str, float]) -> OscDispatchResult:
        """
        Validate and dispatch 8 individual OSC packets to self.host:self.port via UDP.
        Returns OscDispatchResult with status 'SENT' or 'FAILED'.
        """
        now_iso = datetime.now().astimezone().isoformat()
        addresses = list(OSC_CHANNELS.keys())

        # 1. Pre-validation of voltage domains
        try:
            validate_voltages(voltages)
        except ValueError as e:
            return OscDispatchResult(
                host=self.host,
                port=self.port,
                addresses=addresses,
                status="FAILED",
                sent_at=now_iso,
                error=f"Voltage pre-validation error: {e}",
            )

        # 2. UDP Transmission
        sock = None
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(self.timeout)

            # Send each canonical channel
            for addr, v_key in OSC_CHANNELS.items():
                val = float(voltages[v_key])
                packet = encode_osc_message(addr, val)
                sock.sendto(packet, (self.host, self.port))

            return OscDispatchResult(
                host=self.host,
                port=self.port,
                addresses=addresses,
                status="SENT",
                sent_at=now_iso,
                error=None,
            )

        except socket.timeout:
            return OscDispatchResult(
                host=self.host,
                port=self.port,
                addresses=addresses,
                status="FAILED",
                sent_at=now_iso,
                error=f"Socket timeout sending OSC to {self.host}:{self.port}",
            )
        except socket.error as e:
            return OscDispatchResult(
                host=self.host,
                port=self.port,
                addresses=addresses,
                status="FAILED",
                sent_at=now_iso,
                error=f"Socket error sending OSC to {self.host}:{self.port}: {e}",
            )
        except Exception as e:
            return OscDispatchResult(
                host=self.host,
                port=self.port,
                addresses=addresses,
                status="FAILED",
                sent_at=now_iso,
                error=f"Unexpected error in OSC transport: {e}",
            )
        finally:
            if sock is not None:
                try:
                    sock.close()
                except Exception:
                    pass
