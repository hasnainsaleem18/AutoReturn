# -------------------------
# VOICE SERVICE
# -------------------------
"""
Push-to-talk voice control service for AutoReturn.

This module stays decoupled from the rest of the application and exposes only:
- deterministic command parsing
- background hotkey / recording / transcription workers
- a Qt signal-based runtime service
"""

from __future__ import annotations

import importlib
import os
import re
import sys
from dataclasses import dataclass
from threading import Lock
from typing import Any, Dict, Optional

from PySide6.QtCore import QObject, QThread, Signal


def _optional_import(module_name: str):
    """Import a module lazily and tolerate missing optional dependencies."""
    try:
        return importlib.import_module(module_name)
    except Exception:
        return None


@dataclass
class VoiceCommand:
    """Structured result returned by the voice command parser."""

    action_type: str
    action: str
    parameters: Dict[str, Any]
    raw_text: str


@dataclass
class AudioCapture:
    """Prepared in-memory audio payload for transcription."""

    samples: Any
    sample_rate: int
    duration_seconds: float
    peak_level: float
    rms_level: float


class VoiceCommandParser:
    """Fast rule/regex command router for voice control."""

    UI_ACTIONS = {
        "show all": ("filter", {"filter_id": "all"}),
        "show all messages": ("filter", {"filter_id": "all"}),
        "show everything": ("filter", {"filter_id": "all"}),
        "all messages": ("filter", {"filter_id": "all"}),
        "show gmail": ("filter", {"filter_id": "gmail"}),
        "show gmail messages": ("filter", {"filter_id": "gmail"}),
        "gmail only": ("filter", {"filter_id": "gmail"}),
        "show slack": ("filter", {"filter_id": "slack"}),
        "show slack messages": ("filter", {"filter_id": "slack"}),
        "slack only": ("filter", {"filter_id": "slack"}),
        "show urgent": ("filter", {"filter_id": "urgent"}),
        "show urgent messages": ("filter", {"filter_id": "urgent"}),
        "urgent messages": ("filter", {"filter_id": "urgent"}),
        "urgent only": ("filter", {"filter_id": "urgent"}),
        "high priority": ("filter", {"filter_id": "urgent"}),
        "open settings": ("open_settings", {}),
        "settings": ("open_settings", {}),
        "show notifications": ("show_notifications", {}),
        "notifications": ("show_notifications", {}),
        "next page": ("next_page", {}),
        "previous page": ("prev_page", {}),
        "go back": ("prev_page", {}),
        "generate summaries": ("generate_summaries", {}),
        "generate all summaries": ("generate_summaries", {}),
        "summarize all": ("generate_summaries", {}),
    }

    SEARCH_PATTERNS = (
        re.compile(r"^\s*search\s+for\s+(.+?)\s*$", re.IGNORECASE),
        re.compile(r"^\s*search\s+(.+?)\s*$", re.IGNORECASE),
        re.compile(r"^\s*find\s+(.+?)\s*$", re.IGNORECASE),
        re.compile(r"^\s*look\s+for\s+(.+?)\s*$", re.IGNORECASE),
    )

    BACKEND_TRIGGERS = (
        "sync",
        "fetch",
        "get messages",
        "check email",
        "check gmail",
        "check slack",
        "summarize",
        "summary",
        "send",
        "reply",
        "draft",
        "analyze",
        "priority",
    )

    MESSAGE_ORDINALS = {
        "first": 1,
        "second": 2,
        "third": 3,
        "fourth": 4,
        "fifth": 5,
    }

    @classmethod
    def parse(cls, raw_text: str) -> VoiceCommand:
        """Parse a spoken command into a UI action or orchestrator fallback."""
        text = cls._normalize(raw_text)
        if not text:
            return VoiceCommand("ui_action", "noop", {}, raw_text)

        ui_match = cls._match_ui_action(text)
        if ui_match is not None:
            action, params = ui_match
            return VoiceCommand("ui_action", action, dict(params), raw_text)

        search_query = cls._extract_search_query(raw_text)
        if search_query:
            return VoiceCommand("ui_action", "search", {"query": search_query}, raw_text)

        reply_target = cls._extract_reply_target(text)
        if reply_target:
            return VoiceCommand(
                "ui_action",
                "reply_to_sender",
                {"sender_name": reply_target},
                raw_text,
            )

        draft_target = cls._extract_draft_target(text)
        if draft_target:
            return VoiceCommand(
                "ui_action",
                "draft_for_sender",
                {"sender_name": draft_target},
                raw_text,
            )

        message_index = cls._extract_message_index(text)
        if message_index is not None and cls._contains_any(text, ("open", "show", "read", "view")):
            return VoiceCommand(
                "ui_action",
                "open_message_by_index",
                {"index": message_index},
                raw_text,
            )

        if cls._contains_any(text, cls.BACKEND_TRIGGERS):
            return VoiceCommand(
                "agent_action",
                "orchestrator",
                {"command": raw_text.strip()},
                raw_text,
            )

        if len(text.split()) < 2:
            return VoiceCommand("ui_action", "noop", {}, raw_text)

        return VoiceCommand(
            "agent_action",
            "orchestrator",
            {"command": raw_text.strip()},
            raw_text,
        )

    @classmethod
    def _normalize(cls, text: str) -> str:
        return re.sub(r"\s+", " ", (text or "").strip()).lower()

    @classmethod
    def _match_ui_action(cls, text: str) -> Optional[tuple]:
        for phrase, result in cls.UI_ACTIONS.items():
            if text == phrase:
                return result
            if re.fullmatch(rf"(?:please\s+)?{re.escape(phrase)}(?:\s+please)?", text):
                return result
        return None

    @classmethod
    def _extract_search_query(cls, raw_text: str) -> Optional[str]:
        for pattern in cls.SEARCH_PATTERNS:
            match = pattern.match(raw_text or "")
            if match:
                query = re.sub(r"\s+", " ", match.group(1).strip())
                return query or None
        return None

    @classmethod
    def _extract_reply_target(cls, text: str) -> Optional[str]:
        patterns = (
            r"\b(?:reply|respond)\s+to\s+(.+?)\s*$",
            r"\bsend\s+(?:a\s+)?message\s+to\s+(.+?)\s*$",
        )
        return cls._extract_named_target(text, patterns)

    @classmethod
    def _extract_draft_target(cls, text: str) -> Optional[str]:
        patterns = (
            r"\bdraft(?:\s+(?:a|the))?(?:\s+response)?\s+(?:for|to)\s+(.+?)\s*$",
            r"\bwrite(?:\s+(?:a|the))?(?:\s+response)?\s+(?:for|to)\s+(.+?)\s*$",
        )
        return cls._extract_named_target(text, patterns)

    @classmethod
    def _extract_named_target(cls, text: str, patterns: tuple) -> Optional[str]:
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if not match:
                continue

            candidate = match.group(1)
            candidate = re.sub(r"\b(message|email|mail|please|now)\b", "", candidate, flags=re.IGNORECASE)
            candidate = candidate.replace("'s", "").strip(" .,!?:;")
            candidate = re.sub(r"\s+", " ", candidate).strip()
            if not candidate:
                continue

            if "message " in candidate:
                continue
            if "@" in candidate:
                return candidate.lower()
            return " ".join(part.capitalize() for part in candidate.split())
        return None

    @classmethod
    def _extract_message_index(cls, text: str) -> Optional[int]:
        for word, index in cls.MESSAGE_ORDINALS.items():
            if re.search(rf"\b{word}\b", text):
                return index - 1

        match = re.search(r"\bmessage\s+(\d+)\b", text)
        if match:
            return max(int(match.group(1)) - 1, 0)
        return None

    @classmethod
    def _contains_any(cls, text: str, phrases: tuple) -> bool:
        padded = f" {text} "
        return any(f" {phrase} " in padded for phrase in phrases)


class HotkeyListenerThread(QThread):
    """Background global hotkey listener."""

    hotkey_pressed = Signal()
    hotkey_released = Signal()
    listener_error = Signal(str)

    QUARTZ_KEYCODES = {
        "a": 0,
        "s": 1,
        "d": 2,
        "f": 3,
        "h": 4,
        "g": 5,
        "z": 6,
        "x": 7,
        "c": 8,
        "v": 9,
        "b": 11,
        "q": 12,
        "w": 13,
        "e": 14,
        "r": 15,
        "y": 16,
        "t": 17,
        "1": 18,
        "2": 19,
        "3": 20,
        "4": 21,
        "6": 22,
        "5": 23,
        "=": 24,
        "9": 25,
        "7": 26,
        "-": 27,
        "8": 28,
        "0": 29,
        "]": 30,
        "o": 31,
        "u": 32,
        "[": 33,
        "i": 34,
        "p": 35,
        "l": 37,
        "j": 38,
        "'": 39,
        "k": 40,
        ";": 41,
        "\\": 42,
        ",": 43,
        "/": 44,
        "n": 45,
        "m": 46,
        ".": 47,
        "tab": 48,
        "space": 49,
        "`": 50,
        "backspace": 51,
        "enter": 36,
        "esc": 53,
    }

    def __init__(self, hotkey: str = "ctrl+shift+v", backend: Optional[str] = None):
        super().__init__()
        self.hotkey = hotkey
        self.backend = backend or ("quartz" if sys.platform == "darwin" else "keyboard")
        self._running = False
        self._hotkey_active = False
        self._hotkey_tokens = self._parse_hotkey_tokens(hotkey)
        self._quartz = None
        self._quartz_run_loop = None
        self._quartz_tap = None
        self._quartz_source = None
        self._quartz_callback = None
        self._quartz_hotkey = self._build_quartz_hotkey(hotkey)

    def run(self):
        self._running = True
        try:
            if self.backend == "quartz":
                self._run_quartz_listener()
            else:
                self._run_keyboard_listener()
        except Exception as exc:
            self.listener_error.emit(str(exc))
        finally:
            self._stop_backend_listener()
            self._hotkey_active = False

    def stop(self):
        self._running = False
        self._stop_backend_listener()
        self.quit()

    def _run_keyboard_listener(self):
        keyboard = _optional_import("keyboard")
        if keyboard is None:
            self.listener_error.emit("keyboard dependency is not installed.")
            return

        keyboard.add_hotkey(self.hotkey, self.hotkey_pressed.emit)
        last_key = self.hotkey.split("+")[-1]
        keyboard.on_release_key(last_key, lambda _event: self.hotkey_released.emit())

        while self._running:
            self.msleep(100)

    def _run_quartz_listener(self):
        self._quartz = _optional_import("Quartz")
        if self._quartz is None:
            self.listener_error.emit("Quartz dependency is not installed.")
            return

        if self._quartz_hotkey is None:
            self.listener_error.emit(
                f"Unsupported macOS voice hotkey: {self.hotkey}. "
                "Use modifier keys plus a single letter, digit, or basic key."
            )
            return

        if not self._macos_access_granted(self._quartz):
            self.listener_error.emit(
                "macOS Accessibility/Input Monitoring permission is required "
                "for the global voice hotkey."
            )
            return

        key_mask = (
            (1 << self._quartz.kCGEventKeyDown)
            | (1 << self._quartz.kCGEventKeyUp)
            | (1 << self._quartz.kCGEventFlagsChanged)
        )

        self._quartz_callback = self._make_quartz_callback()
        self._quartz_tap = self._quartz.CGEventTapCreate(
            self._quartz.kCGSessionEventTap,
            self._quartz.kCGHeadInsertEventTap,
            self._quartz.kCGEventTapOptionListenOnly,
            key_mask,
            self._quartz_callback,
            None,
        )

        if self._quartz_tap is None:
            self.listener_error.emit(
                "Unable to create macOS event tap. Grant Accessibility/Input Monitoring "
                "permission to Terminal or Python, then restart the app."
            )
            return

        self._quartz_source = self._quartz.CFMachPortCreateRunLoopSource(None, self._quartz_tap, 0)
        self._quartz_run_loop = self._quartz.CFRunLoopGetCurrent()
        self._quartz.CFRunLoopAddSource(
            self._quartz_run_loop,
            self._quartz_source,
            self._quartz.kCFRunLoopCommonModes,
        )
        self._quartz.CGEventTapEnable(self._quartz_tap, True)

        while self._running:
            self._quartz.CFRunLoopRunInMode(self._quartz.kCFRunLoopDefaultMode, 0.25, False)

    def _stop_backend_listener(self):
        if self.backend == "quartz":
            if self._quartz is not None and self._quartz_run_loop is not None:
                try:
                    self._quartz.CFRunLoopStop(self._quartz_run_loop)
                except Exception:
                    pass
            if self._quartz is not None and self._quartz_tap is not None:
                invalidate = getattr(self._quartz, "CFMachPortInvalidate", None)
                if callable(invalidate):
                    try:
                        invalidate(self._quartz_tap)
                    except Exception:
                        pass
            self._quartz_run_loop = None
            self._quartz_source = None
            self._quartz_tap = None
            self._quartz_callback = None
            self._quartz = None
        else:
            keyboard = _optional_import("keyboard")
            if keyboard is not None:
                try:
                    keyboard.unhook_all()
                except Exception:
                    pass

    @classmethod
    def _parse_hotkey_tokens(cls, hotkey: str) -> set[str]:
        tokens = set()
        for part in (hotkey or "").split("+"):
            token = cls._normalize_hotkey_token(part)
            if token:
                tokens.add(token)
        return tokens

    @staticmethod
    def _normalize_hotkey_token(token: str) -> str:
        normalized = (token or "").strip().lower()
        aliases = {
            "control": "ctrl",
            "ctl": "ctrl",
            "option": "alt",
            "opt": "alt",
            "command": "cmd",
            "super": "cmd",
            "win": "cmd",
            "return": "enter",
            "escape": "esc",
            "delete": "backspace",
        }
        normalized = aliases.get(normalized, normalized)
        if normalized == " ":
            return "space"
        return normalized

    @classmethod
    def _build_quartz_hotkey(cls, hotkey: str) -> Optional[dict]:
        modifiers = {
            token
            for token in cls._parse_hotkey_tokens(hotkey)
            if token in {"ctrl", "shift", "alt", "cmd"}
        }
        key_tokens = [
            token
            for token in cls._parse_hotkey_tokens(hotkey)
            if token not in {"ctrl", "shift", "alt", "cmd"}
        ]
        if len(key_tokens) != 1:
            return None

        main_key = key_tokens[0]
        keycode = cls.QUARTZ_KEYCODES.get(main_key)
        if keycode is None:
            return None

        return {
            "main_key": main_key,
            "keycode": keycode,
            "modifiers": modifiers,
        }

    @staticmethod
    def _macos_access_granted(quartz) -> bool:
        preflight = getattr(quartz, "CGPreflightListenEventAccess", None)
        request = getattr(quartz, "CGRequestListenEventAccess", None)

        if callable(preflight):
            try:
                granted = bool(preflight())
            except Exception:
                granted = False
            if not granted and callable(request):
                try:
                    request()
                except Exception:
                    pass
            return granted
        return True

    def _make_quartz_callback(self):
        quartz = self._quartz
        hotkey = self._quartz_hotkey or {}
        required_modifiers = hotkey.get("modifiers", set())
        required_keycode = hotkey.get("keycode")

        modifier_mask = 0
        if "ctrl" in required_modifiers:
            modifier_mask |= quartz.kCGEventFlagMaskControl
        if "shift" in required_modifiers:
            modifier_mask |= quartz.kCGEventFlagMaskShift
        if "alt" in required_modifiers:
            modifier_mask |= quartz.kCGEventFlagMaskAlternate
        if "cmd" in required_modifiers:
            modifier_mask |= quartz.kCGEventFlagMaskCommand

        def callback(_proxy, event_type, event, _refcon):
            if not self._running:
                return event

            flags = quartz.CGEventGetFlags(event)
            modifiers_active = (flags & modifier_mask) == modifier_mask
            keycode = quartz.CGEventGetIntegerValueField(event, quartz.kCGKeyboardEventKeycode)

            if event_type == quartz.kCGEventKeyDown:
                if keycode == required_keycode and modifiers_active and not self._hotkey_active:
                    self._hotkey_active = True
                    self.hotkey_pressed.emit()
            elif event_type == quartz.kCGEventKeyUp:
                if keycode == required_keycode and self._hotkey_active:
                    self._hotkey_active = False
                    self.hotkey_released.emit()
            elif event_type == quartz.kCGEventFlagsChanged:
                if self._hotkey_active and not modifiers_active:
                    self._hotkey_active = False
                    self.hotkey_released.emit()

            return event

        return callback


class AudioRecorderThread(QThread):
    """Record mono microphone input and prepare it for Whisper."""

    recording_stopped = Signal(object)

    SAMPLE_RATE = 16000
    BLOCK_SIZE = 2048
    MAX_SECONDS = 30
    TARGET_PEAK = 0.92
    MAX_GAIN = 6.0
    MIN_SIGNAL_PEAK = 0.015
    EDGE_NOISE_SECONDS = 0.18
    TRIM_PADDING_SECONDS = 0.18
    LOW_FREQUENCY_CUTOFF = 80

    def __init__(self):
        super().__init__()
        self._stop_flag = False

    def run(self):
        np = _optional_import("numpy")
        sd = _optional_import("sounddevice")
        signal = _optional_import("scipy.signal")

        if np is None or sd is None:
            self.recording_stopped.emit(None)
            return

        frames = []
        total_frames = 0
        max_frames = self.SAMPLE_RATE * self.MAX_SECONDS

        try:
            with sd.InputStream(
                samplerate=self.SAMPLE_RATE,
                channels=1,
                dtype="float32",
                blocksize=self.BLOCK_SIZE,
                latency="low",
            ) as stream:
                while not self._stop_flag and total_frames < max_frames:
                    block, _overflowed = stream.read(self.BLOCK_SIZE)
                    frames.append(block.copy())
                    total_frames += len(block)
        except Exception as exc:
            print(f"[VoiceService] Recording error: {exc}")
            self.recording_stopped.emit(None)
            return

        if not frames:
            self.recording_stopped.emit(None)
            return

        try:
            audio = np.concatenate(frames, axis=0).flatten()
            capture = self.prepare_capture(
                audio,
                sample_rate=self.SAMPLE_RATE,
                np_module=np,
                signal_module=signal,
            )
            self.recording_stopped.emit(capture)
        except Exception as exc:
            print(f"[VoiceService] Failed to prepare audio capture: {exc}")
            self.recording_stopped.emit(None)

    def stop_recording(self):
        self._stop_flag = True

    @classmethod
    def prepare_capture(cls, audio: Any, sample_rate: int, np_module=None, signal_module=None) -> Optional[AudioCapture]:
        """Clean and normalize microphone input before it reaches Whisper."""
        np = np_module or _optional_import("numpy")
        if np is None or audio is None:
            return None

        samples = np.asarray(audio, dtype=np.float32).flatten()
        if samples.size == 0:
            return None

        samples = np.nan_to_num(samples, nan=0.0, posinf=0.0, neginf=0.0)
        samples = samples - float(np.mean(samples))

        if signal_module is not None and samples.size > sample_rate // 8:
            try:
                sos = signal_module.butter(
                    2,
                    cls.LOW_FREQUENCY_CUTOFF,
                    btype="highpass",
                    fs=sample_rate,
                    output="sos",
                )
                samples = signal_module.sosfiltfilt(sos, samples).astype(np.float32)
            except Exception:
                # Filtering is optional; keep raw audio if SciPy cannot process it.
                pass

        abs_samples = np.abs(samples)
        peak_level = float(abs_samples.max()) if abs_samples.size else 0.0
        if peak_level < cls.MIN_SIGNAL_PEAK:
            return None

        edge_samples = min(samples.size, max(int(sample_rate * cls.EDGE_NOISE_SECONDS), 1))
        if samples.size > edge_samples * 2:
            edge_profile = np.concatenate((abs_samples[:edge_samples], abs_samples[-edge_samples:]))
        else:
            edge_profile = abs_samples[:edge_samples]

        noise_floor = float(np.percentile(edge_profile, 75)) if edge_profile.size else 0.0
        speech_threshold = max(cls.MIN_SIGNAL_PEAK * 0.75, noise_floor * 2.5)
        active_indices = np.flatnonzero(abs_samples >= speech_threshold)

        if active_indices.size:
            padding = int(sample_rate * cls.TRIM_PADDING_SECONDS)
            start = max(int(active_indices[0]) - padding, 0)
            end = min(int(active_indices[-1]) + padding + 1, samples.size)
            samples = samples[start:end]
            abs_samples = np.abs(samples)
        elif peak_level < cls.MIN_SIGNAL_PEAK * 2.0:
            return None

        peak_level = float(abs_samples.max()) if abs_samples.size else 0.0
        if peak_level < cls.MIN_SIGNAL_PEAK:
            return None

        rms_level = float(np.sqrt(np.mean(np.square(samples), dtype=np.float64))) if samples.size else 0.0
        if rms_level > 1e-5 and peak_level < cls.TARGET_PEAK * 0.85:
            target_rms = 0.12
            gain = min(
                cls.MAX_GAIN,
                cls.TARGET_PEAK / max(peak_level, 1e-6),
                max(target_rms / max(rms_level, 1e-6), 1.0),
            )
            samples = samples * gain
            abs_samples = np.abs(samples)

        if noise_floor > 0:
            gate_threshold = max(noise_floor * 1.6, cls.MIN_SIGNAL_PEAK * 0.5)
            quiet_mask = abs_samples < gate_threshold
            if quiet_mask.any():
                samples = samples.copy()
                samples[quiet_mask] *= 0.35

        peak_level = float(np.max(np.abs(samples))) if samples.size else 0.0
        if peak_level > cls.TARGET_PEAK:
            samples = samples * (cls.TARGET_PEAK / peak_level)
            peak_level = cls.TARGET_PEAK

        samples = np.clip(samples, -1.0, 1.0).astype(np.float32)
        rms_level = float(np.sqrt(np.mean(np.square(samples), dtype=np.float64))) if samples.size else 0.0
        duration_seconds = samples.size / float(sample_rate)

        return AudioCapture(
            samples=samples,
            sample_rate=sample_rate,
            duration_seconds=duration_seconds,
            peak_level=peak_level,
            rms_level=rms_level,
        )


class WhisperTranscriberThread(QThread):
    """Transcribe a prepared audio buffer using local Whisper."""

    transcription_ready = Signal(str)
    transcription_failed = Signal(str)

    _model_cache: Dict[tuple[str, str], Any] = {}
    _cache_lock = Lock()
    _device_cache: Optional[str] = None

    def __init__(
        self,
        audio_input: Any,
        model_size: str = "base",
        language: str = "en",
        preferred_device: Optional[str] = None,
    ):
        super().__init__()
        self.audio_input = audio_input
        self.audio_path = audio_input
        self.model_size = model_size
        self.language = language
        self.preferred_device = preferred_device
        self.resolved_device: Optional[str] = None

    def run(self):
        try:
            model, device = self.load_cached_model(self.model_size, self.preferred_device)
            self.resolved_device = device
            result = model.transcribe(
                self.audio_input,
                language=self.language,
                task="transcribe",
                fp16=device == "cuda",
                verbose=False,
                condition_on_previous_text=False,
                temperature=0.0,
                no_speech_threshold=0.45,
            )
            text = re.sub(r"\s+", " ", (result.get("text") or "").strip())
            if text:
                self.transcription_ready.emit(text)
            else:
                self.transcription_failed.emit("Empty transcription.")
        except Exception as exc:
            self.transcription_failed.emit(str(exc))

    @classmethod
    def detect_device(cls) -> str:
        if cls._device_cache:
            return cls._device_cache

        torch = _optional_import("torch")
        if torch is None:
            cls._device_cache = "cpu"
            return cls._device_cache

        try:
            if torch.cuda.is_available():
                cls._device_cache = "cuda"
            elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                cls._device_cache = "mps"
            else:
                cls._device_cache = "cpu"
        except Exception:
            cls._device_cache = "cpu"

        return cls._device_cache

    @classmethod
    def load_cached_model(cls, model_size: str, preferred_device: Optional[str] = None) -> tuple[Any, str]:
        whisper = _optional_import("whisper")
        if whisper is None:
            raise RuntimeError("whisper dependency is not installed.")

        device = preferred_device or cls.detect_device()
        cache_key = (model_size, device)

        with cls._cache_lock:
            cached = cls._model_cache.get(cache_key)
            if cached is not None:
                return cached, device

            try:
                model = whisper.load_model(model_size, device=device)
                cls._model_cache[cache_key] = model
                return model, device
            except Exception:
                if device == "cpu":
                    raise

                fallback_key = (model_size, "cpu")
                cached = cls._model_cache.get(fallback_key)
                if cached is not None:
                    cls._device_cache = "cpu"
                    return cached, "cpu"

                model = whisper.load_model(model_size, device="cpu")
                cls._model_cache[fallback_key] = model
                cls._device_cache = "cpu"
                return model, "cpu"

    @classmethod
    def preload_model(cls, model_size: str, preferred_device: Optional[str] = None) -> str:
        _, device = cls.load_cached_model(model_size, preferred_device)
        return device

    @classmethod
    def is_model_cached(cls, model_size: str, preferred_device: Optional[str] = None) -> bool:
        device = preferred_device or cls.detect_device()
        return (model_size, device) in cls._model_cache or (model_size, "cpu") in cls._model_cache


class WhisperWarmupThread(QThread):
    """Warm Whisper in the background so the first command responds faster."""

    warmup_complete = Signal(str)
    warmup_failed = Signal(str)

    def __init__(self, model_size: str = "base", preferred_device: Optional[str] = None):
        super().__init__()
        self.model_size = model_size
        self.preferred_device = preferred_device

    def run(self):
        try:
            device = WhisperTranscriberThread.preload_model(self.model_size, self.preferred_device)
            self.warmup_complete.emit(device)
        except Exception as exc:
            self.warmup_failed.emit(str(exc))


class VoiceService(QObject):
    """Coordinate hotkey listening, recording, and local transcription."""

    command_ready = Signal(str)
    listening_started = Signal()
    listening_stopped = Signal()
    transcription_done = Signal()
    error_occurred = Signal(str)

    MIN_AUDIO_SECONDS = 0.5

    def __init__(self, hotkey: str = "ctrl+shift+v", model_size: str = "base", language: str = "en"):
        super().__init__()
        self.hotkey = hotkey
        self.model_size = model_size
        self.language = language

        self._enabled = False
        self._is_listening = False
        self._startup_error = ""
        self._hotkey_thread: Optional[HotkeyListenerThread] = None
        self._recorder: Optional[AudioRecorderThread] = None
        self._transcriber: Optional[WhisperTranscriberThread] = None
        self._warmup_thread: Optional[WhisperWarmupThread] = None
        self._resolved_device: Optional[str] = None

    def start(self) -> bool:
        """Start background voice capture. Returns True when the listener is live."""
        missing = []
        for module_name in ("whisper", "sounddevice", "numpy"):
            if _optional_import(module_name) is None:
                missing.append(module_name)

        if missing:
            self._startup_error = f"Voice unavailable: missing dependencies ({', '.join(missing)})."
            self._enabled = False
            print(f"[VoiceService] {self._startup_error}")
            return False

        hotkey_backend = self._select_hotkey_backend()
        hotkey_dependency = "Quartz" if hotkey_backend == "quartz" else "keyboard"
        hotkey_module = _optional_import(hotkey_dependency)
        if hotkey_module is None:
            self._startup_error = f"Voice unavailable: missing dependencies ({hotkey_dependency})."
            self._enabled = False
            print(f"[VoiceService] {self._startup_error}")
            return False

        if hotkey_backend == "quartz" and not HotkeyListenerThread._macos_access_granted(hotkey_module):
            self._startup_error = (
                "Voice hotkey unavailable: allow Terminal or Python in macOS "
                "Privacy & Security > Accessibility and Input Monitoring, then restart."
            )
            self._enabled = False
            print(f"[VoiceService] {self._startup_error}")
            return False

        try:
            self._hotkey_thread = HotkeyListenerThread(self.hotkey, backend=hotkey_backend)
            self._hotkey_thread.hotkey_pressed.connect(self._on_hotkey_pressed)
            self._hotkey_thread.hotkey_released.connect(self._on_hotkey_released)
            self._hotkey_thread.listener_error.connect(self._on_listener_error)
            self._hotkey_thread.start()
            self._enabled = True
            self._startup_error = ""
            self._resolved_device = WhisperTranscriberThread.detect_device()
            self._start_model_warmup()
            print(f"[VoiceService] Ready. Hold {self.hotkey.upper()} to speak.")
            return True
        except Exception as exc:
            self._enabled = False
            self._startup_error = f"Voice startup failed: {exc}"
            print(f"[VoiceService] {self._startup_error}")
            return False

    def stop(self):
        """Stop background hotkey listening and any in-flight recording/transcription."""
        self._enabled = False
        self._is_listening = False

        if self._hotkey_thread is not None:
            self._hotkey_thread.stop()
            self._hotkey_thread.wait(2000)
            self._hotkey_thread.deleteLater()
            self._hotkey_thread = None

        if self._recorder is not None:
            if self._recorder.isRunning():
                self._recorder.stop_recording()
                self._recorder.wait(2000)
            self._recorder.deleteLater()
            self._recorder = None

        if self._transcriber is not None:
            if self._transcriber.isRunning():
                self._transcriber.wait(2000)
            self._transcriber.deleteLater()
            self._transcriber = None

        if self._warmup_thread is not None:
            if self._warmup_thread.isRunning():
                self._warmup_thread.wait(2000)
            self._warmup_thread.deleteLater()
            self._warmup_thread = None

    def is_available(self) -> bool:
        return self._enabled and self._hotkey_thread is not None and self._hotkey_thread.isRunning()

    def startup_error(self) -> str:
        return self._startup_error

    def _on_hotkey_pressed(self):
        if not self._enabled or self._is_listening:
            return
        if self._recorder is not None and self._recorder.isRunning():
            return

        self._is_listening = True
        self.listening_started.emit()
        recorder = AudioRecorderThread()
        recorder.recording_stopped.connect(self._on_recording_stopped)
        recorder.finished.connect(lambda: self._on_recorder_finished(recorder))
        self._recorder = recorder
        recorder.start()

    def _on_hotkey_released(self):
        if not self._is_listening:
            return

        self._is_listening = False
        self.listening_stopped.emit()
        if self._recorder is not None and self._recorder.isRunning():
            self._recorder.stop_recording()

    def _on_recording_stopped(self, capture: object):
        if isinstance(capture, AudioCapture):
            if capture.duration_seconds < self.MIN_AUDIO_SECONDS:
                self.error_occurred.emit("Recording too short - speak longer.")
                self.transcription_done.emit()
                return

            self._transcriber = WhisperTranscriberThread(
                audio_input=capture.samples,
                model_size=self.model_size,
                language=self.language,
                preferred_device=self._resolved_device,
            )
            self._transcriber.transcription_ready.connect(self._on_transcription_ready)
            self._transcriber.transcription_failed.connect(self._on_transcription_failed)
            self._transcriber.finished.connect(self._on_transcriber_finished)
            self._transcriber.start()
            return

        audio_path = capture if isinstance(capture, str) else ""
        if not audio_path or not os.path.exists(audio_path):
            self.error_occurred.emit("No audio captured.")
            self.transcription_done.emit()
            return

        min_bytes = int(AudioRecorderThread.SAMPLE_RATE * 2 * self.MIN_AUDIO_SECONDS)
        try:
            size_bytes = os.path.getsize(audio_path)
        except OSError:
            size_bytes = 0

        if size_bytes < min_bytes:
            self._cleanup_audio_file(audio_path)
            self.error_occurred.emit("Recording too short - speak longer.")
            self.transcription_done.emit()
            return

        self._transcriber = WhisperTranscriberThread(
            audio_input=audio_path,
            model_size=self.model_size,
            language=self.language,
            preferred_device=self._resolved_device,
        )
        self._transcriber.transcription_ready.connect(self._on_transcription_ready)
        self._transcriber.transcription_failed.connect(self._on_transcription_failed)
        self._transcriber.finished.connect(self._on_transcriber_finished)
        self._transcriber.start()

    def _on_transcription_ready(self, text: str):
        self.command_ready.emit(text)

    def _on_transcription_failed(self, error: str):
        self.error_occurred.emit(f"Transcription failed: {error}")

    def _on_recorder_finished(self, recorder: AudioRecorderThread):
        if self._recorder is recorder:
            self._recorder = None
        recorder.deleteLater()

    def _on_transcriber_finished(self):
        audio_path = None
        if self._transcriber is not None:
            self._resolved_device = self._transcriber.resolved_device or self._resolved_device
            audio_path = self._transcriber.audio_path
            self._transcriber.deleteLater()
            self._transcriber = None

        self._cleanup_audio_file(audio_path)
        self.transcription_done.emit()

    def _on_listener_error(self, error: str):
        self._enabled = False
        self._startup_error = error
        self.error_occurred.emit(f"Voice hotkey unavailable: {error}")

    def _start_model_warmup(self):
        if self._warmup_thread is not None:
            return
        if WhisperTranscriberThread.is_model_cached(self.model_size, self._resolved_device):
            return

        self._warmup_thread = WhisperWarmupThread(
            model_size=self.model_size,
            preferred_device=self._resolved_device,
        )
        self._warmup_thread.warmup_complete.connect(self._on_warmup_complete)
        self._warmup_thread.warmup_failed.connect(self._on_warmup_failed)
        self._warmup_thread.finished.connect(self._on_warmup_finished)
        self._warmup_thread.start(QThread.LowPriority)

    def _on_warmup_complete(self, device: str):
        self._resolved_device = device or self._resolved_device

    def _on_warmup_failed(self, error: str):
        print(f"[VoiceService] Whisper warmup skipped: {error}")

    def _on_warmup_finished(self):
        if self._warmup_thread is None:
            return
        self._warmup_thread.deleteLater()
        self._warmup_thread = None

    @staticmethod
    def _select_hotkey_backend() -> str:
        return "quartz" if sys.platform == "darwin" else "keyboard"

    @staticmethod
    def _cleanup_audio_file(audio_path: Optional[str]):
        if not isinstance(audio_path, str) or not audio_path:
            return
        try:
            if os.path.exists(audio_path):
                os.remove(audio_path)
        except OSError:
            pass
