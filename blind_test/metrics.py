"""
metrics.py — Pure Mathematical Metrics & Affective Geometry Engine
Project 2: A Machine for Misunderstanding (Blind Test Experiment)

Design Principles:
- PURE functional computation: No database, no network, no side-effects.
- Normalized 3D Euclidean affective space: V, A, D in [0, 1].
- Soft Confidence Modulation Factor: kappa(C1, C2) = (1 - alpha) + alpha * sqrt(C1 * C2)
- Strict validation: Handles zero vectors, missing fields, out-of-range values, NaN, and Infinity safely.
"""

import math
from typing import Any, Dict, Optional, Tuple

SQRT_3 = math.sqrt(3.0)  # ~1.7320508075688772
DEFAULT_CONFIDENCE_ALPHA = 0.3


def validate_vadc(vadc: Dict[str, Any], name: str = "vadc") -> Tuple[Tuple[float, float, float], float]:
    """
    Validate that vadc contains valence, arousal, dominance, and confidence
    as finite numbers within [0.0, 1.0].
    Returns ((v, a, d), c).
    """
    if not isinstance(vadc, dict):
        raise ValueError(f"'{name}' must be a dictionary, got {type(vadc).__name__}")

    for key in ("valence", "arousal", "dominance", "confidence"):
        if key not in vadc:
            raise ValueError(f"'{name}' is missing required field '{key}'")
        val = vadc[key]
        if not isinstance(val, (int, float)):
            raise ValueError(f"Field '{key}' in '{name}' must be a number, got {type(val).__name__}")
        if math.isnan(val):
            raise ValueError(f"Field '{key}' in '{name}' cannot be NaN")
        if math.isinf(val):
            raise ValueError(f"Field '{key}' in '{name}' cannot be Infinite")
        if val < 0.0 or val > 1.0:
            raise ValueError(f"Field '{key}' in '{name}' must be in range [0.0, 1.0], got {val}")

    coords = (float(vadc["valence"]), float(vadc["arousal"]), float(vadc["dominance"]))
    confidence = float(vadc["confidence"])
    return coords, confidence


FORMULA_VERSION = "metrics-v1-euclidean-drift"


def normalized_euclidean_distance(p1: Tuple[float, float, float], p2: Tuple[float, float, float]) -> float:
    """
    Compute Euclidean distance between two 3D points normalized by sqrt(3).
    Result is strictly in [0.0, 1.0].
    Handles zero vectors [0, 0, 0] without singularities.
    """
    dx = p1[0] - p2[0]
    dy = p1[1] - p2[1]
    dz = p1[2] - p2[2]
    dist = math.sqrt(dx * dx + dy * dy + dz * dz)
    normalized = dist / SQRT_3
    # Clamp for float precision
    return max(0.0, min(1.0, round(normalized, 6)))


def confidence_modulation_factor(
    c1: float,
    c2: float,
    alpha: float = DEFAULT_CONFIDENCE_ALPHA,
    strict: bool = True,
) -> float:
    """
    Compute soft confidence modulation factor kappa(c1, c2):
    kappa = (1 - alpha) + alpha * sqrt(c1 * c2)
    For alpha=0.3 and c in [0, 1], kappa is in [0.7, 1.0].

    If strict=True, rejects any value not in [0.0, 1.0].
    If strict=False, clamps to [0.0, 1.0].
    """
    for name, c in (("c1", c1), ("c2", c2)):
        if not isinstance(c, (int, float)):
            raise ValueError(f"Confidence '{name}' must be a number, got {type(c).__name__}")
        if math.isnan(c):
            raise ValueError(f"Confidence '{name}' cannot be NaN")
        if math.isinf(c):
            raise ValueError(f"Confidence '{name}' cannot be Infinite")
        if strict and (c < 0.0 or c > 1.0):
            raise ValueError(f"Confidence '{name}' must be in range [0.0, 1.0], got {c}")

    c1_clamped = max(0.0, min(1.0, float(c1)))
    c2_clamped = max(0.0, min(1.0, float(c2)))
    kappa = (1.0 - alpha) + alpha * math.sqrt(c1_clamped * c2_clamped)
    return round(kappa, 6)


def calculate_round_metrics(
    input_vadc: Dict[str, Any],
    model_vadc: Dict[str, Any],
    receiver_vadc: Dict[str, Any],
    previous_receiver_vadc: Optional[Dict[str, Any]] = None,
    alpha: float = DEFAULT_CONFIDENCE_ALPHA,
) -> Dict[str, Any]:
    """
    Compute complete canonical metrics dictionary for a completed round:
    - raw_distance: {model, medium, total}
    - confidence_adjusted_distance: {model, medium, total}
    - confidence: {input, model, receiver}
    - inter_round_drift: float or None
    - formula_version: "metrics-v1-euclidean-drift"
    """
    input_coords, c_in = validate_vadc(input_vadc, "input_vadc")
    model_coords, c_model = validate_vadc(model_vadc, "model_vadc")
    receiver_coords, c_rec = validate_vadc(receiver_vadc, "receiver_vadc")

    # 1. Raw Distances (Pure Normalized Euclidean in [0, 1])
    raw_model = normalized_euclidean_distance(input_coords, model_coords)
    raw_medium = normalized_euclidean_distance(model_coords, receiver_coords)
    raw_total = normalized_euclidean_distance(input_coords, receiver_coords)

    # 2. Confidence Modulation Factors (Strict Mode)
    kappa_model = confidence_modulation_factor(c_in, c_model, alpha, strict=True)
    kappa_medium = confidence_modulation_factor(c_model, c_rec, alpha, strict=True)
    kappa_total = confidence_modulation_factor(c_in, c_rec, alpha, strict=True)

    # 3. Confidence-Adjusted Distances
    adj_model = round(raw_model * kappa_model, 6)
    adj_medium = round(raw_medium * kappa_medium, 6)
    adj_total = round(raw_total * kappa_total, 6)

    # 4. Inter-Round Drift
    inter_round_drift = None
    if previous_receiver_vadc is not None:
        prev_coords, _ = validate_vadc(previous_receiver_vadc, "previous_receiver_vadc")
        # Shift between previous round's felt receiver state and current sender input intent
        inter_round_drift = normalized_euclidean_distance(prev_coords, input_coords)

    return {
        "formula_version": FORMULA_VERSION,
        "raw_distance": {
            "model": raw_model,
            "medium": raw_medium,
            "total": raw_total,
        },
        "confidence_adjusted_distance": {
            "model": adj_model,
            "medium": adj_medium,
            "total": adj_total,
        },
        "confidence": {
            "input": c_in,
            "model": c_model,
            "receiver": c_rec,
        },
        "inter_round_drift": inter_round_drift,
    }
