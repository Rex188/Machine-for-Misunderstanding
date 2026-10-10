"""
test_real_model.py — Unit & Contract Tests for LocalQwenBackend
Project 2: A Machine for Misunderstanding (Blind Test Experiment)

Architecture:
- Pure contract testing isolated from torch, transformers, peft, GPU, model weights, or network.
- Directly mocks LocalQwenBackend._generate_raw() to test JSON parsing, strict VADC validation,
  rejection rules, status tracking, metadata auditing, and BlindTestService integration.
- Separate optional live smoke test (test_live_smoke_optional) for when torch and weights are present.
- Verifies that model load failures return status="BACKEND_ERROR" without raising uncaught exceptions.
"""

import json
import math
import os
import shutil
import tempfile
import time
from typing import Any, Dict, Optional
from unittest.mock import MagicMock, patch

from acoustic_bridge import FakeOscTransport
from db import Database
from real_model import LocalQwenBackend, extract_json_from_text
from service import BlindTestService
from state_machine import STATE_ERROR, STATE_INPUT_OPEN, STATE_RECEIVER_RESPONSE


def test_extract_json_from_text():
    """Verify robust extraction of JSON from various LLM response formats."""
    # 1. Clean JSON
    clean = '{"valence": 0.4, "arousal": 0.6, "dominance": 0.5, "confidence": 0.8}'
    res1 = extract_json_from_text(clean)
    assert res1["valence"] == 0.4

    # 2. Markdown fenced code block
    fenced = '```json\n{"valence": 0.1, "arousal": 0.9, "dominance": 0.2, "confidence": 0.7}\n```'
    res2 = extract_json_from_text(fenced)
    assert res2["valence"] == 0.1

    # 3. Leading and trailing explanatory text
    surrounded = 'Analysis complete. Output: {"valence": 0.8, "arousal": 0.2, "dominance": 0.9, "confidence": 0.95}. Thank you.'
    res3 = extract_json_from_text(surrounded)
    assert res3["dominance"] == 0.9

    # 4. Malformed JSON
    try:
        extract_json_from_text("Sorry, I cannot produce a vector for this.")
        assert False, "Should have raised ValueError on non-JSON"
    except ValueError as e:
        assert "Failed to parse model output as JSON" in str(e)


def test_contract_mocked_generate_raw_success():
    """Verify LocalQwenBackend contract when _generate_raw returns valid JSON."""
    backend = LocalQwenBackend(lazy_load=True)
    backend._model_name = "MockedQwen2.5-1.5B"

    # Mock _generate_raw directly (zero torch / transformers / weight dependencies)
    backend._generate_raw = MagicMock(
        return_value='{"valence": 0.35, "arousal": 0.75, "dominance": 0.45, "confidence": 0.88}'
    )

    res = backend.infer("Shivers down the spine as the temperature drops.")

    assert res.status == "SUCCESS"
    assert res.output is not None
    assert res.output["valence"] == 0.35
    assert res.output["arousal"] == 0.75
    assert res.output["confidence"] == 0.88
    assert res.fallback_used is False
    assert res.backend == "local_qwen"
    assert res.model_name == "MockedQwen2.5-1.5B"
    assert res.prompt_version == "local-qwen-v1"
    assert res.latency_ms >= 0
    assert "0.35" in res.raw_output
    backend._generate_raw.assert_called_once_with("Shivers down the spine as the temperature drops.")


def test_contract_strict_rejection_no_silent_neutral():
    """Ensure out-of-range, NaN, Infinity, or missing fields are strictly rejected and NEVER silently neutralized."""
    backend = LocalQwenBackend(lazy_load=True)
    backend._model_name = "MockedQwen"

    # 1. Out of range (> 1.0)
    backend._generate_raw = MagicMock(
        return_value='{"valence": 1.5, "arousal": 0.5, "dominance": 0.5, "confidence": 0.5}'
    )
    res1 = backend.infer("Test out of range")
    assert res1.status == "INVALID_RANGE"
    assert res1.output is None  # MUST NOT be neutral 0.5 vector!
    assert "must be in range [0.0, 1.0]" in str(res1.fallback_reason)

    # 2. Out of range (< 0.0)
    backend._generate_raw = MagicMock(
        return_value='{"valence": -0.2, "arousal": 0.5, "dominance": 0.5, "confidence": 0.5}'
    )
    res_neg = backend.infer("Test negative")
    assert res_neg.status == "INVALID_RANGE"
    assert res_neg.output is None

    # 3. Missing field (dominance missing)
    backend._generate_raw = MagicMock(
        return_value='{"valence": 0.5, "arousal": 0.5, "confidence": 0.5}'
    )
    res2 = backend.infer("Test missing field")
    assert res2.status == "INVALID_RANGE"
    assert res2.output is None
    assert "missing required field 'dominance'" in str(res2.fallback_reason)

    # 4. NaN / Infinity in JSON
    backend._generate_raw = MagicMock(
        return_value='{"valence": "NaN", "arousal": 0.5, "dominance": 0.5, "confidence": 0.5}'
    )
    res_nan = backend.infer("Test NaN")
    assert res_nan.status == "INVALID_RANGE"
    assert res_nan.output is None

    # 5. Non-JSON output
    backend._generate_raw = MagicMock(
        return_value="I am an AI and cannot feel emotions."
    )
    res3 = backend.infer("Test non json")
    assert res3.status == "INVALID_JSON"
    assert res3.output is None
    assert res3.raw_output == "I am an AI and cannot feel emotions."


def test_contract_backend_error_handling_no_uncaught_exception():
    """Verify that if _generate_raw raises an exception, infer() returns BACKEND_ERROR without crashing."""
    backend = LocalQwenBackend(lazy_load=True)
    backend._generate_raw = MagicMock(side_effect=RuntimeError("CUDA/MPS device out of memory"))

    res = backend.infer("Valid text that encounters backend error")
    assert res.status == "BACKEND_ERROR"
    assert res.output is None
    assert "CUDA/MPS device out of memory" in str(res.fallback_reason)
    assert res.latency_ms >= 0


def test_contract_service_integration_with_local_qwen_backend():
    """Verify BlindTestService properly transitions to ERROR when LocalQwenBackend fails, and commits marker when it succeeds."""
    temp_dir = tempfile.mkdtemp()
    try:
        db = Database(db_path=os.path.join(temp_dir, "test_real_model.db"))
        db.init_db()

        backend = LocalQwenBackend(lazy_load=True)
        backend._model_name = "MockedQwen"

        fake_osc = FakeOscTransport()
        service = BlindTestService(db=db, model_backend=backend, osc_transport=fake_osc)

        session_id = "s_rm_01"
        service.create_session(session_id)
        res_a = service.join(session_id, "A", "tok_a")
        res_b = service.join(session_id, "B", "tok_b")
        p_a = res_a["participant"]["participant_id"]
        p_b = res_b["participant"]["participant_id"]
        service.ready(session_id, p_a)
        service.ready(session_id, p_b)
        service.start_session(session_id)

        # 1. Failure scenario: model outputs invalid JSON
        backend._generate_raw = MagicMock(return_value="Corrupted model response")
        vadc_in = {"valence": 0.5, "arousal": 0.5, "dominance": 0.5, "confidence": 0.5}
        res_fail = service.submit_input(session_id, p_a, "Cold breath in the room", vadc_in, "sub_fail")

        assert res_fail["accepted"] is False
        assert res_fail["model_status"] == "INVALID_JSON"

        # Check DB session status is STATE_ERROR and NO MARKER COMMITTED
        full_session = service.db.get_full_session(session_id)
        assert full_session["session"]["status"] == STATE_ERROR
        assert len(full_session["markers"]) == 0

        # Reset session for success scenario
        session_id_ok = "s_rm_02"
        service.create_session(session_id_ok)
        res_ok_a = service.join(session_id_ok, "A", "tok_a")
        res_ok_b = service.join(session_id_ok, "B", "tok_b")
        p_ok_a = res_ok_a["participant"]["participant_id"]
        p_ok_b = res_ok_b["participant"]["participant_id"]
        service.ready(session_id_ok, p_ok_a)
        service.ready(session_id_ok, p_ok_b)
        service.start_session(session_id_ok)

        # 2. Success scenario: model outputs valid JSON
        backend._generate_raw = MagicMock(
            return_value='{"valence": 0.25, "arousal": 0.85, "dominance": 0.15, "confidence": 0.9}'
        )
        res_ok = service.submit_input(session_id_ok, p_ok_a, "Heart racing violently", vadc_in, "sub_ok")

        assert res_ok["accepted"] is True
        assert res_ok["session_status"] == STATE_RECEIVER_RESPONSE
        assert res_ok["marker_id"] is not None

        # Verify model run was saved in DB with full audit trail
        full_ok = service.db.get_full_session(session_id_ok)
        assert len(full_ok["markers"]) == 1
        assert len(full_ok["model_runs"]) == 1
        m_run = full_ok["model_runs"][0]
        assert m_run["model_name"] == "MockedQwen"
        assert m_run["backend"] == "local_qwen"
        assert m_run["status"] == "SUCCESS"
        assert m_run["output"]["valence"] == 0.25

        # Double-blind projection verification: receiver MUST NOT see model reasoning or model output
        proj_receiver = service.get_projection(session_id_ok, p_ok_b)
        dumped = json.dumps(proj_receiver)
        assert "0.25" not in dumped
        assert "model_output" not in dumped
        assert "output" not in dumped
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_live_smoke_optional():
    """
    Optional smoke test that runs the real un-mocked backend ONLY if
    torch and model weights are accessible, otherwise skips gracefully.
    """
    enable_smoke = os.environ.get("RUN_LIVE_MODEL_SMOKE", "0") == "1"
    if not enable_smoke:
        # Skipped by default in automated non-GPU/CI test runs
        return

    try:
        import torch
        from transformers import AutoModelForCausalLM
    except ImportError:
        print("[!] Torch / transformers not installed; skipping optional live smoke test.")
        return

    backend = LocalQwenBackend(lazy_load=True)
    res = backend.infer("Deep night, cold glass pane vibrating against the wind.")
    assert res.status in ("SUCCESS", "BACKEND_ERROR")
    if res.status == "SUCCESS":
        assert res.output is not None
        assert 0.0 <= res.output["valence"] <= 1.0


if __name__ == "__main__":
    print("[*] Running test_real_model.py...")
    test_extract_json_from_text()
    test_contract_mocked_generate_raw_success()
    test_contract_strict_rejection_no_silent_neutral()
    test_contract_backend_error_handling_no_uncaught_exception()
    test_contract_service_integration_with_local_qwen_backend()
    test_live_smoke_optional()
    print("[✓] All Phase 5B Real Model Backend contract tests passed successfully!")
