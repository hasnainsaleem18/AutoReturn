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
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from collections import deque
from dataclasses import dataclass
from difflib import get_close_matches
from threading import Lock
from typing import Any, Dict, Optional

from PySide6.QtCore import QObject, QThread, Signal

from src.backend.models.automation_models import VoiceActivationMode


def _optional_import(module_name: str):
    """Import a module lazily and tolerate missing optional dependencies."""
    try:
        return importlib.import_module(module_name)
    except Exception:
        return None


def _optional_dependency_available(module_name: str) -> bool:
    """Check whether an optional dependency exists without importing it."""
    try:
        return importlib.util.find_spec(module_name) is not None
    except Exception:
        return False


def _use_macos_subprocess_audio() -> bool:
    """Return True when PortAudio work must stay out of the main process."""
    return sys.platform == "darwin" and os.environ.get("AUTORETURN_INLINE_AUDIO") != "1"


def _use_macos_subprocess_transcription() -> bool:
    """Return True when Whisper/Torch work must stay out of the main process."""
    return sys.platform == "darwin" and os.environ.get("AUTORETURN_INLINE_TRANSCRIBE") != "1"


def _microphone_access_error_message(error: Exception) -> str:
    details = str(error).strip()
    if sys.platform == "darwin":
        message = (
            "Microphone access is unavailable. macOS may be blocking microphone "
            "permission. Allow microphone access for Visual Studio Code, Terminal, "
            "or Python in System Preferences > Security & Privacy > Privacy > "
            "Microphone, then try Mic again."
        )
    else:
        message = (
            "Microphone access is unavailable. Check your operating system "
            "microphone privacy settings, then try Mic again."
        )
    if details:
        return f"{message} Details: {details}"
    return message


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

    TRAILING_PUNCTUATION = " \t\r\n.,!?;:"
    WAKE_WORD_ALIASES = (
        ("hey", "autoreturn"),
        ("hi", "autoreturn"),
        ("hello", "autoreturn"),
        ("okay", "autoreturn"),
        ("ok", "autoreturn"),
    )

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

    COMMAND_VOCABULARY = {
        "all",
        "analyze",
        "back",
        "check",
        "draft",
        "email",
        "everything",
        "fetch",
        "find",
        "for",
        "generate",
        "get",
        "gmail",
        "go",
        "high",
        "look",
        "mail",
        "message",
        "messages",
        "next",
        "notification",
        "notifications",
        "open",
        "page",
        "previous",
        "priority",
        "read",
        "reply",
        "respond",
        "search",
        "send",
        "settings",
        "show",
        "slack",
        "summaries",
        "summarize",
        "summary",
        "sync",
        "to",
        "urgent",
        "view",
        "write",
    }

    @classmethod
    def parse(cls, raw_text: str) -> VoiceCommand:
        """Parse a spoken command into a UI action or orchestrator fallback."""
        cleaned_raw = cls._cleanup_transcribed_text(raw_text)
        wake_command = cls.extract_wake_command(cleaned_raw)
        if wake_command is not None:
            if not wake_command:
                return VoiceCommand("ui_action", "noop", {}, raw_text)
            cleaned_raw = wake_command
        text = cls._normalize(cleaned_raw)
        if not text:
            return VoiceCommand("ui_action", "noop", {}, raw_text)

        corrected_text = cls._correct_command_tokens(text)

        ui_match = cls._match_ui_action(corrected_text)
        if ui_match is None:
            ui_match = cls._match_fuzzy_ui_action(corrected_text)
        if ui_match is not None:
            action, params = ui_match
            return VoiceCommand("ui_action", action, dict(params), raw_text)

        search_query = cls._extract_search_query(cleaned_raw, corrected_text)
        if search_query:
            return VoiceCommand("ui_action", "search", {"query": search_query}, raw_text)

        reply_target = cls._extract_reply_target(corrected_text)
        if reply_target:
            return VoiceCommand(
                "ui_action",
                "reply_to_sender",
                {"sender_name": reply_target},
                raw_text,
            )

        draft_target = cls._extract_draft_target(corrected_text)
        if draft_target:
            return VoiceCommand(
                "ui_action",
                "draft_for_sender",
                {"sender_name": draft_target},
                raw_text,
            )

        message_index = cls._extract_message_index(corrected_text)
        if message_index is not None and cls._contains_any(corrected_text, ("open", "show", "read", "view")):
            return VoiceCommand(
                "ui_action",
                "open_message_by_index",
                {"index": message_index},
                raw_text,
            )

        if cls._contains_any(corrected_text, cls.BACKEND_TRIGGERS):
            return VoiceCommand(
                "agent_action",
                "orchestrator",
                {"command": cleaned_raw},
                raw_text,
            )

        if len(text.split()) < 2:
            return VoiceCommand("ui_action", "noop", {}, raw_text)

        return VoiceCommand(
            "agent_action",
            "orchestrator",
            {"command": cleaned_raw},
            raw_text,
        )

    @classmethod
    def _normalize(cls, text: str) -> str:
        return re.sub(r"\s+", " ", (text or "").strip()).lower()

    @classmethod
    def _cleanup_transcribed_text(cls, text: str) -> str:
        cleaned = re.sub(r"\s+", " ", (text or "").strip())
        cleaned = cleaned.strip(cls.TRAILING_PUNCTUATION)
        return cleaned

    @classmethod
    def extract_wake_command(cls, text: str) -> Optional[str]:
        normalized = cls._normalize(text)
        if not normalized:
            return None

        normalized = normalized.replace("auto return", "autoreturn")
        normalized = normalized.replace("auto-return", "autoreturn")
        tokens = normalized.split()
        if len(tokens) < 2:
            return None

        wake_matches = cls.WAKE_WORD_ALIASES
        first = tokens[0]
        second = cls._closest_token(tokens[1], ("autoreturn",))
        for intro, expected_name in wake_matches:
            if first == intro and second == expected_name:
                remainder = " ".join(tokens[2:]).strip()
                remainder = re.sub(r"^(please\s+)", "", remainder)
                return cls._cleanup_transcribed_text(remainder)
        return None

    @classmethod
    def _correct_command_tokens(cls, text: str) -> str:
        corrected_tokens = []
        for token in text.split():
            bare = token.strip(cls.TRAILING_PUNCTUATION)
            if not bare or "@" in bare or any(char.isdigit() for char in bare):
                corrected_tokens.append(bare or token)
                continue

            if bare in cls.COMMAND_VOCABULARY or len(bare) < 4:
                corrected_tokens.append(bare)
                continue

            corrected_tokens.append(cls._closest_token(bare, tuple(cls.COMMAND_VOCABULARY), cutoff=0.84))
        return " ".join(corrected_tokens)

    @classmethod
    def _closest_token(cls, token: str, vocabulary: tuple[str, ...], cutoff: float = 0.84) -> str:
        match = get_close_matches(token, vocabulary, n=1, cutoff=cutoff)
        return match[0] if match else token

    @classmethod
    def _match_ui_action(cls, text: str) -> Optional[tuple]:
        for phrase, result in cls.UI_ACTIONS.items():
            if text == phrase:
                return result
            if re.fullmatch(rf"(?:please\s+)?{re.escape(phrase)}(?:\s+please)?", text):
                return result
        return None

    @classmethod
    def _match_fuzzy_ui_action(cls, text: str) -> Optional[tuple]:
        match = get_close_matches(text, tuple(cls.UI_ACTIONS.keys()), n=1, cutoff=0.88)
        if not match:
            return None
        return cls.UI_ACTIONS.get(match[0])

    @classmethod
    def _extract_search_query(cls, raw_text: str, corrected_text: Optional[str] = None) -> Optional[str]:
        for pattern in cls.SEARCH_PATTERNS:
            match = pattern.match(raw_text or "")
            if match:
                query = cls._clean_search_query(match.group(1))
                return query or None

        fallback_text = corrected_text or ""
        fallback_patterns = (
            re.compile(r"^\s*search\s+for\s+(.+?)\s*$", re.IGNORECASE),
            re.compile(r"^\s*search\s+(.+?)\s*$", re.IGNORECASE),
            re.compile(r"^\s*find\s+(.+?)\s*$", re.IGNORECASE),
            re.compile(r"^\s*look\s+for\s+(.+?)\s*$", re.IGNORECASE),
        )
        for pattern in fallback_patterns:
            match = pattern.match(fallback_text)
            if match:
                query = cls._clean_search_query(match.group(1))
                return query or None
        return None

    @classmethod
    def _clean_search_query(cls, query: str) -> Optional[str]:
        cleaned = re.sub(r"\s+", " ", (query or "").strip())
        cleaned = cleaned.strip("\"'`")
        cleaned = cleaned.rstrip(".,!?;:")
        return cleaned or None

    @classmethod
    def _extract_reply_target(cls, text: str) -> Optional[str]:
        patterns = (
            r"\b(?:reply|respond)\s+(?:to|too)\s+(.+?)\s*$",
            r"\bsend\s+(?:a\s+)?message\s+(?:to|too)\s+(.+?)\s*$",
        )
        return cls._extract_named_target(text, patterns)

    @classmethod
    def _extract_draft_target(cls, text: str) -> Optional[str]:
        patterns = (
            r"\bdraft(?:\s+(?:a|the))?(?:\s+response)?\s+(?:for|to|too)\s+(.+?)\s*$",
            r"\bwrite(?:\s+(?:a|the))?(?:\s+response)?\s+(?:for|to|too)\s+(.+?)\s*$",
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
    recording_failed = Signal(str)

    SAMPLE_RATE = 16000
    BLOCK_SIZE = 2048
    MAX_SECONDS = 30
    TARGET_PEAK = 0.92
    MAX_GAIN = 6.0
    MIN_SIGNAL_PEAK = 0.015
    AUTO_STOP_SILENCE_SECONDS = 0.95
    EDGE_NOISE_SECONDS = 0.18
    TRIM_PADDING_SECONDS = 0.18
    LOW_FREQUENCY_CUTOFF = 80
    STOP_TIMEOUT_SECONDS = 5.0

    def __init__(
        self,
        stop_on_silence: bool = False,
        input_device: Optional[int] = None,
        np_module=None,
        sd_module=None,
        signal_module=None,
    ):
        super().__init__()
        self._stop_flag = False
        self.stop_on_silence = stop_on_silence
        self.input_device = input_device
        self._np_module = np_module
        self._sd_module = sd_module
        self._signal_module = signal_module
        self._process: Optional[subprocess.Popen] = None
        self._stop_path: Optional[str] = None

    def run(self):
        input_device = self.input_device
        if _use_macos_subprocess_audio():
            self._run_subprocess_recorder()
            return

        if input_device is None:
            error = RuntimeError(
                "No preflighted microphone input device was provided. "
                "Try Mic again after allowing microphone access."
            )
            self.recording_failed.emit(_microphone_access_error_message(error))
            self.recording_stopped.emit(None)
            return

        np = self._np_module or _optional_import("numpy")
        signal = self._signal_module
        if np is None:
            self.recording_failed.emit("Voice recording dependencies are unavailable.")
            self.recording_stopped.emit(None)
            return

        sd = self._sd_module or _optional_import("sounddevice")
        if sd is None:
            self.recording_failed.emit("Voice recording dependencies are unavailable.")
            self.recording_stopped.emit(None)
            return

        self._run_inline_recorder(np, sd, signal, input_device)

    def _run_inline_recorder(self, np, sd, signal, input_device: int):
        frames = []
        total_frames = 0

        # Detect supported sample rate — try 16000 first, fall back to native
        sample_rate = self.SAMPLE_RATE
        try:
            sd.check_input_settings(device=input_device, channels=1,
                                    samplerate=sample_rate, dtype="float32")
        except Exception:
            try:
                device_info = sd.query_devices(input_device, 'input')
                sample_rate = int(device_info.get('default_samplerate', 44100))
                print(f"[VoiceService] 16000Hz not supported, using {sample_rate}Hz")
            except Exception:
                sample_rate = 44100

        max_frames = sample_rate * self.MAX_SECONDS
        silence_seconds = 0.0
        speech_detected = False

        try:
            with sd.InputStream(
                device=input_device,
                samplerate=sample_rate,
                channels=1,
                dtype="float32",
                blocksize=self.BLOCK_SIZE,
                latency="high",
            ) as stream:
                while not self._stop_flag and total_frames < max_frames:
                    block, _overflowed = stream.read(self.BLOCK_SIZE)
                    block_copy = block.copy()
                    frames.append(block_copy)
                    total_frames += len(block)

                    if self.stop_on_silence:
                        peak = float(np.max(np.abs(block_copy))) if len(block_copy) else 0.0
                        if peak >= self.MIN_SIGNAL_PEAK * 0.9:
                            speech_detected = True
                            silence_seconds = 0.0
                        elif speech_detected:
                            silence_seconds += len(block_copy) / float(sample_rate)
                            if silence_seconds >= self.AUTO_STOP_SILENCE_SECONDS:
                                break
        except Exception as exc:
            message = _microphone_access_error_message(exc)
            print(f"[VoiceService] Recording error: {message}")
            self.recording_failed.emit(message)
            self.recording_stopped.emit(None)
            return

        if not frames:
            self.recording_stopped.emit(None)
            return

        try:
            audio = np.concatenate(frames, axis=0).flatten()
            capture = self.prepare_capture(
                audio,
                sample_rate=sample_rate,
                np_module=np,
                signal_module=signal,
            )
            self.recording_stopped.emit(capture)
        except Exception as exc:
            print(f"[VoiceService] Failed to prepare audio capture: {exc}")
            self.recording_stopped.emit(None)

    def stop_recording(self):
        self._stop_flag = True
        self._write_stop_file()

    def _write_stop_file(self):
        if not self._stop_path:
            return
        try:
            with open(self._stop_path, "w", encoding="utf-8") as stop_file:
                stop_file.write("stop")
        except OSError:
            pass

    def _run_subprocess_recorder(self):
        output_fd, output_path = tempfile.mkstemp(prefix="autoreturn_voice_", suffix=".npy")
        os.close(output_fd)
        try:
            os.unlink(output_path)
        except OSError:
            pass

        with tempfile.TemporaryDirectory(prefix="autoreturn_voice_") as temp_dir:
            stop_path = os.path.join(temp_dir, "stop")
            self._stop_path = stop_path
            if self._stop_flag:
                self._write_stop_file()

            args = [
                sys.executable,
                "-c",
                self._subprocess_recorder_code(),
                output_path,
                stop_path,
                "" if self.input_device is None else str(self.input_device),
                str(self.SAMPLE_RATE),
                str(self.BLOCK_SIZE),
                str(self.MAX_SECONDS),
                "1" if self.stop_on_silence else "0",
                str(self.MIN_SIGNAL_PEAK),
                str(self.AUTO_STOP_SILENCE_SECONDS),
            ]

            try:
                process = subprocess.Popen(
                    args,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                self._process = process
            except Exception as exc:
                self._process = None
                self.recording_failed.emit(_microphone_access_error_message(exc))
                self._cleanup_output_file(output_path)
                self.recording_stopped.emit(None)
                self._stop_path = None
                return

            stop_started_at = None
            while process.poll() is None:
                if self._stop_flag:
                    self._write_stop_file()
                    if stop_started_at is None:
                        stop_started_at = time.monotonic()
                    elif time.monotonic() - stop_started_at > self.STOP_TIMEOUT_SECONDS:
                        process.terminate()
                        break
                time.sleep(0.05)

            try:
                stdout, stderr = process.communicate(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                stdout, stderr = process.communicate()

            return_code = process.returncode
            self._process = None
            self._stop_path = None

            if return_code != 0:
                details = (stderr or stdout or "").strip()
                if return_code is not None and return_code < 0:
                    message = (
                        "Voice recording crashed in the isolated macOS audio process. "
                        "This usually means CoreAudio/PortAudio could not safely open "
                        "the microphone for this launcher."
                    )
                else:
                    message = "Voice recording failed in the isolated macOS audio process."
                if details:
                    message = f"{message} Details: {details}"
                self.recording_failed.emit(message)
                self._cleanup_output_file(output_path)
                self.recording_stopped.emit(None)
                return

            if not os.path.exists(output_path):
                self._cleanup_output_file(output_path)
                self.recording_stopped.emit(None)
                return

            self.recording_stopped.emit(output_path)

    @staticmethod
    def _cleanup_output_file(output_path: Optional[str]):
        if not output_path:
            return
        try:
            if os.path.exists(output_path):
                os.remove(output_path)
        except OSError:
            pass

    @staticmethod
    def _subprocess_recorder_code() -> str:
        return r'''
import os
import sys
import traceback

import numpy as np
import sounddevice as sd

output_path = sys.argv[1]
stop_path = sys.argv[2]
input_device_arg = sys.argv[3].strip()
sample_rate = int(sys.argv[4])
block_size = int(sys.argv[5])
max_seconds = float(sys.argv[6])
stop_on_silence = sys.argv[7] == "1"
min_signal_peak = float(sys.argv[8])
auto_stop_silence_seconds = float(sys.argv[9])

frames = []
total_frames = 0
max_frames = int(sample_rate * max_seconds)
silence_seconds = 0.0
speech_detected = False

def resolve_input_device():
    if input_device_arg:
        return int(input_device_arg)

    devices = sd.query_devices()
    input_devices = []
    for index, device in enumerate(devices):
        try:
            max_input_channels = int(device.get("max_input_channels", 0))
        except Exception:
            max_input_channels = 0
        if max_input_channels > 0:
            input_devices.append(index)

    if not input_devices:
        raise RuntimeError(
            "No microphone input device is visible to Python. "
            "macOS may be blocking microphone access for this app."
        )

    try:
        default_device = sd.default.device
        if isinstance(default_device, (list, tuple)):
            default_input = int(default_device[0])
        else:
            default_input = int(default_device)
        if default_input in input_devices:
            return default_input
    except Exception:
        pass

    return input_devices[0]

try:
    input_device = resolve_input_device()
    with sd.InputStream(
        device=input_device,
        samplerate=sample_rate,
        channels=1,
        dtype="float32",
        blocksize=block_size,
        latency="high",
    ) as stream:
        while not os.path.exists(stop_path) and total_frames < max_frames:
            block, _overflowed = stream.read(block_size)
            block_copy = block.copy()
            frames.append(block_copy)
            total_frames += len(block_copy)

            if stop_on_silence:
                peak = float(np.max(np.abs(block_copy))) if len(block_copy) else 0.0
                if peak >= min_signal_peak * 0.9:
                    speech_detected = True
                    silence_seconds = 0.0
                elif speech_detected:
                    silence_seconds += len(block_copy) / float(sample_rate)
                    if silence_seconds >= auto_stop_silence_seconds:
                        break

    if frames:
        audio = np.concatenate(frames, axis=0).flatten().astype(np.float32)
        np.save(output_path, audio, allow_pickle=False)
except Exception:
    traceback.print_exc()
    sys.exit(2)
'''

    @classmethod
    def check_microphone_available(cls, sd_module=None) -> tuple[bool, str, Optional[int]]:
        """Return whether a usable microphone input device is visible to sounddevice."""
        sd = sd_module or _optional_import("sounddevice")
        if sd is None:
            return False, "Voice recording dependency sounddevice is unavailable.", None

        try:
            input_device = cls._resolve_input_device(sd)
        except Exception as exc:
            return False, _microphone_access_error_message(exc), None

        if input_device is None:
            error = RuntimeError(
                "No microphone input device is visible to Python. "
                "macOS may be blocking microphone access for this app."
            )
            return False, _microphone_access_error_message(error), None

        try:
            sd.check_input_settings(
                device=input_device,
                channels=1,
                samplerate=cls.SAMPLE_RATE,
                dtype="float32",
            )
        except Exception:
            # 16000 not supported — try device's native sample rate
            try:
                device_info = sd.query_devices(input_device, 'input')
                native_rate = int(device_info.get('default_samplerate', 44100))
                sd.check_input_settings(
                    device=input_device,
                    channels=1,
                    samplerate=native_rate,
                    dtype="float32",
                )
                print(f"[VoiceService] Using native sample rate: {native_rate}Hz")
            except Exception as exc:
                return False, _microphone_access_error_message(exc), None

        return True, "", input_device

    @staticmethod
    def _resolve_input_device(sd_module) -> Optional[int]:
        devices = sd_module.query_devices()
        input_devices = []
        for index, device in enumerate(devices):
            try:
                max_input_channels = int(device.get("max_input_channels", 0))
            except (AttributeError, TypeError, ValueError):
                max_input_channels = 0
            if max_input_channels > 0:
                input_devices.append(index)

        if not input_devices:
            return None

        try:
            default_device = sd_module.default.device
            if isinstance(default_device, (list, tuple)):
                default_input = default_device[0]
            else:
                default_input = default_device
            default_input = int(default_input)
        except Exception:
            default_input = -1

        if default_input in input_devices:
            return default_input
        return input_devices[0]

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


class WakeWordListenerThread(QThread):
    """Listen for short wake-word utterances in the background."""

    wake_audio_ready = Signal(object)
    listener_error = Signal(str)

    SAMPLE_RATE = 16000
    BLOCK_SIZE = 1024
    MIN_SIGNAL_PEAK = 0.02
    MIN_CAPTURE_SECONDS = 0.7
    MAX_CAPTURE_SECONDS = 4.5
    SILENCE_SECONDS = 0.8
    PRE_ROLL_SECONDS = 0.35

    def __init__(
        self,
        input_device: Optional[int] = None,
        np_module=None,
        sd_module=None,
        signal_module=None,
    ):
        super().__init__()
        self._running = False
        self.input_device = input_device
        self._np_module = np_module
        self._sd_module = sd_module
        self._signal_module = signal_module

    def run(self):
        if sys.platform == "darwin" and (self._np_module is None or self._sd_module is None):
            self.listener_error.emit("Wake word listener dependencies were not prepared before startup.")
            return

        np = self._np_module or _optional_import("numpy")
        sd = self._sd_module or _optional_import("sounddevice")
        signal = self._signal_module

        if np is None or sd is None:
            self.listener_error.emit("Wake word listener dependencies are unavailable.")
            return

        self._running = True
        history = deque(maxlen=max(int(self.PRE_ROLL_SECONDS * self.SAMPLE_RATE / self.BLOCK_SIZE), 1))
        frames = []
        segment_seconds = 0.0
        silence_seconds = 0.0
        speech_detected = False

        try:
            with sd.InputStream(
                device=self.input_device,
                samplerate=self.SAMPLE_RATE,
                channels=1,
                dtype="float32",
                blocksize=self.BLOCK_SIZE,
                latency="high",
            ) as stream:
                while self._running:
                    block, _overflowed = stream.read(self.BLOCK_SIZE)
                    block_copy = block.copy()
                    peak = float(np.max(np.abs(block_copy))) if len(block_copy) else 0.0
                    block_seconds = len(block_copy) / float(self.SAMPLE_RATE)

                    if not speech_detected:
                        history.append(block_copy)
                        if peak >= self.MIN_SIGNAL_PEAK:
                            speech_detected = True
                            frames = list(history)
                            history.clear()
                            segment_seconds = sum(len(frame) for frame in frames) / float(self.SAMPLE_RATE)
                            silence_seconds = 0.0
                        continue

                    frames.append(block_copy)
                    segment_seconds += block_seconds

                    if peak >= self.MIN_SIGNAL_PEAK * 0.8:
                        silence_seconds = 0.0
                    else:
                        silence_seconds += block_seconds

                    if segment_seconds >= self.MAX_CAPTURE_SECONDS or silence_seconds >= self.SILENCE_SECONDS:
                        self._emit_capture(frames, np, signal)
                        frames = []
                        segment_seconds = 0.0
                        silence_seconds = 0.0
                        speech_detected = False
        except Exception as exc:
            if self._running:
                self.listener_error.emit(_microphone_access_error_message(exc))
        finally:
            self._running = False

    def stop(self):
        self._running = False
        self.quit()

    def _emit_capture(self, frames, np_module, signal_module):
        if not frames:
            return

        try:
            audio = np_module.concatenate(frames, axis=0).flatten()
            capture = AudioRecorderThread.prepare_capture(
                audio,
                sample_rate=self.SAMPLE_RATE,
                np_module=np_module,
                signal_module=signal_module,
            )
        except Exception:
            capture = None

        if capture is None or capture.duration_seconds < self.MIN_CAPTURE_SECONDS:
            return

        self.wake_audio_ready.emit(capture)


class WhisperTranscriberThread(QThread):
    """Transcribe a prepared audio buffer using local Whisper."""

    transcription_ready = Signal(str)
    transcription_failed = Signal(str)
    DEFAULT_MODEL_SIZE = "small"
    COMMAND_PROMPT = (
        "Voice commands for AutoReturn. Keywords include gmail, slack, urgent, "
        "settings, notifications, search, reply, draft, summarize, sync, "
        "next page, previous page, message, and the wake phrase 'Hey AutoReturn'."
    )

    _model_cache: Dict[tuple[str, str], Any] = {}
    _cache_lock = Lock()
    _device_cache: Optional[str] = None
    SUBPROCESS_TIMEOUT_SECONDS = 180

    def __init__(
        self,
        audio_input: Any,
        model_size: str = DEFAULT_MODEL_SIZE,
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
        if _use_macos_subprocess_transcription():
            self._run_subprocess_transcription()
            return

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
                initial_prompt=self.COMMAND_PROMPT,
                temperature=0.0,
                no_speech_threshold=0.45,
            )
            text = VoiceCommandParser._cleanup_transcribed_text(result.get("text") or "")
            if text:
                self.transcription_ready.emit(text)
            else:
                self.transcription_failed.emit("Empty transcription.")
        except Exception as exc:
            self.transcription_failed.emit(str(exc))

    def _run_subprocess_transcription(self):
        temp_dir_context = None
        if isinstance(self.audio_input, str):
            audio_path = self.audio_input
            if not os.path.exists(audio_path):
                self.transcription_failed.emit("Voice audio file is missing.")
                return
        else:
            np = _optional_import("numpy")
            if np is None:
                self.transcription_failed.emit("numpy dependency is not installed.")
                return

            temp_dir_context = tempfile.TemporaryDirectory(prefix="autoreturn_transcribe_")
            audio_path = os.path.join(temp_dir_context.name, "voice.npy")
            try:
                audio = np.asarray(self.audio_input, dtype=np.float32).flatten()
                np.save(audio_path, audio.astype(np.float32), allow_pickle=False)
            except Exception as exc:
                temp_dir_context.cleanup()
                self.transcription_failed.emit(f"Could not prepare voice audio for transcription: {exc}")
                return

        try:
            args = [
                sys.executable,
                "-c",
                self._subprocess_transcriber_code(),
                audio_path,
                self.model_size,
                self.language or "en",
                self.preferred_device or "",
                self.COMMAND_PROMPT,
            ]

            try:
                process = subprocess.run(
                    args,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=self.SUBPROCESS_TIMEOUT_SECONDS,
                )
            except subprocess.TimeoutExpired:
                self.transcription_failed.emit("Voice transcription timed out.")
                return
            except Exception as exc:
                self.transcription_failed.emit(f"Voice transcription process failed: {exc}")
                return

            if process.returncode != 0:
                details = (process.stderr or process.stdout or "").strip()
                if len(details) > 500:
                    details = details[-500:]
                message = "Voice transcription failed in the isolated macOS process."
                if details:
                    message = f"{message} Details: {details}"
                self.transcription_failed.emit(message)
                return

            try:
                payload_text = (process.stdout or "").strip().splitlines()[-1]
                payload = json.loads(payload_text)
            except Exception as exc:
                self.transcription_failed.emit(f"Voice transcription returned invalid output: {exc}")
                return

            self.resolved_device = payload.get("device") or self.preferred_device
            text = VoiceCommandParser._cleanup_transcribed_text(payload.get("text") or "")
            if text:
                self.transcription_ready.emit(text)
            else:
                self.transcription_failed.emit("Empty transcription.")
        finally:
            if temp_dir_context is not None:
                temp_dir_context.cleanup()

    @staticmethod
    def _subprocess_transcriber_code() -> str:
        return r'''
import json
import sys
import traceback

import numpy as np

audio_path = sys.argv[1]
model_size = sys.argv[2]
language = sys.argv[3] or "en"
preferred_device = sys.argv[4] or None
command_prompt = sys.argv[5]

def optional_import(module_name):
    try:
        return __import__(module_name)
    except Exception:
        return None

def detect_device():
    torch = optional_import("torch")
    if torch is None:
        return "cpu"
    try:
        if torch.cuda.is_available():
            return "cuda"
        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            return "mps"
    except Exception:
        pass
    return "cpu"

try:
    whisper = optional_import("whisper")
    if whisper is None:
        raise RuntimeError("whisper dependency is not installed.")

    audio = np.load(audio_path, allow_pickle=False).astype(np.float32).flatten()
    device = preferred_device or detect_device()
    try:
        model = whisper.load_model(model_size, device=device)
    except Exception:
        if device == "cpu":
            raise
        device = "cpu"
        model = whisper.load_model(model_size, device=device)

    result = model.transcribe(
        audio,
        language=language,
        task="transcribe",
        fp16=device == "cuda",
        verbose=False,
        condition_on_previous_text=False,
        initial_prompt=command_prompt,
        temperature=0.0,
        no_speech_threshold=0.45,
    )
    print(json.dumps({"text": result.get("text") or "", "device": device}))
except Exception:
    traceback.print_exc()
    sys.exit(2)
'''

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
    def warm_runtime(
        cls,
        model_size: str,
        preferred_device: Optional[str] = None,
        language: str = "en",
    ) -> str:
        """Load the model and run a tiny silent inference to warm the first command path."""
        model, device = cls.load_cached_model(model_size, preferred_device)
        np = _optional_import("numpy")
        if np is None:
            return device

        try:
            warmup_audio = np.zeros(16000, dtype=np.float32)
            model.transcribe(
                warmup_audio,
                language=language,
                task="transcribe",
                fp16=device == "cuda",
                verbose=False,
                condition_on_previous_text=False,
                initial_prompt=cls.COMMAND_PROMPT,
                temperature=0.0,
                no_speech_threshold=0.45,
            )
        except Exception:
            # Runtime warmup is best-effort; loaded model is still useful even if the dry run fails.
            pass
        return device

    @classmethod
    def is_model_cached(cls, model_size: str, preferred_device: Optional[str] = None) -> bool:
        device = preferred_device or cls.detect_device()
        return (model_size, device) in cls._model_cache or (model_size, "cpu") in cls._model_cache


class WhisperWarmupThread(QThread):
    """Warm Whisper in the background so the first command responds faster."""

    warmup_complete = Signal(str)
    warmup_failed = Signal(str)

    def __init__(
        self,
        model_size: str = WhisperTranscriberThread.DEFAULT_MODEL_SIZE,
        preferred_device: Optional[str] = None,
        language: str = "en",
    ):
        super().__init__()
        self.model_size = model_size
        self.preferred_device = preferred_device
        self.language = language
        self.resolved_device: Optional[str] = None
        self.last_error: str = ""

    def run(self):
        try:
            device = WhisperTranscriberThread.warm_runtime(
                self.model_size,
                self.preferred_device,
                self.language,
            )
            self.resolved_device = device
            self.warmup_complete.emit(device)
        except Exception as exc:
            self.last_error = str(exc)
            self.warmup_failed.emit(str(exc))


class VoiceService(QObject):
    """Coordinate hotkey listening, recording, and local transcription."""

    command_ready = Signal(str)
    listening_started = Signal()
    listening_stopped = Signal()
    transcription_done = Signal()
    error_occurred = Signal(str)

    MIN_AUDIO_SECONDS = 0.5
    MODEL_SIZE = WhisperTranscriberThread.DEFAULT_MODEL_SIZE
    WAKE_WORD_HINT = "Hey AutoReturn"
    STARTUP_WARMUP_WAIT_MS = 1200

    def __init__(
        self,
        hotkey: str = "ctrl+shift+v",
        model_size: str = MODEL_SIZE,
        activation_mode: str = VoiceActivationMode.MANUAL.value,
        language: str = "en",
    ):
        super().__init__()
        self.hotkey = hotkey
        self.model_size = model_size or self.MODEL_SIZE
        self.activation_mode = self._normalize_activation_mode(activation_mode)
        self.language = language

        self._enabled = False
        self._is_listening = False
        self._startup_error = ""
        self._hotkey_thread: Optional[HotkeyListenerThread] = None
        self._wake_listener: Optional[WakeWordListenerThread] = None
        self._recorder: Optional[AudioRecorderThread] = None
        self._transcriber: Optional[WhisperTranscriberThread] = None
        self._wake_transcriber: Optional[WhisperTranscriberThread] = None
        self._warmup_thread: Optional[WhisperWarmupThread] = None
        self._resolved_device: Optional[str] = None
        self._activation_source: Optional[str] = None
        self._hotkey_available = False
        self._wake_word_available = False
        self._pending_wake_followup = False
        self._startup_prepared = False
        self._last_recording_error = ""

    def start(self) -> bool:
        """Start background voice capture. Returns True when the listener is live."""
        missing = []
        for module_name in ("sounddevice", "numpy"):
            if _use_macos_subprocess_audio():
                module_present = _optional_dependency_available(module_name)
            else:
                module_present = _optional_import(module_name) is not None
            if not module_present:
                missing.append(module_name)

        if missing:
            self._startup_error = f"Voice unavailable: missing dependencies ({', '.join(missing)})."
            self._enabled = False
            print(f"[VoiceService] {self._startup_error}")
            return False

        try:
            self._enabled = True
            self._startup_error = ""
            self._startup_prepared = False
            self._resolved_device = None
            self._start_hotkey_listener()
            if self.activation_mode == VoiceActivationMode.WAKE_WORD.value:
                self._start_wake_listener()
            print(f"[VoiceService] Ready. {self.usage_hint()}")
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
        self._activation_source = None
        self._pending_wake_followup = False
        self._startup_prepared = False

        self._stop_hotkey_listener()
        self._stop_wake_listener()

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

        if self._wake_transcriber is not None:
            if self._wake_transcriber.isRunning():
                self._wake_transcriber.wait(2000)
            self._wake_transcriber.deleteLater()
            self._wake_transcriber = None

        if self._warmup_thread is not None:
            if self._warmup_thread.isRunning():
                self._warmup_thread.wait(2000)
            self._warmup_thread.deleteLater()
            self._warmup_thread = None

    def is_available(self) -> bool:
        return self._enabled

    def is_recording(self) -> bool:
        return self._is_listening

    def last_recording_error(self) -> str:
        return self._last_recording_error

    def current_activation_source(self) -> str:
        return self._activation_source or ""

    def usage_hint(self) -> str:
        triggers = ["click Mic"]
        if self._hotkey_available:
            triggers.append(f"hold {self.hotkey.upper()}")
        if self._wake_word_available:
            triggers.append(f"say '{self.WAKE_WORD_HINT}'")
        if len(triggers) == 1:
            return "Click Mic to start a voice command."
        if len(triggers) == 2:
            return f"Use {triggers[0]} or {triggers[1]} to start a voice command."
        return "Use " + ", ".join(triggers[:-1]) + f", or {triggers[-1]} to start a voice command."

    def startup_error(self) -> str:
        return self._startup_error

    def is_prepared(self) -> bool:
        return self._startup_prepared

    def _on_hotkey_pressed(self):
        self._start_recording_session("hotkey", stop_on_silence=False)

    def _on_hotkey_released(self):
        if self._activation_source == "hotkey":
            self.stop_recording()

    def start_button_capture(self) -> bool:
        return self._start_recording_session("button", stop_on_silence=True)

    def stop_recording(self):
        if self._recorder is not None and self._recorder.isRunning():
            self._recorder.stop_recording()

    def _start_recording_session(self, source: str, stop_on_silence: bool) -> bool:
        if not self._enabled or self._is_listening:
            return False
        if self._recorder is not None and self._recorder.isRunning():
            return False
        if self._transcriber is not None or self._wake_transcriber is not None:
            return False

        self._last_recording_error = ""
        if self.activation_mode == VoiceActivationMode.WAKE_WORD.value:
            self._stop_wake_listener()

        use_subprocess_audio = _use_macos_subprocess_audio()
        input_device = None
        if not use_subprocess_audio:
            mic_check = getattr(AudioRecorderThread, "check_microphone_available", None)
            if callable(mic_check):
                ok, error, input_device = mic_check()
            else:
                ok, error, input_device = True, "", None
            if not ok:
                self._last_recording_error = error or "Microphone access is unavailable."
                self.error_occurred.emit(self._last_recording_error)
                return False

        if use_subprocess_audio:
            np_module = None
            signal_module = None
            sd_module = None
        else:
            np_module = _optional_import("numpy")
            signal_module = _optional_import("scipy.signal")
            sd_module = _optional_import("sounddevice")
            if np_module is None or sd_module is None:
                self._last_recording_error = "Voice recording dependencies are unavailable."
                self.error_occurred.emit(self._last_recording_error)
                return False

        self._activation_source = source
        self._is_listening = True
        self.listening_started.emit()
        recorder_kwargs = {"stop_on_silence": stop_on_silence}
        if input_device is not None:
            recorder_kwargs["input_device"] = input_device
        recorder_kwargs.update(
            {
                "np_module": np_module,
                "sd_module": sd_module,
                "signal_module": signal_module,
            }
        )
        recorder = AudioRecorderThread(**recorder_kwargs)
        recorder.recording_failed.connect(self._on_recording_failed)
        recorder.recording_stopped.connect(self._on_recording_stopped)
        recorder.finished.connect(lambda: self._on_recorder_finished(recorder))
        self._recorder = recorder
        recorder.start()
        return True

    def _on_recording_failed(self, error: str):
        self._last_recording_error = error or "Voice recording failed."
        self.error_occurred.emit(self._last_recording_error)

    def _on_recording_stopped(self, capture: object):
        if self._is_listening:
            self._is_listening = False
            self.listening_stopped.emit()

        if isinstance(capture, AudioCapture):
            if capture.duration_seconds < self.MIN_AUDIO_SECONDS:
                self.error_occurred.emit("Recording too short - speak longer.")
                self._finish_voice_cycle()
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
            if not self._last_recording_error:
                self.error_occurred.emit("No audio captured.")
            self._finish_voice_cycle()
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
            self._finish_voice_cycle()
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
            if self._resolved_device:
                self._startup_prepared = True
            audio_path = self._transcriber.audio_path
            self._transcriber.deleteLater()
            self._transcriber = None

        self._cleanup_audio_file(audio_path)
        self._finish_voice_cycle()
        self.transcription_done.emit()

    def _on_listener_error(self, error: str):
        self._hotkey_available = False
        self.error_occurred.emit(f"Voice hotkey unavailable: {error}")

    def _on_wake_listener_error(self, error: str):
        self._wake_word_available = False
        self.error_occurred.emit(f"Wake word unavailable: {error}")

    def _on_wake_audio_ready(self, capture: object):
        if not self._enabled or self._is_listening or self._transcriber is not None or self._wake_transcriber is not None:
            return
        if not isinstance(capture, AudioCapture):
            return

        self._wake_transcriber = WhisperTranscriberThread(
            audio_input=capture.samples,
            model_size=self.model_size,
            language=self.language,
            preferred_device=self._resolved_device,
        )
        self._wake_transcriber.transcription_ready.connect(self._on_wake_transcription_ready)
        self._wake_transcriber.transcription_failed.connect(self._on_wake_transcription_failed)
        self._wake_transcriber.finished.connect(self._on_wake_transcriber_finished)
        self._wake_transcriber.start()

    def _on_wake_transcription_ready(self, text: str):
        command_text = VoiceCommandParser.extract_wake_command(text)
        if command_text is None:
            return
        if command_text:
            self.command_ready.emit(command_text)
            return
        self._pending_wake_followup = True

    def _on_wake_transcription_failed(self, _error: str):
        return

    def _on_wake_transcriber_finished(self):
        if self._wake_transcriber is not None:
            self._resolved_device = self._wake_transcriber.resolved_device or self._resolved_device
            self._wake_transcriber.deleteLater()
            self._wake_transcriber = None
        if self._pending_wake_followup:
            self._pending_wake_followup = False
            self._start_recording_session("wake-word", stop_on_silence=True)
            return
        if self.activation_mode == VoiceActivationMode.WAKE_WORD.value:
            self._start_wake_listener()

    def _start_hotkey_listener(self):
        hotkey_backend = self._select_hotkey_backend()
        hotkey_dependency = "Quartz" if hotkey_backend == "quartz" else "keyboard"
        hotkey_module = _optional_import(hotkey_dependency)
        if hotkey_module is None:
            self._hotkey_available = False
            return False

        if hotkey_backend == "quartz" and not HotkeyListenerThread._macos_access_granted(hotkey_module):
            self._hotkey_available = False
            return False

        self._stop_hotkey_listener()
        self._hotkey_thread = HotkeyListenerThread(self.hotkey, backend=hotkey_backend)
        self._hotkey_thread.hotkey_pressed.connect(self._on_hotkey_pressed)
        self._hotkey_thread.hotkey_released.connect(self._on_hotkey_released)
        self._hotkey_thread.listener_error.connect(self._on_listener_error)
        self._hotkey_thread.start()
        self._hotkey_available = True
        return True

    def _stop_hotkey_listener(self):
        self._hotkey_available = False
        if self._hotkey_thread is None:
            return
        self._hotkey_thread.stop()
        self._hotkey_thread.wait(2000)
        self._hotkey_thread.deleteLater()
        self._hotkey_thread = None

    def _start_wake_listener(self):
        if self.activation_mode != VoiceActivationMode.WAKE_WORD.value:
            self._wake_word_available = False
            return False
        if not self._enabled or self._is_listening or self._wake_transcriber is not None:
            return False
        if sys.platform == "darwin" and os.environ.get("AUTORETURN_INLINE_AUDIO") != "1":
            self._wake_word_available = False
            return False
        if self._wake_listener is not None and self._wake_listener.isRunning():
            self._wake_word_available = True
            return True

        mic_check = getattr(AudioRecorderThread, "check_microphone_available", None)
        if callable(mic_check):
            ok, error, input_device = mic_check()
        else:
            ok, error, input_device = True, "", None
        if not ok:
            self._wake_word_available = False
            self._last_recording_error = error or "Microphone access is unavailable."
            self.error_occurred.emit(self._last_recording_error)
            return False

        np_module = _optional_import("numpy")
        sd_module = _optional_import("sounddevice")
        signal_module = _optional_import("scipy.signal")
        if np_module is None or sd_module is None:
            self._wake_word_available = False
            self._last_recording_error = "Wake word listener dependencies are unavailable."
            self.error_occurred.emit(self._last_recording_error)
            return False

        self._stop_wake_listener()
        wake_kwargs = {}
        if input_device is not None:
            wake_kwargs["input_device"] = input_device
        wake_kwargs.update(
            {
                "np_module": np_module,
                "sd_module": sd_module,
                "signal_module": signal_module,
            }
        )
        try:
            self._wake_listener = WakeWordListenerThread(**wake_kwargs)
        except TypeError:
            self._wake_listener = WakeWordListenerThread()
        self._wake_listener.wake_audio_ready.connect(self._on_wake_audio_ready)
        self._wake_listener.listener_error.connect(self._on_wake_listener_error)
        self._wake_listener.start()
        self._wake_word_available = True
        return True

    def _stop_wake_listener(self):
        self._wake_word_available = False
        if self._wake_listener is None:
            return
        self._wake_listener.stop()
        self._wake_listener.wait(2000)
        self._wake_listener.deleteLater()
        self._wake_listener = None

    def _finish_voice_cycle(self):
        self._activation_source = None
        if self.activation_mode == VoiceActivationMode.WAKE_WORD.value and self._wake_transcriber is None:
            self._start_wake_listener()

    @staticmethod
    def _normalize_activation_mode(value: str) -> str:
        try:
            return VoiceActivationMode(value).value
        except Exception:
            return VoiceActivationMode.MANUAL.value

    def _start_model_warmup(self):
        if self._warmup_thread is not None:
            return
        if WhisperTranscriberThread.is_model_cached(self.model_size, self._resolved_device):
            self._startup_prepared = True
            return

        self._warmup_thread = WhisperWarmupThread(
            model_size=self.model_size,
            preferred_device=self._resolved_device,
            language=self.language,
        )
        self._warmup_thread.warmup_complete.connect(self._on_warmup_complete)
        self._warmup_thread.warmup_failed.connect(self._on_warmup_failed)
        self._warmup_thread.finished.connect(self._on_warmup_finished)
        self._warmup_thread.start(QThread.LowPriority)

    def _await_initial_warmup(self):
        if self._warmup_thread is None or not self._warmup_thread.isRunning():
            return
        self._warmup_thread.wait(self.STARTUP_WARMUP_WAIT_MS)
        if self._warmup_thread.isRunning():
            return
        if self._warmup_thread.resolved_device:
            self._resolved_device = self._warmup_thread.resolved_device
            self._startup_prepared = True

    def _on_warmup_complete(self, device: str):
        self._resolved_device = device or self._resolved_device
        self._startup_prepared = True

    def _on_warmup_failed(self, error: str):
        print(f"[VoiceService] Whisper warmup skipped: {error}")
        self._startup_prepared = False

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
