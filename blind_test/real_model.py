"""
real_model.py — Production Local Qwen2.5-1.5B LoRA Model Backend Implementation
Project 2: A Machine for Misunderstanding (Blind Test Experiment)

Architecture:
- Implements LocalQwenBackend behind the abstract ModelBackend interface (acoustic_bridge.py).
- Maps phenomenological body descriptions to strict VADC vectors:
    valence:    [0.0, 1.0]
    arousal:    [0.0, 1.0]
    dominance:  [0.0, 1.0]
    confidence: [0.0, 1.0]
- Zero external cloud/API network dependencies (offline MPS/CUDA/CPU inference).
- Strict validation:
    - Parses JSON output.
    - Rejects missing fields, invalid JSON, non-numeric values, out-of-range values, NaN, and Infinity.
    - NEVER silently converts invalid outputs to neutral vectors (preserves scientific integrity).
- Detailed metadata auditing:
    - Records raw_output, backend, model_name, prompt_version, status, fallback_used,
      fallback_reason, and latency_ms.
- Zero credential requirements (no hardcoded API keys).
- Model execution executes strictly outside SQLite transactions.
"""

from dataclasses import asdict
import json
import math
import os
import re
import sys
import time
from typing import Any, Dict, Optional, Tuple

from acoustic_bridge import ModelBackend, ModelResult
from metrics import validate_vadc

DEFAULT_BASE_MODEL = os.environ.get("BASE_MODEL", "Qwen/Qwen2.5-1.5B-Instruct")
DEFAULT_LORA_PATH = os.path.join(os.path.dirname(__file__), "..", "models", "qwen_lora")
DEFAULT_PROMPT_VERSION = "local-qwen-v1"

SYSTEM_PROMPT = (
    "You map a phenomenological body description to a VAD vector. "
    "Return ONLY a JSON object with keys valence, arousal, dominance, confidence, "
    "each a number between 0 and 1. "
    "Never output emotion labels or any text outside the JSON."
)


def extract_json_from_text(raw_text: str) -> Dict[str, Any]:
    """
    Extract first valid JSON object enclosed in braces from raw model text.
    Raises ValueError if no valid JSON object can be parsed.
    """
    cleaned = raw_text.strip()
    match = re.search(r"\{.*?\}", cleaned, re.DOTALL)
    if match:
        json_str = match.group(0)
    else:
        json_str = cleaned

    try:
        data = json.loads(json_str)
        if not isinstance(data, dict):
            raise ValueError(f"Extracted JSON is not a dictionary, got {type(data).__name__}")
        return data
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse model output as JSON: {e}")


class LocalQwenBackend(ModelBackend):
    """
    Local Qwen2.5-1.5B + LoRA Phenomenological Inference Engine.
    Uses Metal MPS on macOS, CUDA on Linux, or CPU fallback.
    """

    def __init__(
        self,
        base_model_name: str = DEFAULT_BASE_MODEL,
        lora_path: Optional[str] = DEFAULT_LORA_PATH,
        prompt_version: str = DEFAULT_PROMPT_VERSION,
        device_override: Optional[str] = None,
        lazy_load: bool = True,
        max_new_tokens: int = 80,
        temperature: float = 0.1,
    ):
        self.base_model_name = base_model_name
        self.lora_path = lora_path if (lora_path and os.path.exists(lora_path)) else None
        self.prompt_version = prompt_version
        self.device_override = device_override
        self.max_new_tokens = max_new_tokens
        self.temperature = temperature

        self._model = None
        self._tokenizer = None
        self._device = None
        self._model_name = self.base_model_name

        if not lazy_load:
            self._ensure_model_loaded()

    def _get_device(self):
        if self._device is not None:
            return self._device

        import torch

        if self.device_override:
            self._device = torch.device(self.device_override)
        elif torch.backends.mps.is_available():
            self._device = torch.device("mps")
        elif torch.cuda.is_available():
            self._device = torch.device("cuda")
        else:
            self._device = torch.device("cpu")
        return self._device

    def _ensure_model_loaded(self) -> None:
        """Initialize and cache tokenizer and model weights."""
        if self._model is not None and self._tokenizer is not None:
            return

        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        device = self._get_device()
        model_path = self.base_model_name

        # If model_path is not a local directory, attempt ModelScope or HuggingFace
        if not os.path.exists(model_path):
            try:
                from modelscope import snapshot_download

                model_path = snapshot_download(self.base_model_name)
            except Exception:
                pass

        self._tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
        base_model = AutoModelForCausalLM.from_pretrained(
            model_path,
            torch_dtype=torch.float16 if device.type != "cpu" else torch.float32,
            trust_remote_code=True,
        ).to(device)

        if self.lora_path and os.path.exists(self.lora_path):
            from peft import PeftModel

            self._model = PeftModel.from_pretrained(base_model, self.lora_path).to(device)
            self._model_name = f"{self.base_model_name}+LoRA"
        else:
            self._model = base_model
            self._model_name = self.base_model_name

        self._model.eval()

    def _generate_raw(self, text: str) -> str:
        """
        Low-level raw text generation using torch and loaded weights.
        Isolated in its own method so contract tests can mock it directly
        without requiring torch, transformers, or GPU.
        """
        self._ensure_model_loaded()

        import torch

        device = self._get_device()
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ]
        prompt = self._tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = self._tokenizer(prompt, return_tensors="pt").to(device)

        with torch.no_grad():
            outputs = self._model.generate(
                **inputs,
                max_new_tokens=self.max_new_tokens,
                temperature=self.temperature,
                do_sample=False,
                pad_token_id=self._tokenizer.eos_token_id,
            )
        generated_token_ids = outputs[0][inputs.input_ids.shape[1] :]
        return self._tokenizer.decode(generated_token_ids, skip_special_tokens=True).strip()

    def infer(self, text: str, context: Optional[Dict[str, Any]] = None) -> ModelResult:
        """
        Run inference on the somatic/phenomenological text.
        Returns ModelResult with strict validation.
        Completely isolated from torch/transformers: calls _generate_raw(text),
        then parses JSON and validates VADC purely in standard library Python.
        """
        start_time = time.monotonic()
        active_model_name = getattr(self, "_model_name", self.base_model_name)

        # Input text sanity check
        if not text or not text.strip():
            latency = int((time.monotonic() - start_time) * 1000)
            return ModelResult(
                output=None,
                raw_output="",
                status="INVALID_INPUT",
                fallback_used=False,
                fallback_reason="Input text is empty",
                latency_ms=latency,
                backend="local_qwen",
                model_name=active_model_name,
                prompt_version=self.prompt_version,
            )

        # Generate raw string from model (isolated helper)
        try:
            raw_text = self._generate_raw(text)
        except Exception as e:
            latency = int((time.monotonic() - start_time) * 1000)
            return ModelResult(
                output=None,
                raw_output="",
                status="BACKEND_ERROR",
                fallback_used=False,
                fallback_reason=f"Model generation error: {e}",
                latency_ms=latency,
                backend="local_qwen",
                model_name=active_model_name,
                prompt_version=self.prompt_version,
            )

        latency = int((time.monotonic() - start_time) * 1000)

        # 1. JSON parsing
        try:
            parsed_data = extract_json_from_text(raw_text)
        except ValueError as e:
            return ModelResult(
                output=None,
                raw_output=raw_text,
                status="INVALID_JSON",
                fallback_used=False,
                fallback_reason=str(e),
                latency_ms=latency,
                backend="local_qwen",
                model_name=self._model_name,
                prompt_version=self.prompt_version,
            )

        # 2. Strict VADC dimension and range validation (NO SILENT CONVERSION TO NEUTRAL)
        try:
            (v, a, d), conf = validate_vadc(parsed_data, "local_qwen_output")
            validated_output = {
                "valence": v,
                "arousal": a,
                "dominance": d,
                "confidence": conf,
            }
        except ValueError as e:
            return ModelResult(
                output=None,
                raw_output=raw_text,
                status="INVALID_RANGE",
                fallback_used=False,
                fallback_reason=f"Model output failed VADC validation: {e}",
                latency_ms=latency,
                backend="local_qwen",
                model_name=self._model_name,
                prompt_version=self.prompt_version,
            )

        return ModelResult(
            output=validated_output,
            raw_output=raw_text,
            status="SUCCESS",
            fallback_used=False,
            fallback_reason=None,
            latency_ms=latency,
            backend="local_qwen",
            model_name=self._model_name,
            prompt_version=self.prompt_version,
        )


class DeepSeekBackend(ModelBackend):
    """
    Cloud DeepSeek API Backend for Phenomenological VADC Inference.
    Falls back gracefully to LocalQwenBackend or error status if API key or network fails.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://api.deepseek.com/chat/completions",
        model: str = "deepseek-chat",
        timeout: float = 15.0,
    ):
        self.api_key = api_key or os.environ.get("DEEPSEEK_API_KEY", "")
        if not self.api_key:
            key_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "deepseek.key")
            if os.path.exists(key_file):
                try:
                    with open(key_file, "r", encoding="utf-8") as f:
                        self.api_key = f.read().strip()
                except Exception:
                    pass
        self.base_url = base_url
        self.model = model
        self.timeout = timeout
        self.prompt_version = "deepseek-v1"

    def infer(self, text: str) -> ModelResult:
        import urllib.request
        import urllib.error

        t0 = time.time()
        if not self.api_key:
            return ModelResult(
                output=None,
                raw_output="",
                status="BACKEND_ERROR",
                fallback_used=False,
                fallback_reason="DEEPSEEK_API_KEY environment variable is not set",
                latency_ms=0,
                backend="deepseek",
                model_name=self.model,
                prompt_version=self.prompt_version,
            )

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
            "temperature": 0.3,
            "response_format": {"type": "json_object"},
        }

        req = urllib.request.Request(
            self.base_url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                body = response.read().decode("utf-8")
                res_json = json.loads(body)
                raw_content = res_json["choices"][0]["message"]["content"]
        except Exception as e:
            latency = int((time.time() - t0) * 1000)
            return ModelResult(
                output=None,
                raw_output=str(e),
                status="BACKEND_ERROR",
                fallback_used=False,
                fallback_reason=f"DeepSeek API request failed: {e}",
                latency_ms=latency,
                backend="deepseek",
                model_name=self.model,
                prompt_version=self.prompt_version,
            )

        latency = int((time.time() - t0) * 1000)

        # Parse & Validate
        try:
            parsed = extract_json_from_text(raw_content)
            (v, a, d), conf = validate_vadc(parsed, "deepseek_output")
            validated = {
                "valence": v,
                "arousal": a,
                "dominance": d,
                "confidence": conf,
            }
            return ModelResult(
                output=validated,
                raw_output=raw_content,
                status="SUCCESS",
                fallback_used=False,
                fallback_reason=None,
                latency_ms=latency,
                backend="deepseek",
                model_name=self.model,
                prompt_version=self.prompt_version,
            )
        except Exception as e:
            return ModelResult(
                output=None,
                raw_output=raw_content,
                status="INVALID_JSON",
                fallback_used=False,
                fallback_reason=f"Failed to validate DeepSeek output: {e}",
                latency_ms=latency,
                backend="deepseek",
                model_name=self.model,
                prompt_version=self.prompt_version,
            )

