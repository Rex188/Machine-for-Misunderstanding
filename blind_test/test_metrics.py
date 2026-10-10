"""
test_metrics.py — Unit Tests for Pure Mathematical Metrics Engine
Verifies:
- Raw distance calculation (model, medium, total)
- Confidence modulation factor and adjusted distances
- Zero vector and extreme boundary cases
- Inter-round drift tracking
- Robust rejection of NaN, Infinity, out-of-range, and missing fields
"""

import math
from metrics import (
    validate_vadc,
    normalized_euclidean_distance,
    confidence_modulation_factor,
    calculate_round_metrics,
)


def test_distance_bounds_and_zero_vectors():
    # Identity points -> 0.0
    p_zero = (0.0, 0.0, 0.0)
    assert normalized_euclidean_distance(p_zero, p_zero) == 0.0

    # Max distance: (0, 0, 0) to (1, 1, 1) -> 1.0
    p_max = (1.0, 1.0, 1.0)
    assert normalized_euclidean_distance(p_zero, p_max) == 1.0

    # Intermediate points: (0, 0, 0) to (1, 0, 0) -> 1 / sqrt(3) ~ 0.577350
    p_unit_x = (1.0, 0.0, 0.0)
    expected = round(1.0 / math.sqrt(3.0), 6)
    assert abs(normalized_euclidean_distance(p_zero, p_unit_x) - expected) < 1e-5


def test_confidence_modulation_factor():
    # When confidences are 1.0, kappa is 1.0
    assert confidence_modulation_factor(1.0, 1.0, alpha=0.3) == 1.0

    # When confidences are 0.0, kappa is 1 - alpha = 0.7
    assert confidence_modulation_factor(0.0, 0.0, alpha=0.3) == 0.7

    # When confidences are 0.5 and 0.5 -> kappa = 0.7 + 0.3 * 0.5 = 0.85
    assert abs(confidence_modulation_factor(0.5, 0.5, alpha=0.3) - 0.85) < 1e-5

    # Strict mode rejects out of range
    try:
        confidence_modulation_factor(-0.1, 0.5, strict=True)
        assert False, "Should have raised ValueError on negative confidence"
    except ValueError as e:
        assert "must be in range [0.0, 1.0]" in str(e)

    try:
        confidence_modulation_factor(0.5, 1.5, strict=True)
        assert False, "Should have raised ValueError on confidence > 1.0"
    except ValueError as e:
        assert "must be in range [0.0, 1.0]" in str(e)


def test_calculate_round_metrics_success():
    in_vadc = {"valence": 0.2, "arousal": 0.8, "dominance": 0.1, "confidence": 0.9}
    model_vadc = {"valence": 0.2, "arousal": 0.8, "dominance": 0.1, "confidence": 0.8}
    rec_vadc = {"valence": 0.5, "arousal": 0.5, "dominance": 0.5, "confidence": 0.6}

    # Round 0: no previous round -> inter_round_drift is None
    res = calculate_round_metrics(in_vadc, model_vadc, rec_vadc, previous_receiver_vadc=None)
    assert res["formula_version"] == "metrics-v1-euclidean-drift"
    assert res["raw_distance"]["model"] == 0.0  # in and model identical
    assert res["confidence_adjusted_distance"]["model"] == 0.0
    assert res["raw_distance"]["medium"] > 0.0
    assert res["raw_distance"]["total"] > 0.0
    assert res["inter_round_drift"] is None

    # Round 1: with previous receiver vadc
    prev_rec = {"valence": 0.1, "arousal": 0.9, "dominance": 0.1, "confidence": 0.7}
    res_r1 = calculate_round_metrics(in_vadc, model_vadc, rec_vadc, previous_receiver_vadc=prev_rec)
    assert res_r1["formula_version"] == "metrics-v1-euclidean-drift"
    assert res_r1["inter_round_drift"] is not None
    assert 0.0 <= res_r1["inter_round_drift"] <= 1.0


def test_validation_errors():
    # Missing field
    try:
        validate_vadc({"valence": 0.5, "arousal": 0.5, "dominance": 0.5})
        assert False, "Should have raised ValueError for missing confidence"
    except ValueError as e:
        assert "missing required field 'confidence'" in str(e)

    # Out of range (< 0)
    try:
        validate_vadc({"valence": -0.1, "arousal": 0.5, "dominance": 0.5, "confidence": 0.5})
        assert False, "Should have raised ValueError for negative value"
    except ValueError as e:
        assert "must be in range [0.0, 1.0]" in str(e)

    # Out of range (> 1)
    try:
        validate_vadc({"valence": 1.2, "arousal": 0.5, "dominance": 0.5, "confidence": 0.5})
        assert False, "Should have raised ValueError for value > 1.0"
    except ValueError as e:
        assert "must be in range [0.0, 1.0]" in str(e)

    # NaN
    try:
        validate_vadc({"valence": float("nan"), "arousal": 0.5, "dominance": 0.5, "confidence": 0.5})
        assert False, "Should have raised ValueError for NaN"
    except ValueError as e:
        assert "cannot be NaN" in str(e)

    # Infinity
    try:
        validate_vadc({"valence": float("inf"), "arousal": 0.5, "dominance": 0.5, "confidence": 0.5})
        assert False, "Should have raised ValueError for Infinity"
    except ValueError as e:
        assert "cannot be Infinite" in str(e)

    # Non-dictionary
    try:
        validate_vadc([0.5, 0.5, 0.5, 0.5])
        assert False, "Should have raised ValueError for non-dict"
    except ValueError as e:
        assert "must be a dictionary" in str(e)


if __name__ == "__main__":
    print("[*] Running test_metrics.py...")
    test_distance_bounds_and_zero_vectors()
    test_confidence_modulation_factor()
    test_calculate_round_metrics_success()
    test_validation_errors()
    print("[✓] All metrics tests passed successfully!")
