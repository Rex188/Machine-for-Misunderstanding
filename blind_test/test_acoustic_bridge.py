"""
test_acoustic_bridge.py — Unit Tests for Acoustic Bridge & Fake Interfaces
Verifies:
- Deterministic 8-channel voltage mapping and boundary clamping
- FakeModelBackend success and configurable failure modes
- FakeOscTransport message logging and failure handling
"""

from acoustic_bridge import (
    OSC_CHANNELS,
    compute_voltages,
    FakeModelBackend,
    FakeOscTransport,
)


def test_voltage_computation_and_channels():
    vadc = {"valence": 0.5, "arousal": 0.5, "dominance": 0.5, "confidence": 0.8}
    voltages = compute_voltages(vadc)

    # Must contain exact 8 canonical channels
    assert len(voltages) == 8
    for addr, key in OSC_CHANNELS.items():
        assert key in voltages, f"Missing voltage key '{key}' for '{addr}'"

    # Extreme bounds: (0, 0, 0)
    v_zero = compute_voltages({"valence": 0.0, "arousal": 0.0, "dominance": 0.0})
    assert v_zero["timbre_v"] == -3.0
    assert v_zero["frequency_v"] == -2.0
    assert v_zero["amplitude_v"] == 2.0
    assert v_zero["envelope_v"] == 4.0
    assert v_zero["mode_v"] == -4.0
    assert v_zero["chord_v"] == 0.0
    assert v_zero["type_v"] == 0.0
    assert v_zero["noise_v"] == 10.0

    # Extreme bounds: (1, 1, 1)
    v_max = compute_voltages({"valence": 1.0, "arousal": 1.0, "dominance": 1.0})
    assert v_max["timbre_v"] == 5.0
    assert v_max["frequency_v"] == 2.0
    assert v_max["amplitude_v"] == 10.0
    assert v_max["envelope_v"] == -4.0
    assert v_max["mode_v"] == 4.0
    assert v_max["chord_v"] == 6.0
    assert v_max["type_v"] == 2.0
    assert v_max["noise_v"] == 0.0

    # Strict mode checks
    try:
        compute_voltages({"valence": -0.1, "arousal": 0.5, "dominance": 0.5}, strict=True)
        assert False, "Should have failed on negative valence"
    except ValueError as e:
        assert "must be in range [0.0, 1.0]" in str(e)

    try:
        compute_voltages({"valence": 0.5, "arousal": 1.2, "dominance": 0.5}, strict=True)
        assert False, "Should have failed on arousal > 1.0"
    except ValueError as e:
        assert "must be in range [0.0, 1.0]" in str(e)

    try:
        compute_voltages({"valence": 0.5, "arousal": 0.5}, strict=True)
        assert False, "Should have failed on missing dominance"
    except ValueError as e:
        assert "Missing required VAD dimension 'dominance'" in str(e)


def test_fake_model_backend():
    backend = FakeModelBackend()
    res = backend.infer("Deep winter night, cold gusts shaking the window frame.")
    assert res.status == "SUCCESS"
    assert res.output is not None
    assert 0.0 <= res.output["valence"] <= 1.0
    assert res.fallback_used is False

    # Failure mode
    fail_backend = FakeModelBackend(should_fail=True, failure_status="TIMEOUT")
    res_fail = fail_backend.infer("Text that should time out.")
    assert res_fail.status == "TIMEOUT"
    assert res_fail.output is None


def test_fake_osc_transport():
    transport = FakeOscTransport()
    voltages = compute_voltages({"valence": 0.4, "arousal": 0.7, "dominance": 0.3})
    res = transport.send_voltages(voltages)

    assert res.status == "SENT"
    assert res.error is None
    assert len(transport.sent_history) == 1
    assert transport.sent_history[0]["voltages"] == voltages

    # Failure mode
    fail_transport = FakeOscTransport(should_fail=True)
    res_fail = fail_transport.send_voltages(voltages)
    assert res_fail.status == "FAILED"
    assert res_fail.error is not None


if __name__ == "__main__":
    print("[*] Running test_acoustic_bridge.py...")
    test_voltage_computation_and_channels()
    test_fake_model_backend()
    test_fake_osc_transport()
    print("[✓] All acoustic bridge tests passed successfully!")
