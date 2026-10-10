"""
acoustic_bridge.py — Acoustic Synthesis & Model Interface Bridge
Project 2: A Machine for Misunderstanding (Blind Test Experiment)

Architecture:
- Defines abstract interfaces: ModelBackend and OscTransport.
- Canonical 8-channel physical voltage mapping matching BLIND_TEST_PLAN.md:
    /param/timbre    -> timbre_v
    /param/frequency -> frequency_v
    /param/amplitude -> amplitude_v
    /param/envelope  -> envelope_v
    /param/mode      -> mode_v
    /param/chord     -> chord_v
    /param/type      -> type_v
    /param/noise     -> noise_v
- Zero real UDP / zero real API calls in Phase 3.
- Provides test-ready FakeModelBackend and FakeOscTransport.
"""

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from datetime import datetime
import json
import math
import time
from typing import Any, Dict, List, Optional

# Canonical 8 OSC channels frozen in architecture
OSC_CHANNELS = {
    "/param/timbre": "timbre_v",
    "/param/frequency": "frequency_v",
    "/param/amplitude": "amplitude_v",
    "/param/envelope": "envelope_v",
    "/param/mode": "mode_v",
    "/param/chord": "chord_v",
    "/param/type": "type_v",
    "/param/noise": "noise_v",
}


@dataclass
class ModelResult:
    output: Optional[Dict[str, Any]]
    raw_output: str
    status: str  # "SUCCESS", "TIMEOUT", "INVALID_JSON", "FALLBACK", "BACKEND_ERROR"
    fallback_used: bool
    fallback_reason: Optional[str]
    latency_ms: int
    backend: str
    model_name: str
    prompt_version: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class OscDispatchResult:
    host: str
    port: int
    addresses: List[str]
    status: str  # "SENT" or "FAILED"
    sent_at: str
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def compute_voltages(vadc: Dict[str, float], strict: bool = True) -> Dict[str, float]:
    """
    Deterministic psychological acoustic voltage calculation.
    Maps VADC in [0, 1] into 8 CV control voltages for VCV Rack.

    If strict=True (default), validates that valence, arousal, and dominance
    are present, numeric, finite, and strictly within [0.0, 1.0].
    If strict=False, missing or out-of-range values are defaulted/clamped to [0.0, 1.0].
    """
    if strict:
        if not isinstance(vadc, dict):
            raise ValueError(f"VADC must be a dict, got {type(vadc).__name__}")
        for key in ("valence", "arousal", "dominance"):
            if key not in vadc:
                raise ValueError(f"Missing required VAD dimension '{key}' for voltage calculation")
            val = vadc[key]
            if not isinstance(val, (int, float)):
                raise ValueError(f"VAD dimension '{key}' must be numeric, got {type(val).__name__}")
            if math.isnan(val) or math.isinf(val):
                raise ValueError(f"VAD dimension '{key}' cannot be NaN or Infinite")
            if val < 0.0 or val > 1.0:
                raise ValueError(f"VAD dimension '{key}' must be in range [0.0, 1.0], got {val}")
        v = float(vadc["valence"])
        a = float(vadc["arousal"])
        d = float(vadc["dominance"])
    else:
        v = max(0.0, min(1.0, float(vadc.get("valence", 0.5))))
        a = max(0.0, min(1.0, float(vadc.get("arousal", 0.5))))
        d = max(0.0, min(1.0, float(vadc.get("dominance", 0.5))))

    # 1. Timbre: Cutoff / Harmonic brightness driven by Valence
    # Valence 0 (dark/subterranean) -> -3.0V, Valence 1 (luminous) -> +5.0V
    timbre_v = round(-3.0 + 8.0 * v, 3)

    # 2. Frequency: Base pitch shift driven by Arousal energy
    # Low arousal (hypothermic) -> -2.0V, High arousal (spasmic) -> +2.0V
    frequency_v = round(-2.0 + 4.0 * a, 3)

    # 3. Amplitude: VCA Level driven by Arousal
    amplitude_v = round(2.0 + 8.0 * a, 3)

    # 4. Envelope: Decay time inversely proportional to Arousal
    envelope_v = round(-4.0 + 8.0 * (1.0 - a), 3)

    # 5. Mode: Scale selection driven by Valence (minor/dark -> major/bright)
    mode_v = round(-4.0 + 8.0 * v, 2)

    # 6. Chord: Harmonic step (0-6) driven by Dominance agency
    chord_v = float(round(d * 6.0))

    # 7. Type: Chord complexity (0=Triad, 1=7th, 2=9th)
    type_v = float(round(d * 2.0))

    # 8. Noise: Atmospheric chaos inversely proportional to Dominance (loss of control)
    noise_v = round(10.0 * (1.0 - d), 3)

    return {
        "timbre_v": timbre_v,
        "frequency_v": frequency_v,
        "amplitude_v": amplitude_v,
        "envelope_v": envelope_v,
        "mode_v": mode_v,
        "chord_v": chord_v,
        "type_v": type_v,
        "noise_v": noise_v,
    }


# ── Abstract Interfaces ──────────────────────────────────────────────────────

class ModelBackend(ABC):
    @abstractmethod
    def infer(self, text: str, context: Optional[Dict[str, Any]] = None) -> ModelResult:
        pass


class OscTransport(ABC):
    @abstractmethod
    def send_voltages(self, voltages: Dict[str, float]) -> OscDispatchResult:
        pass


# ── Fake Implementations for Phase 3 Verification ───────────────────────────

class FakeModelBackend(ModelBackend):
    """
    Configurable in-memory Fake Model Backend.
    Zero external network calls.
    """

    def __init__(
        self,
        backend_name: str = "fake_qwen",
        model_name: str = "FakeQwen-1.5B",
        prompt_version: str = "fake-v1",
        should_fail: bool = False,
        failure_status: str = "BACKEND_ERROR",
        failure_reason: str = "Simulated model backend failure",
        fixed_output: Optional[Dict[str, Any]] = None,
        latency_ms: int = 15,
    ):
        self.backend_name = backend_name
        self.model_name = model_name
        self.prompt_version = prompt_version
        self.should_fail = should_fail
        self.failure_status = failure_status
        self.failure_reason = failure_reason
        self.fixed_output = fixed_output
        self.latency_ms = latency_ms

    def infer(self, text: str, context: Optional[Dict[str, Any]] = None) -> ModelResult:
        if self.should_fail:
            return ModelResult(
                output=None,
                raw_output="",
                status=self.failure_status,
                fallback_used=False,
                fallback_reason=self.failure_reason,
                latency_ms=self.latency_ms,
                backend=self.backend_name,
                model_name=self.model_name,
                prompt_version=self.prompt_version,
            )

        if self.fixed_output:
            vadc = self.fixed_output
        else:
            # Deterministic pseudo-inference based on text length and character hash
            text_hash = sum(ord(c) for c in text) % 1000
            v = round(0.2 + 0.6 * ((text_hash % 100) / 100.0), 3)
            a = round(0.1 + 0.8 * (((text_hash // 10) % 100) / 100.0), 3)
            d = round(0.2 + 0.7 * (((text_hash // 100) % 10) / 10.0), 3)
            vadc = {
                "valence": v,
                "arousal": a,
                "dominance": d,
                "confidence": 0.85,
                "reasoning": f"Simulated phenomenological somatic parse of: {text[:30]}...",
            }

        return ModelResult(
            output=vadc,
            raw_output=json.dumps(vadc),
            status="SUCCESS",
            fallback_used=False,
            fallback_reason=None,
            latency_ms=self.latency_ms,
            backend=self.backend_name,
            model_name=self.model_name,
            prompt_version=self.prompt_version,
        )


class FakeOscTransport(OscTransport):
    """
    Configurable in-memory Fake OSC Transport.
    Zero UDP socket operations.
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 7001,
        should_fail: bool = False,
        failure_error: str = "Simulated OSC transport error",
    ):
        self.host = host
        self.port = port
        self.should_fail = should_fail
        self.failure_error = failure_error
        self.sent_history: List[Dict[str, Any]] = []

    def send_voltages(self, voltages: Dict[str, float]) -> OscDispatchResult:
        now_iso = datetime.now().astimezone().isoformat()
        addresses = list(OSC_CHANNELS.keys())

        if self.should_fail:
            return OscDispatchResult(
                host=self.host,
                port=self.port,
                addresses=addresses,
                status="FAILED",
                sent_at=now_iso,
                error=self.failure_error,
            )

        dispatch = {
            "host": self.host,
            "port": self.port,
            "voltages": voltages,
            "addresses": addresses,
            "sent_at": now_iso,
        }
        self.sent_history.append(dispatch)

        return OscDispatchResult(
            host=self.host,
            port=self.port,
            addresses=addresses,
            status="SENT",
            sent_at=now_iso,
            error=None,
        )
