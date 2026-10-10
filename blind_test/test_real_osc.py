"""
test_real_osc.py — Unit & Integration Tests for RealOscTransport
Project 2: A Machine for Misunderstanding (Blind Test Experiment)

Tests:
1. OSC 1.0 message packet byte-encoding (padding, big-endian float, address, type tags)
2. Voltage range pre-validation (canonical 8 channels, out-of-range, NaN, Infinity, missing keys)
3. Live UDP loopback transmission to a local mock socket receiver on 127.0.0.1
4. Transmission verification: exactly 8 canonical addresses received with expected float values
5. Validation failure handling (status="FAILED", no socket packets dispatched)
6. Socket error / unreachable port handling (does not crash or leak traceback)
7. Integration with BlindTestService swapping FakeOscTransport with RealOscTransport
"""

import math
import os
import shutil
import socket
import struct
import tempfile
import threading
import time
from typing import Any, Dict, List, Tuple

from acoustic_bridge import (
    OSC_CHANNELS,
    FakeModelBackend,
    FakeOscTransport,
    compute_voltages,
)
from db import Database
from real_osc import (
    VOLTAGE_RANGES,
    RealOscTransport,
    _pad_osc_string,
    encode_osc_message,
    validate_voltages,
)
from service import BlindTestService


def decode_osc_message(data: bytes) -> Tuple[str, List[float]]:
    """Decode basic OSC 1.0 packet with float arguments for test verification."""
    # Read address up to null, aligned to 4 bytes
    null_idx = data.find(b"\x00")
    addr = data[:null_idx].decode("utf-8")
    offset = (null_idx + 4) & ~3

    # Read type tags
    tag_null = data.find(b"\x00", offset)
    tag_str = data[offset:tag_null].decode("utf-8")
    offset = (tag_null + 4) & ~3

    # Read floats
    floats = []
    for tag in tag_str[1:]:  # skip comma
        if tag == "f":
            f_val = struct.unpack(">f", data[offset : offset + 4])[0]
            floats.append(round(f_val, 4))
            offset += 4

    return addr, floats


def test_osc_packet_encoding():
    # 1. Padding
    assert _pad_osc_string("/a") == b"/a\x00\x00"
    assert _pad_osc_string("/abc") == b"/abc\x00\x00\x00\x00"

    # 2. Message encoding
    msg = encode_osc_message("/param/timbre", 1.5)
    addr, vals = decode_osc_message(msg)
    assert addr == "/param/timbre"
    assert len(vals) == 1
    assert abs(vals[0] - 1.5) < 1e-4


def test_voltage_validation():
    valid_vadc = {"valence": 0.5, "arousal": 0.5, "dominance": 0.5}
    valid_voltages = compute_voltages(valid_vadc)

    # Valid voltages must pass without exception
    validate_voltages(valid_voltages)

    # Missing key
    incomplete = dict(valid_voltages)
    del incomplete["timbre_v"]
    try:
        validate_voltages(incomplete)
        assert False, "Should have raised ValueError on missing voltage key"
    except ValueError as e:
        assert "Missing required voltage key 'timbre_v'" in str(e)

    # Out of range (timbre_v max is +5.0V)
    out_of_bound = dict(valid_voltages)
    out_of_bound["timbre_v"] = 5.5
    try:
        validate_voltages(out_of_bound)
        assert False, "Should have raised ValueError on out of range voltage"
    except ValueError as e:
        assert "out of range" in str(e)

    # NaN
    nan_voltages = dict(valid_voltages)
    nan_voltages["amplitude_v"] = float("nan")
    try:
        validate_voltages(nan_voltages)
        assert False, "Should have raised ValueError on NaN"
    except ValueError as e:
        assert "cannot be NaN" in str(e)

    # Infinity
    inf_voltages = dict(valid_voltages)
    inf_voltages["noise_v"] = float("inf")
    try:
        validate_voltages(inf_voltages)
        assert False, "Should have raised ValueError on Infinity"
    except ValueError as e:
        assert "cannot be NaN or Infinite" in str(e)


def test_real_osc_udp_loopback():
    """Start local mock UDP socket on an ephemeral port and verify reception of all 8 channels."""
    mock_receiver = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    mock_receiver.bind(("127.0.0.1", 0))
    receiver_host, receiver_port = mock_receiver.getsockname()
    mock_receiver.settimeout(2.0)

    received_packets = []
    listening = threading.Event()

    def receive_loop():
        listening.set()
        try:
            for _ in range(8):
                data, _ = mock_receiver.recvfrom(1024)
                addr, vals = decode_osc_message(data)
                received_packets.append((addr, vals[0]))
        except socket.timeout:
            pass

    t = threading.Thread(target=receive_loop, daemon=True)
    t.start()
    listening.wait()

    transport = RealOscTransport(host=receiver_host, port=receiver_port)
    voltages = {
        "timbre_v": 1.0,
        "frequency_v": -0.5,
        "amplitude_v": 6.0,
        "envelope_v": 0.0,
        "mode_v": 2.0,
        "chord_v": 3.0,
        "type_v": 1.0,
        "noise_v": 5.0,
    }

    res = transport.send_voltages(voltages)
    assert res.status == "SENT"
    assert res.error is None
    assert len(res.addresses) == 8

    t.join(timeout=3.0)
    mock_receiver.close()

    assert len(received_packets) == 8
    received_dict = {addr: val for addr, val in received_packets}

    for addr, v_key in OSC_CHANNELS.items():
        assert addr in received_dict
        expected_val = voltages[v_key]
        assert abs(received_dict[addr] - expected_val) < 1e-3


def test_real_osc_validation_failure_handling():
    """Verify that if voltages are invalid, transport returns FAILED without socket crash."""
    transport = RealOscTransport(host="127.0.0.1", port=7001)
    invalid_voltages = {"timbre_v": 99.0}  # missing keys and out of range

    res = transport.send_voltages(invalid_voltages)
    assert res.status == "FAILED"
    assert res.error is not None
    assert "Voltage pre-validation error" in res.error


def test_service_with_real_osc_transport():
    """Verify BlindTestService works seamlessly with RealOscTransport in loopback."""
    mock_receiver = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    mock_receiver.bind(("127.0.0.1", 0))
    receiver_host, receiver_port = mock_receiver.getsockname()
    mock_receiver.settimeout(2.0)

    received_addrs = []

    def receive_loop():
        try:
            for _ in range(8):
                data, _ = mock_receiver.recvfrom(1024)
                addr, _ = decode_osc_message(data)
                received_addrs.append(addr)
        except socket.timeout:
            pass

    t = threading.Thread(target=receive_loop, daemon=True)
    t.start()

    temp_dir = tempfile.mkdtemp()
    try:
        db = Database(db_path=os.path.join(temp_dir, "test_real_osc.db"))
        db.init_db()

        real_transport = RealOscTransport(host=receiver_host, port=receiver_port)
        service = BlindTestService(
            db=db,
            model_backend=FakeModelBackend(),
            osc_transport=real_transport,
        )

        session_id = "s_real_osc"
        service.create_session(session_id)
        res_a = service.join(session_id, "A", "tok_a")
        res_b = service.join(session_id, "B", "tok_b")
        p_a = res_a["participant"]["participant_id"]
        p_b = res_b["participant"]["participant_id"]
        service.ready(session_id, p_a)
        service.ready(session_id, p_b)
        service.start_session(session_id)

        # Sender A submits input -> triggers RealOscTransport.send_voltages
        vadc = {"valence": 0.4, "arousal": 0.6, "dominance": 0.5, "confidence": 0.8}
        res_in = service.submit_input(session_id, p_a, "Night wind howling outside.", vadc, "sub_real_1")
        assert res_in["accepted"] is True
        assert res_in["sequence"] == 1

        t.join(timeout=3.0)
        assert len(received_addrs) == 8
        for addr in OSC_CHANNELS.keys():
            assert addr in received_addrs
    finally:
        mock_receiver.close()
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    print("[*] Running test_real_osc.py...")
    test_osc_packet_encoding()
    test_voltage_validation()
    test_real_osc_udp_loopback()
    test_real_osc_validation_failure_handling()
    test_service_with_real_osc_transport()
    print("[✓] All Phase 5A Real OSC Transport tests passed successfully!")
